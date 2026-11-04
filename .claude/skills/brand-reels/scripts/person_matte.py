"""Person matte (alpha) for every frame of a video: text behind the head, layer splits, cut-outs, "hide me".

usage: python3 person_matte.py <video> <matte.mkv> [--model motion/inputs/selfie.tflite] [--start s --end s]

Two passes per frame with MediaPipe's selfie multiclass segmenter (Apache-2.0, 256x256): a coarse pass on the whole
frame finds the person's box, a second pass on a square crop around it gives the detail, and a guided filter with
the frame as guide snaps the edge to hair and shoulders. A light temporal blend removes flicker. The matte is
written as a lossless 8-bit grey video (FFV1) at the input size and frame rate, frame-aligned with the input.
Needs: pip install mediapipe; apt libegl1 libgles2; the .tflite from
storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/
"""
import argparse, subprocess, numpy as np, cv2
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

def box(x, r):
    return cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1), borderType=cv2.BORDER_REFLECT)

def guided(I, p, r=10, eps=2e-3):
    mI, mp_ = box(I, r), box(p, r)
    a = (box(I * p, r) - mI * mp_) / (box(I * I, r) - mI * mI + eps)
    b = mp_ - a * mI
    return box(a, r) * I + box(b, r)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('out')
    ap.add_argument('--model', default='motion/inputs/selfie.tflite')
    ap.add_argument('--start', type=float, default=0); ap.add_argument('--end', type=float)
    a = ap.parse_args()
    seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
        base_options=BaseOptions(model_asset_path=a.model), output_confidence_masks=True))
    cap = cv2.VideoCapture(a.video); fps = cap.get(cv2.CAP_PROP_FPS)
    W, H = int(cap.get(3)), int(cap.get(4))
    for _ in range(int(round(a.start * fps))): cap.grab()   # frame-exact start (seeking by time can land off by a frame)
    n_end = int(round((a.end - a.start) * fps)) if a.end else None
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', f'{W}x{H}', '-r', f'{fps}',
                           '-i', '-', '-c:v', 'ffv1', '-pix_fmt', 'gray', a.out], stdin=subprocess.PIPE)
    def person(rgb):
        r = seg.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
        return 1.0 - r.confidence_masks[0].numpy_view()   # category 0 = background
    prev = None; n = 0
    while True:
        ok, fr = cap.read()
        if not ok or (n_end is not None and n >= n_end): break
        rgb = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
        # pass 1: whole frame padded to a square
        S = max(W, H); pad = np.zeros((S, S, 3), np.uint8); oy, ox = (S - H) // 2, (S - W) // 2
        pad[oy:oy + H, ox:ox + W] = rgb
        c = cv2.resize(person(pad), (S, S))[oy:oy + H, ox:ox + W]
        ys, xs = np.where(c > 0.5)
        alpha = c
        if len(xs) > 50:
            # pass 2: square crop around the person (with margin) for finer detail
            x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
            side = int(max(x1 - x0, y1 - y0) * 1.15) + 16; side = min(side, max(W, H))
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            X0, Y0 = cx - side // 2, cy - side // 2
            crop = np.zeros((side, side, 3), np.uint8)
            sx0, sy0, sx1, sy1 = max(0, X0), max(0, Y0), min(W, X0 + side), min(H, Y0 + side)
            crop[sy0 - Y0:sy1 - Y0, sx0 - X0:sx1 - X0] = rgb[sy0:sy1, sx0:sx1]
            f = cv2.resize(person(crop), (side, side))
            alpha = np.zeros((H, W), np.float32)
            alpha[sy0:sy1, sx0:sx1] = f[sy0 - Y0:sy1 - Y0, sx0 - X0:sx1 - X0]
        # edge refinement at half size with the frame as guide, then back to full size
        h2, w2 = H // 2, W // 2
        g = cv2.resize(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), (w2, h2)).astype(np.float32) / 255
        p = cv2.resize(alpha.astype(np.float32), (w2, h2))
        q = np.clip(guided(g, p), 0, 1)
        q = np.clip((q - 0.15) / 0.7, 0, 1)            # firm the core, keep a soft edge
        q = cv2.resize(q, (W, H), interpolation=cv2.INTER_LINEAR)
        if prev is not None:
            q = 0.65 * q + 0.35 * prev                  # temporal smoothing against flicker
        prev = q
        ff.stdin.write((q * 255).astype(np.uint8).tobytes()); n += 1
    ff.stdin.close(); ff.wait()
    print(f'{n} frames -> {a.out}')

if __name__ == '__main__':
    main()
