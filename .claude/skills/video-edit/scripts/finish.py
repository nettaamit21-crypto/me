"""Finish the edit: B-roll over the cut, captions, sound effects, music with ducking, loudness.

usage: python3 finish.py finish.json

finish.json (all times on the rough-cut timeline):
{
  "video": "motion/out/rough.mp4",
  "out": "motion/out/final.mp4",
  "broll": [
    {"file": "motion/out/01-intro_0m03s20.mp4", "at": 3.2, "mode": "cutaway", "fade": 0.12},
    {"file": "motion/out/02-panel_0m15s00.mov", "at": 15.0, "dur": 6.0, "mode": "overlay", "x": 0, "y": 0},
    {"file": "motion/inputs/screen.mp4", "at": 22.0, "dur": 4.0, "src_in": 10.0, "mode": "cutaway", "transition": "zoom"}
  ],
  "captions": "motion/work/captions.ass",
  "fontsdir": ".claude/skills/hebrew-captions/fonts",
  "sfx": [{"file": "sfx/whoosh.wav", "at": 3.1, "gain_db": -10}],
  "music": {"file": "motion/inputs/music.mp3", "gain_db": -20, "duck": true, "fade_in": 1.0, "fade_out": 2.5},
  "loudness": -14
}
broll mode: cutaway (fills the frame; fit cover, or contain over a blur when the aspect differs) | overlay (placed as-is at x,y; use alpha .mov panels) |
  pip (scaled by "scale", placed at x,y). transition: cut | fade (uses "fade" seconds) | zoom (enters 8% zoomed in and settles).
"""
import argparse, json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import run, probe, load

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('finish'); a = ap.parse_args()
    f = load(a.finish); base = f['video']; info = probe(base); W, H, T = info['W'], info['H'], info['duration']
    ins = ['-i', base]; fc = []; v = '[0:v]'; n = 1
    for k, b in enumerate(f.get('broll', [])):
        bi = probe(b['file']); dur = float(b.get('dur') or (bi['duration'] - b.get('src_in', 0)))
        dur = min(dur, T - b['at'])
        if dur <= 0: continue
        ins += (['-ss', str(b['src_in'])] if b.get('src_in') else []) + ['-i', b['file']]
        mode = b.get('mode', 'cutaway'); fade = float(b.get('fade', 0.12 if b.get('transition', 'fade') == 'fade' else 0))
        chain = f'[{n}:v]trim=duration={dur:.4f},setpts=PTS-STARTPTS'
        if mode == 'cutaway':
            fit = b.get('fit') or ('cover' if abs(bi['W'] / bi['H'] - W / H) < 0.15 else 'contain')
            if fit == 'cover':
                chain += f',scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}'
            else:  # whole clip over a blurred, darkened copy of itself (e.g. 16:9 b-roll in a 9:16 video)
                print(f"note: {b['file']} is {bi['W']}x{bi['H']} in a {W}x{H} video; letterboxed over blur. "
                      f"Render motion-broll clips at {W}x{H} to fill the frame.")
                chain += (f',split[bg{k}][fg{k}];[bg{k}]scale={W // 8}:{H // 8}:force_original_aspect_ratio=increase,crop={W // 8}:{H // 8},'
                          f'boxblur=6:2,scale={W}:{H},eq=brightness=-0.12[bgb{k}];[fg{k}]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs{k}];'
                          f'[bgb{k}][fgs{k}]overlay=(W-w)/2:(H-h)/2')
        elif mode == 'pip':
            chain += f",scale=iw*{b.get('scale', 0.5)}:-2"
        chain += f",fps={info['fps_str']},format=yuva420p"
        if b.get('transition') == 'zoom':
            # enters 8% zoomed in and settles to 1.0 over 0.35s; the output size stays fixed (scale up, then crop)
            if mode == 'cutaway': bw, bh = W, H
            else:
                sc = float(b.get('scale', 0.5)) if mode == 'pip' else 1.0
                bw, bh = int(bi['W'] * sc) // 2 * 2, int(bi['H'] * sc) // 2 * 2
            Z = "(1+0.08*pow(1-min(t/0.35,1),3))"
            chain += (f",scale=w='trunc({bw}*{Z}/2)*2':h='trunc({bh}*{Z}/2)*2':eval=frame,"
                      f"crop={bw}:{bh}:x='({bw}*{Z}-{bw})/2':y='({bh}*{Z}-{bh})/2'")
        if fade > 0:
            chain += f',fade=t=in:st=0:d={fade}:alpha=1,fade=t=out:st={max(0, dur - fade):.4f}:d={fade}:alpha=1'
        chain += f",setpts=PTS+{b['at']:.4f}/TB[b{k}]"
        x = b.get('x', '(W-w)/2'); y = b.get('y', '(H-h)/2')
        fc.append(chain)
        fc.append(f"{v}[b{k}]overlay=x={x}:y={y}:eof_action=pass:enable='between(t,{b['at']:.4f},{b['at'] + dur:.4f})'[v{k}]")
        v = f'[v{k}]'; n += 1
    if f.get('captions'):
        cap = str(pathlib.Path(f['captions']).resolve()).replace(':', r'\:').replace("'", r"\'")
        fd = str(pathlib.Path(f.get('fontsdir', '.claude/skills/hebrew-captions/fonts')).resolve())
        fc.append(f"{v}subtitles='{cap}':fontsdir='{fd}'[vc]"); v = '[vc]'
    if v == '[0:v]':
        fc.append('[0:v]null[vn]'); v = '[vn]'

    # audio: voice + sfx + ducked music, then loudness
    # gentle voice compression evens out phone-mic peaks, so loudness can reach the target without clipping
    comp = ',acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=2' if f.get('compress', True) else ''
    mix = [f'[0:a]aresample=48000{comp},asplit=2[voice][side]' if f.get('music', {}).get('duck', True) and f.get('music') else f'[0:a]aresample=48000{comp}[voice]']
    parts = ['[voice]']
    for k, s in enumerate(f.get('sfx', [])):
        ins += ['-i', s['file']]
        ms = int(s['at'] * 1000)
        mix.append(f"[{n}:a]aresample=48000,volume={s.get('gain_db', -10)}dB,adelay={ms}|{ms}[s{k}]"); parts.append(f'[s{k}]'); n += 1
    m = f.get('music')
    if m:
        ins += ['-stream_loop', '-1', '-i', m['file']]
        fo = m.get('fade_out', 2.5)
        chain = (f"[{n}:a]aresample=48000,atrim=0:{T:.3f},volume={m.get('gain_db', -20)}dB,"
                 f"afade=t=in:d={m.get('fade_in', 1.0)},afade=t=out:st={max(0, T - fo):.3f}:d={fo}")
        if m.get('duck', True):
            mix.append(chain + '[mus0]')
            mix.append('[mus0][side]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[mus]')
        else:
            mix.append(chain + '[mus]')
        parts.append('[mus]'); n += 1
    mixed = f"{''.join(parts)}amix=inputs={len(parts)}:normalize=0:duration=first"
    target = f.get('loudness', -14)
    # two-pass loudnorm: measure the mix, then normalise linearly to the exact target
    r = run(['ffmpeg', '-hide_banner', '-y', *ins, '-filter_complex', ';'.join(mix + [mixed + f',loudnorm=I={target}:TP=-1.0:LRA=11:print_format=json[aout]']),
             '-map', '[aout]', '-t', f'{T:.4f}', '-f', 'null', '-'])
    ms = json.loads(r.stderr[r.stderr.rindex('{'):r.stderr.rindex('}') + 1])
    ln = (f"loudnorm=I={target}:TP=-1.0:LRA=11:measured_I={ms['input_i']}:measured_TP={ms['input_tp']}:"
          f"measured_LRA={ms['input_lra']}:measured_thresh={ms['input_thresh']}:offset={ms['target_offset']}:linear=true")
    graph = ';'.join(fc + mix + [mixed + f',{ln},aresample=48000[aout]'])
    run(['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', graph, '-map', v, '-map', '[aout]', '-t', f'{T:.4f}',
         '-c:v', 'libx264', '-preset', f.get('preset', 'medium'), '-crf', str(f.get('crf', 17)), '-pix_fmt', 'yuv420p',
         '-r', info['fps_str'], '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', f['out']])
    print(f"final: {len(f.get('broll', []))} b-roll, {'captions, ' if f.get('captions') else ''}{len(f.get('sfx', []))} sfx"
          f"{', music' if m else ''} -> {f['out']}")

if __name__ == '__main__':
    main()
