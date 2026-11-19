#!/usr/bin/env python3
"""Bangun sprites/poses/<Nama>/*.png + poses.json dari sheet yang sudah dipetakan."""
import json, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(__file__))
import cut_sheets as C

FILES = json.load(open('/tmp/work/files.json'))
OUT = '/home/claude/ruangrealita/sprites/poses'
FRONT_H = 600  # tinggi pose 'front' dalam piksel di sprite akhir

ROW1 = ['front', 'point', 'explain', 'hips', 'crossed', 'wave']
ROW2 = ['scratch', 'facepalm', 'shrug', 'shock', 'laugh', 'angry']
ROW3 = ['side_stand', 'side_walkA', 'side_walkB', 'side_talk', 'side_point', 'side_jog']
ROW4 = ['tq_left', 'tq_right', 'sit_front', 'sit_side', 'back', 'thumb']
MOTOR = ['motor_front', 'motor_R', 'motor_L', 'motor_tq_front', 'motor_tq_rear', 'motor_back']
# motor_R = melaju ke kanan (roda depan di kanan), motor_L = ke kiri
# indeks referensi tinggi berdiri per baris
REF = {1: 0, 2: 2, 3: 0, 4: 4}

# karakter -> (indeks sheet baris1..4, opsi)
CHARS = {
    'Budi':  dict(r1=18, r2=20, r3=17, r4=19),
    'Udin':  dict(r1=16, r2=13, r3=2,  r4=9, ground3=True),
    'Joko':  dict(r1=8,  r2=1,  r3=12, r4=37, white1=True, ground3=True),
    'Agus':  dict(r1=40, r2=39, r3=29, r4=28),
    'Rizky': dict(r1=5,  r2=4,  r3=3,  r4=15),
    'Siti':  dict(r1=6,  r2=7,  r3=10, r4=14),
    'Dewi':  dict(r1=22, r2=34, r3=26, r4=23),
    'Maya':  dict(r1=36, r2=30, r3=25, r4=21),
    'Rina':  dict(r1=35, r2=33, r3=24, r4=31),
    'Nina':  dict(r1=27, r2=38, r3=53, r4=50),
}
MOTORS = {  # hanya sheet yang bersih; sisanya dibuang (terpotong): Udin 11, Dewi 46, Agus 47, Joko 49, Nina 55, Budi 56
  # sheet motor + penumpang
    'Rina': 32, 'Rizky': 43, 'Siti': 52, 'Maya': 54,
}
EXTRA = {  # nama: (indeks, nama pose, opsi)
    'Pedagang_A': (51, ['stall', 'walkA', 'walkB', 'talk', 'open', 'angry'], {}),
    'Pedagang_B': (44, ['stall', 'walkA', 'walkB', 'talk', 'open', 'angry'], dict(ground=True)),
    'Fig_Nenek':  (45, ['stand', 'walk', 'talk', 'smile', 'wave', 'bags'], {}),
    'Fig_Hoodie': (48, ['stand', 'walk', 'talk', 'laugh', 'wave', 'phone'], {}),
    'Fig_Parkir': (58, ['stand', 'stop', 'whistle', 'talk', 'hips', 'baton'], {}),
    'Fig_Anak':   (57, ['stand', 'run', 'wave', 'laugh', 'icecream', 'kick'], dict(ghost=True)),
    'Fig_Peci':   (41, ['stand', 'walkA', 'walkB'], {}),
    'Fig_Hijab':  (42, ['stand', 'walkA', 'walkB'], {}),
}
MOTOR_GHOST = {54}
MOTOR_GROUND = {11, 43, 54}

def anchor_x(sp):
    h = sp.shape[0]
    low = sp[int(h * 0.62):, :, 3] > 8
    xs = np.where(low.any(0))[0]
    return int((xs.min() + xs.max()) / 2) if len(xs) else sp.shape[1] // 2

def run_sheet(idx, **kw):
    expect = kw.pop('expect', 6)
    sp, _ = C.cut(FILES[idx], gap=7, expect=expect, **kw)
    return sp

