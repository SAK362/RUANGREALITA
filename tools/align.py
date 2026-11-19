#!/usr/bin/env python3
"""Whisper -> words.json. Pakai: python tools/align.py jobs/0001  [--model small]
Baca jobs/<id>/job.json + audio/beat_NN.wav. Tulis jobs/<id>/words.json:
{"beats":[ [[mulai,akhir],...satu pasang per kata naskah], ... ]}
Kata hasil Whisper dicocokkan ke kata naskah (difflib), sisanya diinterpolasi,
jadi jumlah pasangan selalu = jumlah kata di naskah."""
import sys, json, os, re, difflib

def norm(w): return re.sub(r'[^a-z0-9]', '', w.lower())

def align(script_words, heard, dur):
    """heard: [(kata, mulai, akhir)] dari Whisper. Return [[mulai, akhir]] per kata naskah."""
    n = len(script_words)
    a = [norm(w) for w in script_words]
    b = [norm(h[0]) for h in heard]
    out = [None] * n
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1): out[i1 + k] = [heard[j1 + k][1], heard[j1 + k][2]]
        elif tag == 'replace' and (i2 - i1) == (j2 - j1):
            for k in range(i2 - i1): out[i1 + k] = [heard[j1 + k][1], heard[j1 + k][2]]
    # isi yang kosong: bagi rata di antara tetangga yang diketahui
    known = [k for k in range(n) if out[k]]
    if not known:
        t0 = heard[0][1] if heard else 0.0; t1 = heard[-1][2] if heard else dur
        step = (t1 - t0) / max(n, 1)
        return [[round(t0 + k * step, 3), round(t0 + (k + .9) * step, 3)] for k in range(n)]
    i = 0
    while i < n:
        if out[i]: i += 1; continue
        j = i
        while j < n and not out[j]: j += 1
        lo = out[i - 1][1] if i > 0 else (heard[0][1] if heard else 0.0)
        hi = out[j][0] if j < n else (heard[-1][2] if heard else dur)
        hi = max(hi, lo + .05 * (j - i)); step = (hi - lo) / (j - i)
        for k in range(i, j): out[k] = [round(lo + (k - i) * step, 3), round(lo + (k - i + .9) * step, 3)]
        i = j
    # monoton + dalam durasi
    prev = 0.0
    for k in range(n):
        s, e = out[k]; s = max(s, prev); e = max(e, s + .04); out[k] = [round(min(s, dur), 3), round(min(e, dur), 3)]; prev = out[k][0]
    return out

def main():
    d = sys.argv[1]; model_name = sys.argv[sys.argv.index('--model') + 1] if '--model' in sys.argv else 'small'
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device='cpu', compute_type='int8')
    job = json.load(open(os.path.join(d, 'job.json')))
    res = []
    for i, b in enumerate(job['beats']):
        f = os.path.join(d, 'audio', f'beat_{i:02d}.wav')
        words = b['text'].split()
        if not os.path.exists(f): res.append(None); continue
        segs, info = model.transcribe(f, language='id', word_timestamps=True, vad_filter=False,
                                      initial_prompt=b['text'], beam_size=5)
        heard = [(w.word.strip(), w.start, w.end) for s in segs for w in (s.words or [])]
        res.append(align(words, heard, info.duration))
        print(f'beat {i}: {len(words)} kata, terdengar {len(heard)}')
    json.dump({'beats': res}, open(os.path.join(d, 'words.json'), 'w'))
    print('words.json ditulis')

if __name__ == '__main__': main()
