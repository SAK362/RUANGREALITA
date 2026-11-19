# RuangRealita - kit pipeline (render di sesi Claude)

Alur: n8n (naskah + suara beremosi) > GitHub Actions (Whisper saja) > bundel ZIP kecil di Drive > Claude render MP4.
GitHub TIDAK merender. File `render.yml` tidak dipakai lagi (boleh dihapus).

## Setup (sekali)
1. Buat repo GitHub (mis. RUANGREALITA), upload seluruh isi folder ini ke branch `main`.
2. Settings > Actions > General > Workflow permissions = **Read and write**.
3. Settings > Secrets > Actions: tambah `CALLBACK_KEY` (sama dengan `callbackKey` di n8n).
4. Token GitHub di n8n (GITHUB TOKEN SAWIKUREAL): `contents:write` dan `actions:write`.

## n8n
Workflow "RuangRealita - Produksi Otomatis". Isi `Konfigurasi` dan `Konfigurasi Callback`:
githubOwner, githubRepo, callbackKey, driveFolderId (folder khusus bundel). Lalu aktifkan.
Status topik: SIAP > PROSES > WHISPER > SIAP_RENDER (bundel di Drive) / GAGAL.
Setelah Claude merender, ubah status manual (atau lewat workflow upload Anda) ke SIAP_UPLOAD.

## Ambil batch (di chat Claude)
Ketik "ambil batch RuangRealita". Claude membaca folder Drive, mengunduh bundel `*_bundle.zip`
(isi: job.json, words.json, audio/*.opus; sekitar 0,3 MB per menit suara), render, kirim MP4 + deskripsi.

## Job JSON
id, title, location (warkop|warung|kantor|pasar|gang), cast[], beats[{speaker,text,style}], description, hashtags[].
Audio per beat: `jobs/<id>/audio/beat_00.wav`, `beat_01.wav`, ...

## Render lokal
`npm install && npx playwright install chromium && node render.js jobs/0001/job.json out/0001.mp4`

## Ekspresi (langkah 2)
`sprites/faces/<Karakter>__<ekspresi>_<mulut>.png` dibuat oleh script (bukan digambar ulang). Ekspresi: n, happy, sad, surp, smirk, flat; mulut: 0 (tutup), a, b (bicara); plus `blink`.
Field `style` pada beat memilih ekspresi: santai=n, mengeluh=sad, kaget=surp, sinis=smirk, pasrah=flat, semangat=happy. Mulut bergerak mengikuti timing kata, ada kedip, loncat kecil per kata, dan condong saat bicara.

## Warkop interior (v3)
`location: "warkop"` kini di dalam ruangan (kipas, jam, TV, lampu, uap kopi, tirai bergoyang). Tambahkan `"exterior": true` di job.json untuk versi luar. Lokasi lain tetap eksterior.