def save(name, poses, scale_by=None):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    meta = {}
    for pn, (sp, s) in poses.items():
        h, w = sp.shape[:2]
        nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
        im = cv2.resize(sp, (nw, nh), interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(d, pn + '.png'), cv2.cvtColor(im, cv2.COLOR_RGBA2BGRA))
        meta[pn] = dict(w=nw, h=nh, ax=int(round(anchor_x(sp) * s)))
    json.dump(meta, open(os.path.join(d, 'poses.json'), 'w'), indent=1)
    return meta

def build_char(name, spec):
    rows = {}
    for r in (1, 2, 3, 4):
        kw = {}
        if r == 1 and spec.get('white1'):
            kw['white'] = True
        if r == 3 and spec.get('ground3'):
            kw['ground'] = True
        idx = spec['r%d' % r]
        if name == 'Maya' and r == 1:
            kw['tworows'] = True
            sp = run_sheet(idx, expect=10, **kw)
            # atas: front point shrug hips wave | bawah: front speak hips crossed wave
            rows[1] = [sp[0], sp[1], sp[2], sp[3], sp[8], sp[4]]
        else:
            rows[r] = run_sheet(idx, **kw)
    ref1 = rows[1][REF[1]].shape[0]
    out = {}
    for r, names in ((1, ROW1), (2, ROW2), (3, ROW3), (4, ROW4)):
        sps = rows[r]
        if len(sps) != 6:
            print('  PERINGATAN', name, 'baris', r, 'jumlah', len(sps))
        s_row = ref1 / sps[min(REF[r], len(sps) - 1)].shape[0]
        for pn, sp in zip(names, sps):
            out[pn] = (sp, s_row * FRONT_H / ref1)
    return out

if __name__ == '__main__':
    only = sys.argv[1:]
    ref_scale = {}
    for name, spec in CHARS.items():
        if only and name not in only:
            continue
        poses = build_char(name, spec)
        meta = save(name, poses)
        ref_scale[name] = poses['front'][0].shape[0]
        print(name, len(meta), 'pose')
    for name, idx in MOTORS.items():
        if only and name not in only:
            continue
        kw = dict(ghost=idx in MOTOR_GHOST, ground=idx in MOTOR_GROUND)
        if idx == 32:      # Rina: 2 baris, kiri-bawah gabung (samping + belakang)
            sps, _ = C.cut(FILES[idx], gap=7, tworows=True)
            top = sps[:3]; bot = sps[3:]
            sp_r, sp_l, sp_front = top
            parts = C.split_one(bot[0])
            sps = [sp_front, sp_r, sp_l, bot[1], bot[2], parts[-1]]
        elif idx == 52:    # Siti: 5 tampilan, satu sisi (ke kiri)
            sps, _, _ = C.motor_cut(FILES[idx], n=5)
            front, tqf, side, tqr, back = sps
            sps = [front, cv2.flip(side, 1), side, tqf, tqr, back]
        else:
            sps, _, _ = C.motor_cut(FILES[idx], **kw)
        s = FRONT_H / max(x.shape[0] for x in sps) * 0.95
        poses = {pn: (sp, s) for pn, sp in zip(MOTOR, sps)}
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        meta = {}
        for pn, (sp, sc) in poses.items():
            h, w = sp.shape[:2]
            nw, nh = int(round(w * sc)), int(round(h * sc))
            im = cv2.resize(sp, (nw, nh), interpolation=cv2.INTER_AREA)
            cv2.imwrite(os.path.join(d, pn + '.png'), cv2.cvtColor(im, cv2.COLOR_RGBA2BGRA))
            meta[pn] = dict(w=nw, h=nh, ax=nw // 2)
        pj = os.path.join(d, 'poses.json')
        old = json.load(open(pj)) if os.path.exists(pj) else {}
        old.update(meta)
        json.dump(old, open(pj, 'w'), indent=1)
        print(name, 'motor', len(meta))
    for name, (idx, pnames, kw) in EXTRA.items():
        if only and name not in only:
            continue
        sps = run_sheet(idx, expect=len(pnames), **kw)
        if len(sps) != len(pnames):
            print('  PERINGATAN', name, len(sps))
        s = FRONT_H / max(x.shape[0] for x in sps)
        meta = save(name, {pn: (sp, s) for pn, sp in zip(pnames, sps)})
        print(name, len(meta))
