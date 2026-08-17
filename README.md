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

Player **Exists — Dirantai Digelangi Rindu** memakai video resmi ExistsVEVO di YouTube. Kontrol putar, jeda, geser posisi, pilihan bagian, dan pengulangan disinkronkan dengan 100 birama data tab; tampilan gitar lead, gitar rhythm, bass, drum, strings, dan synth tetap tersedia tanpa menyimpan MP3 lagu atau hasil pemisahan audio.

Player **Romeo — Bunga Terakhir** memakai rekaman Bebi Romeo di YouTube. Kontrol putar, jeda, geser posisi, pilihan bagian, dan pengulangan disinkronkan dengan 88 birama data tab termasuk pickup; tampilan gitar elektrik, piano, bass, drum, dan orkestra/pad tetap tersedia tanpa menyimpan MP3 lagu atau hasil pemisahan audio.

Player **Atmosfera — Berakhirlah Sudah** memakai video resmi Rusa Music di YouTube dengan sinkronisasi 66 birama untuk Gitar, Piano/Keyboard, Bass, dan Drum. Identitas artis lama “Aiman Tino” dikoreksi karena data nada, akor, tempo, dan durasi cocok dengan rekaman Atmosfera. Halaman tidak memuat MP3 lagu, pemutar sampel, mixer, atau indikator teks nada berjalan; tampilan desktop, iframe Blogger, dan mobile menggunakan tata letak responsif.

Player **Anie Carera — Hati Siapa Tak Luka** memakai video dari kanal terverifikasi GP Musikpedia di YouTube. Kontrol putar, jeda, geser posisi, pilihan bagian, dan pengulangan disinkronkan dengan 96 birama data tab; tampilan Gitar 1, Gitar 2, Keyboard/Synth, Bass, dan Drum tetap tersedia tanpa menyimpan MP3 lagu atau hasil pemisahan audio.

Player **Kahitna — Cerita Cinta** memakai video resmi Musica Studios di YouTube dengan sinkronisasi tab 121 birama untuk Gitar Elektrik, Bass, dan Drum. Halaman ini tidak memuat MP3 lagu, pemutar sampel, mixer, atau indikator teks nada berjalan; tampilan desktop, iframe Blogger, dan mobile memakai tata letak responsif yang sama.

Player **Peterpan — Semua Tentang Kita** memakai video resmi Musica Studios di YouTube. Data Guitar Pro yang tersedia hanya memuat 78 birama untuk Gitar Rhythm dan Gitar Lead, sekitar 74% dari perkiraan struktur penuh; halaman menandainya sebagai **tab parsial** dan tidak membuat nada/birama palsu. MP3, sampler, mixer, dan indikator teks nada berjalan tidak digunakan; tampilan desktop, iframe Blogger, dan mobile tetap responsif.

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
