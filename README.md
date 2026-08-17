# Kompilasi Chord — Karaoke Akustik

Database timeline dan pemutar Karaoke Akustik untuk KompilasiChord.com.

## Prinsip

- Audio lagu asli hanya menjadi input analisis sementara dan tidak disimpan di repository.
- Hasil analisis disimpan satu kali sebagai JSON berdasarkan ID video YouTube.
- Halaman Blogger membaca `catalog.json` dan file pada `data/`, lalu memainkan petikan gitar sendiri.
- Lagu yang sudah mempunyai timeline tidak dianalisis ulang.

## Struktur

- `analyzer/` — mesin analisis gratis berbasis NumPy/SciPy.
- `input/` — metadata dan urutan chord untuk proses admin.
- `data/` — timeline publik berukuran kecil.
- `player/` — pemutar yang digunakan halaman Karaoke Akustik.
- `catalog.json` — indeks karaoke yang sudah tersedia.
- `tab-catalog.json` — satu-satunya daftar lagu untuk halaman katalog dan kotak pemilih di seluruh player Tab Musik.

## Menambahkan Tab Musik

Tambahkan halaman player ke folder `tabs/`, lalu daftarkan metadata lagunya satu kali di `tab-catalog.json`. Halaman `tab-musik.html` dan kotak **Pilih Tab Musik** pada setiap player akan membaca katalog yang sama secara otomatis.

## Mesin audio Tab Musik

Pemutar menggunakan bank sampel CC0, scheduler Web Audio dengan look-ahead adaptif, bus EQ/kompresor per kelompok instrumen, sustain-loop untuk nada panjang, dan limiter master. Full Band memiliki profil volume khusus per lagu; suara osilator sintetis hanya dipakai untuk klik metronom, bukan sebagai pengganti instrumen yang gagal dimuat.

Player Exists menyediakan mode **Karaoke HQ** sepanjang 4:27 dari enam stem hasil render bank suara CC0: gitar clean, gitar lead, bass, drum, strings, dan synth. Stem di-stream serempak agar mixer/solo tetap bekerja; `full-band.mp3` menjadi fallback kompatibilitas untuk perangkat tablet yang tidak sanggup membuka enam decoder sekaligus. Mode **Latihan Tab** lama tetap tersedia.

Player **For Revenge x Stereo Wall — Jakarta Hari Ini** memakai video resmi YouTube yang tampil di halaman. Kontrol putar, jeda, geser posisi, pilihan bagian, dan pengulangan disinkronkan dengan 106 birama data tab; tidak ada MP3 lagu atau hasil pemisahan vokal yang disimpan untuk player ini.

`harmony-engine.js` memahami accidental kres/mol, extension chord, dan slash bass. Pada playback, hanya nada bass non-chord di ketukan kuat yang diamankan ke root/fifth terdekat; event lain, kepadatan tab, dan timing transkripsi tetap dipertahankan. Targetnya adalah pengalaman latihan berbasis sampel yang konsisten seperti workflow Guitar Pro, bukan meniru mesin RSE proprietari.

Jalankan pemeriksaan mesin bersama dan seluruh player dengan:

```bash
python analyzer/validate_audio_engine.py
```

## Analisis lokal

```bash
python analyzer/analyze.py song.wav input/mangu.json data/JENpTmMQBQY.json
```

MP3/WAV lagu asli dan master karaoke dilarang di-commit. Master karaoke dipublikasikan ke Cloudflare R2; repository hanya menyimpan renderer, data tab, serta manifest asal-usul dan validasinya.
