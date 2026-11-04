"""Contact sheet of stills from a video at given times, labelled, to check an edit.

usage: python3 sheet.py <video> <out.png> t1 t2 t3 ...   (or --every 5 for a frame every 5 s)
"""
import sys, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import run, probe, fmt

video, out, *rest = sys.argv[1:]
info = probe(video)
if rest and rest[0] == '--every':
    step = float(rest[1]); ts = [round(i * step + 0.05, 2) for i in range(int(info['duration'] // step) + 1)]
else:
    ts = [float(t) for t in rest]
tmp = pathlib.Path(tempfile.mkdtemp()); files = []
w = 360 if info['H'] > info['W'] else 480
for i, t in enumerate(ts):
    f = tmp / f'{i:03d}.png'
    run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', video, '-frames:v', '1', '-vf',
         f"scale={w}:-2,drawtext=text='{fmt(t).replace(':', chr(92) + ':')}':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=5", str(f)])
    files.append(f)
cols = min(4, len(files)); rows = (len(files) + cols - 1) // cols
ins = sum((['-i', str(f)] for f in files), [])
pads = ''.join(f'[{i}:v]' for i in range(len(files)))
graph = pads + f'xstack=inputs={len(files)}:layout=' + '|'.join(
    f"{'+'.join(['w0'] * (i % cols)) or '0'}_{'+'.join(['h0'] * (i // cols)) or '0'}" for i in range(len(files))) + ':fill=black'
run(['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', graph if len(files) > 1 else 'null', '-frames:v', '1', out])
print(f'{len(files)} stills -> {out}')
