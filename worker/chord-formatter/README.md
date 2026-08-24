# Protected Chord Formatter

Cloudflare Worker untuk Formatter SOP Kompilasi Chord dengan login username + password.

## Keamanan

- Username default berasal dari `FORMATTER_USER` di `wrangler.jsonc`.
- Password **tidak disimpan di GitHub** dan wajib disimpan sebagai Worker secret `FORMATTER_PASSWORD`.
- Session signing key **tidak disimpan di GitHub** dan wajib disimpan sebagai Worker secret `SESSION_SECRET`.
- Session berlaku 12 jam, menggunakan cookie `HttpOnly`, `Secure`, dan `SameSite=Lax`.
- Halaman formatter GitHub Pages publik telah dinonaktifkan.

## Deploy pertama

```bash
cd worker/chord-formatter
npm install
npx wrangler login
npx wrangler secret put FORMATTER_PASSWORD
npx wrangler secret put SESSION_SECRET
npx wrangler deploy
```

Saat diminta nilai `SESSION_SECRET`, gunakan string acak panjang minimal 32 karakter.

Setelah deploy, buka URL `workers.dev` yang ditampilkan Wrangler. Pengguna yang belum login hanya melihat halaman login; aplikasi formatter baru dikirim oleh Worker setelah session tervalidasi.
