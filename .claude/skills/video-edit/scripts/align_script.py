"""Put the exact script text onto transcribed word times: punctuation, capitals and spelling come from the
script, timings from the audio. Use it whenever the user has the script (AI avatars always do).

usage: python3 align_script.py words.json script.txt out.json
Words are matched in order (difflib); an equal-length replaced run is taken word for word, anything else keeps
the transcript word and is reported. Dashes count as a comma so captions break there.
"""
import json, re, sys, difflib
words_p, script_p, out_p = sys.argv[1:4]
norm = lambda t: re.sub(r"[^\w']", '', t.lower().replace('’', "'"))
text = open(script_p, encoding='utf-8-sig').read()
text = re.sub(r'\s*[—–]\s*|\s+-\s+', ', ', text)
script = [t.strip('"“”') for t in text.split() if norm(t)]
w = json.load(open(words_p, encoding='utf-8'))
sm = difflib.SequenceMatcher(a=[norm(x['w']) for x in w], b=[norm(t) for t in script], autojunk=False)
changed = unmatched = 0
for op, i1, i2, j1, j2 in sm.get_opcodes():
    if op == 'equal' or (op == 'replace' and i2 - i1 == j2 - j1):
        for k in range(i2 - i1):
            changed += w[i1 + k]['w'] != script[j1 + k]; w[i1 + k]['w'] = script[j1 + k]
    else:
        unmatched += max(i2 - i1, j2 - j1)
        print(f"{op}: transcript {[x['w'] for x in w[i1:i2]]} vs script {script[j1:j2]}", file=sys.stderr)
json.dump(w, open(out_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'{len(script)} script words, {len(w)} transcript words, {changed} corrected, {unmatched} unmatched, match {sm.ratio():.3f} -> {out_p}')
