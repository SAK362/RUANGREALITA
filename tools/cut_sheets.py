#!/usr/bin/env python3
"""Potong pose sheet (latar hijau / putih) menjadi sprite PNG transparan per pose.
Dipakai: python3 -I tools/cut_sheets.py  (baca /tmp/work/files.json + peta di MAP)
"""
import json, sys, os
import numpy as np, cv2
from scipy import ndimage as ndi

def load(path):
    im = cv2.imread(path, cv2.IMREAD_COLOR)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)

def bg_mask(rgb, white=False):
    r, g, b = [rgb[..., i].astype(np.int16) for i in range(3)]
    if white:
        greenish = (r > 235) & (g > 235) & (b > 235)
    else:
        greenish = (g - np.maximum(r, b) > 55) & (g > 110)
    lab, n = ndi.label(greenish)
    border = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    border = border[border > 0]
    bg = np.isin(lab, border)
    if not white:
        pure = (g > 200) & (r < 90) & (b < 90)
        bg |= pure
    return bg

def to_rgba(rgb, bg, white=False):
    """alpha lembut + buang spill hijau di tepi."""
    h, w = bg.shape
    fg = (~bg).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    alpha = fg.astype(np.float32)
    # tepi: 2px dari bg
    dist = cv2.distanceTransform(fg, cv2.DIST_L2, 3)
    edge = (dist <= 2.5) & (fg > 0)
    r, g, b = [rgb[..., i].astype(np.float32) for i in range(3)]
    if not white:
        spill = np.clip(g - np.maximum(r, b), 0, None)
        t = np.clip((spill - 25) / 110.0, 0, 1)
        alpha = np.where(edge, np.minimum(alpha, 1 - t), alpha)
        gl = np.minimum(g, np.maximum(r, b) + 12)
        g = np.where(edge, gl, g)
    a = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
    a = cv2.GaussianBlur(a, (3, 3), 0) * (fg > 0)
    out = np.dstack([r, g, b]).clip(0, 255).astype(np.uint8)
    return np.dstack([out, a.astype(np.uint8)])

def components(bg, gap=22, drop_top=False, keep_rows=1):
    fg = (~bg).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    d = cv2.dilate(fg, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (gap, gap)))
    lab, n = ndi.label(d)
    objs = ndi.find_objects(lab)
    comps = []
    for i, sl in enumerate(objs, 1):
        m = (lab[sl] == i) & (fg[sl] > 0)
        area = int(m.sum())
        if area < 400:
            continue
        y0, y1 = sl[0].start, sl[0].stop
        x0, x1 = sl[1].start, sl[1].stop
        comps.append(dict(id=i, x0=x0, x1=x1, y0=y0, y1=y1, area=area))
    return comps, lab

def split_two_rows(comps):
    """urut: baris atas lalu baris bawah, tiap baris kiri->kanan."""
    if not comps:
        return []
    ys = np.array([(c['y0'] + c['y1']) / 2 for c in comps])
    hs = np.array([c['y1'] - c['y0'] for c in comps])
    thr = (ys.min() + ys.max()) / 2
    if ys.max() - ys.min() < 0.5 * hs.max():
        return sorted(comps, key=lambda c: c['x0'])
    top = sorted([c for c, y in zip(comps, ys) if y < thr], key=lambda c: c['x0'])
    bot = sorted([c for c, y in zip(comps, ys) if y >= thr], key=lambda c: c['x0'])
    return top + bot

def remove_ground_line(bg):
    fg = (~bg).astype(np.uint8)
    h, w = fg.shape
    rowsum = fg.sum(1)
    cand = np.where(rowsum > 0.55 * w)[0]
    if len(cand) == 0:
        return bg
    # run vertikal tiap kolom
    out = bg.copy()
    lab, n = ndi.label(fg[:, :, None][..., 0], structure=np.array([[0,1,0],[0,1,0],[0,1,0]]))
    # tebal vertikal per piksel
    thick = np.zeros_like(fg, dtype=np.int32)
    for x in range(w):
        col = fg[:, x]
        if not col.any():
            continue
        d = np.diff(np.concatenate([[0], col, [0]]))
        st = np.where(d == 1)[0]; en = np.where(d == -1)[0]
        for a, b in zip(st, en):
            thick[a:b, x] = b - a
    band = np.zeros_like(fg, dtype=bool)
    y0, y1 = cand.min() - 6, cand.max() + 6
    band[max(y0, 0):y1, :] = True
    line = band & (fg > 0) & (thick <= 11)
    out |= line
    return out

