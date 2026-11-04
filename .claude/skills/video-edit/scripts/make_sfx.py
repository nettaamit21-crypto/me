"""Generate a small set of subtle sound effects with ffmpeg (no downloads): whoosh, swoosh-short, pop, click, riser, hit.

usage: python3 make_sfx.py <outdir>
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import run

SFX = {
    # band-passed pink noise with a swell: transitions, cutaways in
    'whoosh': ("anoisesrc=d=0.6:c=pink:a=0.6", "highpass=f=300,lowpass=f=4500,afade=t=in:d=0.35:curve=exp,afade=t=out:st=0.35:d=0.25,volume=2"),
    'swoosh-short': ("anoisesrc=d=0.25:c=pink:a=0.6", "highpass=f=900,lowpass=f=7000,afade=t=in:d=0.12:curve=exp,afade=t=out:st=0.12:d=0.13,volume=2"),
    # falling sine blip: text pops, captions, icons
    'pop': ("aevalsrc='0.6*sin(2*PI*(900*t-2600*t*t))*exp(-28*t)':d=0.12:s=48000", "highpass=f=200"),
    # very short tick: cursor clicks in motion graphics
    'click': ("aevalsrc='0.7*sin(2*PI*2200*t)*exp(-180*t)+0.3*(random(0)-0.5)*exp(-250*t)':d=0.05:s=48000", "highpass=f=800"),
    # rising filtered noise: before a reveal or chapter change
    'riser': ("anoisesrc=d=1.5:c=white:a=0.35", "bandpass=f=2000:w=1.2:t=o,afade=t=in:d=1.4:curve=qsin,afade=t=out:st=1.42:d=0.08"),
    # low thump: emphasis on a key word or number
    'hit': ("aevalsrc='0.9*sin(2*PI*(95*t-60*t*t))*exp(-9*t)':d=0.45:s=48000", "lowpass=f=900"),
}
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'motion/inputs/sfx'); out.mkdir(parents=True, exist_ok=True)
for name, (src, af) in SFX.items():
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', src, '-af', af + ',aformat=sample_rates=48000:channel_layouts=stereo', str(out / f'{name}.wav')])
print('sfx:', ', '.join(SFX), '->', out)
