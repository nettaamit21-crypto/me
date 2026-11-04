"""Word-level transcript of a video -> words.json  [{"w": "שלום", "s": 1.02, "e": 1.38, "p": 0.97}, ...]

usage: python3 transcribe.py <video> <out/words.json> [--srt transcript.srt] [--model NAME] [--lang he]

With --srt, word times are estimated from the SRT cues (about ±0.2s). Without it, faster-whisper
transcribes the audio with real word timestamps. Models are tried in order until one loads:
  --model, then for --lang he: ivrit-ai/whisper-large-v3-turbo-ct2 (best for Hebrew), large-v3-turbo, medium;
  for other languages: large-v3-turbo, medium (the ivrit-ai model translates non-Hebrew speech into Hebrew).
  Mixed Hebrew/English speech: use --lang he; English terms come out in Hebrew letters, fix them with captions --fix.
Models download from huggingface.co, which the environment's network policy must allow.
"""
import argparse, re, subprocess, sys, tempfile, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import save

BIDI = re.compile('[‎‏‪-‮⁦-⁩﻿]')

def from_srt(path):
    def ts(x):
        h, m, r = x.strip().split(':'); s, ms = r.replace('.', ',').split(','); return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    txt = BIDI.sub('', open(path, encoding='utf-8-sig').read().replace('\r\n', '\n').replace('\r', '\n'))
    out = []
    for blk in re.split(r'\n\s*\n', txt.strip()):
        L = blk.strip().split('\n')
        k = next((i for i, l in enumerate(L) if '-->' in l), None)
        if k is None: continue
        a, b = [ts(x.split()[0] if x.split() else x) for x in L[k].split('-->')]
        words = re.sub(r'<[^>]+>|\{[^}]+\}', '', ' '.join(L[k + 1:])).split()
        n = sum(len(w) + 1 for w in words) or 1; c = 0
        for w in words:
            s = a + (b - a) * c / n; c += len(w) + 1; e = a + (b - a) * (c - 1) / n
            out.append({'w': w, 's': round(s, 3), 'e': round(e, 3), 'p': None})
    return out

def from_audio(video, model_name, lang):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit('faster-whisper is not installed: pip install faster-whisper')
    wav = pathlib.Path(tempfile.mkdtemp()) / 'a.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-vn', '-ac', '1', '-ar', '16000', str(wav)], check=True)
    tried = []
    # The ivrit-ai model is fine-tuned on Hebrew and translates other languages into Hebrew: use it for Hebrew only.
    order = ['ivrit-ai/whisper-large-v3-turbo-ct2', 'large-v3-turbo', 'medium'] if lang == 'he' else ['large-v3-turbo', 'medium']
    for name in [model_name] + order:
        if not name or name in tried: continue
        tried.append(name)
        try:
            model = WhisperModel(name, device='cpu', compute_type='int8'); break
        except Exception as e:
            print(f'model {name} unavailable: {str(e)[:160]}', file=sys.stderr)
    else:
        raise SystemExit('No Whisper model could be loaded. Allow huggingface.co in the environment network settings, or pass --srt.')
    print(f'transcribing with {name}', file=sys.stderr)
    segs, info = model.transcribe(str(wav), language=lang, word_timestamps=True, vad_filter=True,
                                  vad_parameters={'min_silence_duration_ms': 300}, condition_on_previous_text=False)
    out = []
    for seg in segs:
        for w in seg.words or []:
            t = w.word.strip()
            if not t: continue
            if out and re.match(r"^['\u05F3\u05F4\"]", t):  # Whisper splits Hebrew geresh words: פיצ + 'ר -> פיצ'ר
                out[-1]['w'] += t; out[-1]['e'] = round(w.end, 3); continue
            out.append({'w': t, 's': round(w.start, 3), 'e': round(w.end, 3), 'p': round(w.probability, 3)})
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('out')
    ap.add_argument('--srt'); ap.add_argument('--model'); ap.add_argument('--lang', default='he')
    a = ap.parse_args()
    words = from_srt(a.srt) if a.srt else from_audio(a.video, a.model, a.lang)
    save(a.out, words)
    print(f'{len(words)} words -> {a.out}')
