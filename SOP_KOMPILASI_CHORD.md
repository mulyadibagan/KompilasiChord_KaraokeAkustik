# SOP Kompilasi Chord

Formatter utama: `chord-formatter.html`.

## Aturan wajib

1. Bungkus output dengan `<pre data-key="...">` dan `</pre>`.
2. `data-key` mengikuti nada dasar lagu yang benar.
3. Nama bagian distandarkan: `[Intro :]`, `[Verse n :]`, `[Pre-Reff :]`, `[Reff :]`, `[Post-Reff :]`, `[Bridge :]`, `[Interlude :]`, `[Reff Overtone :]`, `[Outro :]`.
4. `[Musik :]` menjadi `[Interlude :]`.
5. `[Intro :]` yang muncul setelah isi lagu dimulai menjadi `[Interlude :]`.
6. Ellipsis/titik berulang pada lirik dihapus. Titik di tengah lirik diganti spasi dengan jumlah kolom yang sama agar alignment tidak berubah.
7. Penanda mandiri `*)` dihapus dari output dan tidak dianggap sebagai lirik atau nama bagian.
8. Baris lirik tidak memakai spasi di awal. Chord dan lirik diperlakukan sebagai pasangan: ketika indent awal lirik dihapus, baris chord pasangannya digeser ke kiri dengan offset yang sama agar posisi chord terhadap kata tetap sejajar.
9. Chord transisi untuk transposer harus memakai spasi: `A-G` → `A -G`, `G-F` → `G -F`, `F#m-G` → `F#m -G`, `D-C#` → `D -C#`.
10. Saat menambah spasi sebelum chord transisi, jarak sesudah token dikompensasi bila tersedia agar chord berikutnya tetap di kolom semula. Jika ruang hanya satu spasi, formatter memberi peringatan alignment dan tidak boleh menggabungkan token chord.
11. Slash chord, accidental, minor, dan chord khusus seperti `D/F#`, `G#`, `A#m`, `-D/F#` dipertahankan.
12. Leading spaces tidak boleh di-trim membabi buta pada seluruh dokumen. Normalisasi indent hanya dilakukan pada pasangan chord–lirik agar alignment tetap terjaga.
13. Lirik, chord, urutan section, dan overtone tidak ditulis ulang kecuali normalisasi format SOP.
14. Output akhir harus siap ditempel ke Blogger.
