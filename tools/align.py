#!/usr/bin/env python3
"""Whisper -> beat_NN.wav + words.json.
Pakai: python tools/align.py jobs/0001 [--model small]

Mode A (hemat kuota TTS): jobs/<id>/speakers/<Nama>.wav = satu rekaman per karakter berisi
semua kalimatnya berurutan. Whisper memberi waktu tiap kata, kata dicocokkan ke naskah,
lalu rekaman dipotong jadi audio/beat_NN.wav per beat.
Mode B: audio/beat_NN.wav sudah ada (satu file per beat), hanya dihitung waktu katanya.

Hasil: jobs/<id>/words.json = {"beats":[ [[mulai,akhir],...satu pasang per kata], ... ]}
Waktu relatif terhadap awal beat_NN.wav. Jumlah pasangan selalu = jumlah kata naskah."""
import sys, json, os, re, difflib, subprocess

def norm(w): return re.sub(r'[^a-z0-9]', '', w.lower())

def align(script_words, heard, dur):
    """heard: [(kata, mulai, akhir)] dari Whisper. Return [[mulai, akhir]] per kata naskah."""
    n = len(script_words)
    a = [norm(w) for w in script_words]
    b = [norm(h[0]) for h in heard]
    out = [None] * n
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and (i2 - i1) == (j2 - j1)):
            for k in range(i2 - i1): out[i1 + k] = [heard[j1 + k][1], heard[j1 + k][2]]
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
    prev = 0.0
    for k in range(n):
        s, e = out[k]; s = max(s, prev); e = max(e, s + .04); out[k] = [round(min(s, dur), 3), round(min(e, dur), 3)]; prev = out[k][0]
    return out

def split_speaker(beats, speaker, heard, total):
    """Bagi rekaman satu karakter menjadi beat-beatnya.
    Return {indeks_beat: (mulai_potong, akhir_potong, [[mulai,akhir] relatif per kata])}"""
    idx = [i for i, b in enumerate(beats) if b['speaker'] == speaker]
    words, counts = [], []
    for i in idx:
        w = beats[i]['text'].split(); words += w; counts.append(len(w))
    times = align(words, heard, total)
    per, pos = [], 0
    for c in counts: per.append(times[pos:pos + c]); pos += c
    cuts = {}
    for k, i in enumerate(idx):
        w = per[k]; s0, e0 = w[0][0], w[-1][1]
        prev_end = per[k - 1][-1][1] if k > 0 else None
        next_start = per[k + 1][0][0] if k + 1 < len(idx) else None
        start = s0 - 0.12
        if prev_end is not None: start = max(start, (prev_end + s0) / 2)
        end = e0 + 0.30
        if next_start is not None: end = min(end, (e0 + next_start) / 2)
        start = max(0.0, start); end = min(total, max(end, start + 0.2))
        cuts[i] = (round(start, 3), round(end, 3), [[round(a - start, 3), round(b - start, 3)] for a, b in w])
    return cuts

def cut_audio(src, start, end, dst):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(start), '-t', str(round(end - start, 3)),
                    '-i', src, '-ac', '1', '-c:a', 'pcm_s16le', dst], check=True)

def transcribe(model, path, prompt):
    segs, info = model.transcribe(path, language='id', word_timestamps=True, vad_filter=False,
                                  initial_prompt=prompt, beam_size=5)
    return [(w.word.strip(), w.start, w.end) for s in segs for w in (s.words or [])], info.duration

def main():
    d = sys.argv[1]; model_name = sys.argv[sys.argv.index('--model') + 1] if '--model' in sys.argv else 'small'
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device='cpu', compute_type='int8')
    job = json.load(open(os.path.join(d, 'job.json'))); beats = job['beats']
    os.makedirs(os.path.join(d, 'audio'), exist_ok=True)
    res = [None] * len(beats)
    sp_dir = os.path.join(d, 'speakers')
    if os.path.isdir(sp_dir):
        for f in sorted(os.listdir(sp_dir)):
            if not f.endswith('.wav'): continue
            name = f[:-4]
            if not any(b['speaker'] == name for b in beats): continue
            heard, total = transcribe(model, os.path.join(sp_dir, f), ' '.join(b['text'] for b in beats if b['speaker'] == name))
            json.dump([[w, round(a, 2), round(b, 2)] for w, a, b in heard], open(os.path.join(d, f'heard_{name}.json'), 'w'), ensure_ascii=False)
            cuts = split_speaker(beats, name, heard, total)
            for i, (s, e, w) in cuts.items():
                cut_audio(os.path.join(sp_dir, f), s, e, os.path.join(d, 'audio', f'beat_{i:02d}.wav'))
                res[i] = w
            print(f'{name}: terdengar {len(heard)} kata, {len(cuts)} beat dipotong, durasi {total:.1f}s')
    for i, b in enumerate(beats):
        if res[i] is not None: continue
        f = os.path.join(d, 'audio', f'beat_{i:02d}.wav')
        if not os.path.exists(f): continue
        heard, dur = transcribe(model, f, b['text'])
        res[i] = align(b['text'].split(), heard, dur)
        print(f'beat {i}: {len(b["text"].split())} kata, terdengar {len(heard)}')
    json.dump({'beats': res}, open(os.path.join(d, 'words.json'), 'w'))
    print('words.json ditulis')

if __name__ == '__main__': main()