def cut(path, white=False, gap=22, ghost=False, minh=0.35, tworows=False, ground=False, expect=None):
    rgb = load(path)
    bg = bg_mask(rgb, white)
    if ground:
        bg = remove_ground_line(bg)
    rgba = to_rgba(rgb, bg, white)
    comps, lab = components(bg, gap)
    if not comps:
        return [], rgba
    maxh = max(c['y1'] - c['y0'] for c in comps)
    big = [c for c in comps if (c['y1'] - c['y0']) >= minh * maxh]
    small = [c for c in comps if c not in big]
    maxbot = max(c['y1'] for c in big)
    if ghost:  # buang bayangan buram di atas
        big = [c for c in big if c['y1'] > 0.55 * maxbot]
    # kecil: tempel (bola, tas) bila di dalam rentang vertikal figur terdekat, buang label teks di bawah
    for s in small:
        cx = (s['x0'] + s['x1']) / 2
        cy = (s['y0'] + s['y1']) / 2
        best = None
        for b in big:
            if b['x0'] - 140 <= cx <= b['x1'] + 140 and b['y0'] <= cy <= b['y1'] - 20:
                best = b
                break
        if best:
            best['x0'] = min(best['x0'], s['x0']); best['x1'] = max(best['x1'], s['x1'])
            best['y0'] = min(best['y0'], s['y0']); best['y1'] = max(best['y1'], s['y1'])
            best.setdefault('extra', []).append(s['id'])
    ordered = split_two_rows(big) if tworows else sorted(big, key=lambda c: c['x0'])
    sprites = []
    for c in ordered:
        ids = [c['id']] + c.get('extra', [])
        sl = (slice(c['y0'], c['y1']), slice(c['x0'], c['x1']))
        mask = np.isin(lab[sl], ids)
        # jaga semua piksel fg dalam bbox milik komponen (dilasi); pakai bbox saja + mask dilasi
        mk = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
        crop = rgba[sl].copy()
        crop[..., 3] = np.where(mk, crop[..., 3], 0)
        ys, xs = np.where(crop[..., 3] > 8)
        if len(ys) == 0:
            continue
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = crop[y0:y1, x0:x1]
        sprites.append(crop)
    if expect and len(sprites) < expect:
        sprites = split_to(sprites, expect)
    return sprites, rgba

def split_to(sprites, n):
    while len(sprites) < n:
        i = int(np.argmax([s.shape[1] for s in sprites]))
        s = sprites.pop(i)
        parts = split_one(s)
        sprites[i:i] = parts
    return sprites

def split_one(s):
    a = (s[..., 3] > 8).astype(np.float32).sum(0)
    a = ndi.uniform_filter1d(a, 25)
    w = len(a)
    lo, hi = int(w * 0.25), int(w * 0.75)
    x = lo + int(np.argmin(a[lo:hi]))
    parts = []
    for part in (s[:, :x], s[:, x:]):
        ys, xs = np.where(part[..., 3] > 8)
        if len(ys):
            parts.append(part[ys.min():ys.max()+1, xs.min():xs.max()+1])
    return parts

if __name__ == '__main__':
    p = sys.argv[1]
    sp, _ = cut(p, white='--white' in sys.argv, ghost='--ghost' in sys.argv, tworows='--two' in sys.argv)
    print(len(sp), [s.shape[:2] for s in sp])


def motor_cut(path, n=6, ground=False, ghost=False):
    """Sheet motor: tampilan saling menempel. Potong di lembah kolom di antara pusat helm."""
    rgb = load(path)
    bg = bg_mask(rgb)
    if ground:
        bg = remove_ground_line(bg)
    rgba = to_rgba(rgb, bg)
    fg = (~bg).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    comps, lab = components(bg, 7)
    big = [c for c in comps if (c['y1'] - c['y0']) > 120]
    if ghost:
        mb = max(c['y1'] for c in big)
        big = [c for c in big if c['y1'] > 0.55 * mb]
    ymin = min(c['y0'] for c in big); ymax = max(c['y1'] for c in big)
    # buang label teks & bayangan buram: batasi baris
    keep = np.zeros_like(fg)
    for c in big:
        keep[c['y0']:c['y1'], c['x0']:c['x1']] = fg[c['y0']:c['y1'], c['x0']:c['x1']]
    H = ymax - ymin
    top = keep[ymin:ymin + int(H * 0.30)]
    dd = cv2.dilate(top, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (45, 45)))
    l2, k = ndi.label(dd)
    cents = []
    for i in range(1, k + 1):
        ys, xs = np.where((l2 == i) & (top > 0))
        if len(xs) > 800:
            cents.append((xs.min(), xs.max(), xs.mean()))
    cents.sort(key=lambda t: t[2])
    prof = ndi.uniform_filter1d(keep[ymin:ymax].sum(0).astype(np.float32), 31)
    cuts = []
    if len(cents) == n:
        for a, b in zip(cents[:-1], cents[1:]):
            lo, hi = int(a[1]), int(b[0])
            if hi - lo < 10:
                lo, hi = int(a[2]), int(b[2])
            lo, hi = min(lo, hi), max(lo, hi)
            cuts.append(lo + int(np.argmin(prof[lo:hi + 1])))
    else:
        # cadangan: bagi rata
        xs = np.where(keep.any(0))[0]
        x0, x1 = xs.min(), xs.max()
        for j in range(1, n):
            ideal = x0 + (x1 - x0) * j // n
            lo, hi = ideal - 120, ideal + 120
            cuts.append(lo + int(np.argmin(prof[lo:hi])))
    edges = [0] + cuts + [keep.shape[1]]
    sprites = []
    for a, b in zip(edges[:-1], edges[1:]):
        cell = np.zeros_like(keep)
        cell[:, a:b] = keep[:, a:b]
        dl = cv2.dilate(cell, np.ones((5, 5), np.uint8))
        l3, m = ndi.label(dl)
        areas = ndi.sum(cell, l3, range(1, m + 1))
        if m == 0:
            continue
        mx = max(areas)
        ids = [i + 1 for i, ar in enumerate(areas) if ar >= 0.12 * mx]
        mask = np.isin(l3, ids)
        crop = rgba.copy()
        crop[..., 3] = np.where(mask, crop[..., 3], 0)
        ys, xs = np.where(crop[..., 3] > 8)
        sprites.append(crop[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    return sprites, cuts, cents
