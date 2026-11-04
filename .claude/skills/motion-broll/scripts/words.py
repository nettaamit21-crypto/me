"""SRT -> estimated word timestamps (spreads each cue across its characters; ~0.2s accuracy).
If faster-whisper is installed, prefer real word timestamps from the audio.
usage: python3 words.py transcript.srt > words.txt"""
import sys, re
BIDI = re.compile('[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]')
def ts(x):
    h,m,r=x.strip().split(':'); s,ms=r.replace('.',',').split(','); return int(h)*3600+int(m)*60+int(s)+int(ms)/1000
txt = BIDI.sub('', open(sys.argv[1],encoding='utf-8-sig').read().replace('\r\n','\n').replace('\r','\n'))
for blk in re.split(r'\n\s*\n', txt.strip()):
    L=blk.strip().split('\n')
    if len(L)<3 or '-->' not in L[1]: continue
    a,b=[ts(x) for x in L[1].split('-->')]; words=re.sub(r'<[^>]+>','',' '.join(L[2:])).split(); n=sum(len(w)+1 for w in words); c=0
    out=[]; c=0
    for w in words: out.append(f'{a+(b-a)*c/n:.2f}:{w}'); c+=len(w)+1
    print(' '.join(out))
