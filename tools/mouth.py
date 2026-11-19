"""Deteksi posisi mulut di tiap sprite pose -> poses.json['pose']['mouth']=[cx,cy,w,h] (piksel sprite)."""
import json, os, sys, glob
import numpy as np, cv2
from scipy import ndimage as ndi

SKIP = ('back', 'motor_')

def detect(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None or im.shape[2] < 4:
        return None
    h, w = im.shape[:2]
    a = im[..., 3] > 128
    lum = cv2.cvtColor(im[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
    top = int(h * 0.30)
    dark = (lum < 110) & a
    dark[top:] = False
    bright = (lum > 200) & a
    lab, n = ndi.label(dark)
    cands = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        ar = len(xs)
        if ar < 12 or ar > 900:
            continue
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        m = np.zeros_like(dark); m[y0:y1 + 1, x0:x1 + 1] = lab[y0:y1 + 1, x0:x1 + 1] == i
        ring = cv2.dilate(m.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) & ~cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        if ring.sum() == 0 or (bright & ring).sum() / ring.sum() < 0.7:
            continue
        cands.append(dict(cx=xs.mean(), cy=ys.mean(), w=x1 - x0 + 1, h=y1 - y0 + 1, ar=ar))
    if len(cands) < 2:
        return None
    cands.sort(key=lambda c: c['cy'])
    mth = cands[-1]
    # mulut harus lebih rendah dari mata (kandidat lain) dengan jarak cukup
    if mth['cy'] - cands[-2]['cy'] < 6:
        return None
    return [round(mth['cx'], 1), round(mth['cy'], 1), int(mth['w']), int(mth['h'])]

if __name__ == '__main__':
    root = 'sprites/poses'
    names = sys.argv[1:] or sorted(os.listdir(root))
    for n in names:
        pj = os.path.join(root, n, 'poses.json')
        if not os.path.exists(pj):
            continue
        meta = json.load(open(pj))
        ok = 0
        for k in meta:
            meta[k].pop('mouth', None)
            if k.startswith(SKIP):
                continue
            mo = detect(os.path.join(root, n, k + '.png'))
            if mo:
                meta[k]['mouth'] = mo; ok += 1
        json.dump(meta, open(pj, 'w'), indent=1)
        print(n, ok, '/', len([k for k in meta if not k.startswith(SKIP)]))


def estimate_side(root='sprites/poses'):
    """Pose samping (menghadap kanan): mulut diperkirakan dari pose 'front' (tinggi mulut dari atas) + tepi muka di baris itu."""
    SIDE = ('side_stand', 'side_walkA', 'side_walkB', 'side_talk', 'side_point', 'side_jog', 'sit_side')
    for n in sorted(os.listdir(root)):
        pj = os.path.join(root, n, 'poses.json')
        if not os.path.exists(pj):
            continue
        meta = json.load(open(pj))
        fr = meta.get('front', {}).get('mouth')
        if not fr:
            continue
        im = cv2.imread(os.path.join(root, n, 'front.png'), cv2.IMREAD_UNCHANGED)
        row = int(fr[1]); a = im[..., 3] > 128
        xs = np.where(a[row])[0]
        headw = xs.max() - xs.min() + 1
        cnt = 0
        for k in SIDE:
            if k not in meta:
                continue
            p = os.path.join(root, n, k + '.png')
            s = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            a2 = s[..., 3] > 128
            cy = fr[1]
            # tepi muka: kolom paling kanan pada baris cy, di dalam rentang kepala (batasi lebar = headw*1.1 dari kiri tubuh-kepala)
            band = a2[int(cy) - 3:int(cy) + 4].any(0)
            xx = np.where(band)[0]
            if len(xx) == 0:
                continue
            # kepala = klaster kolom yang berisi tepi kanan; ambil span kontigu dari kanan sepanjang <= headw*1.15
            xr = xx.max(); xl = max(xx.min(), xr - int(headw * 1.15))
            hw = xr - xl
            meta[k]['mouth'] = [round(xr - 0.17 * hw, 1), round(cy, 1), max(8, int(fr[2] * 0.7)), max(4, fr[3])]
            cnt += 1
        json.dump(meta, open(pj, 'w'), indent=1)
        print(n, 'side', cnt)
