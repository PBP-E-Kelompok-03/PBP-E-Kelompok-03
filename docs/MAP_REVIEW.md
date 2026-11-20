# Location & Map — FR-2.2, FR-2.3, FR-2.4, FR-2.5

## Perilaku

- `/map/` meminta Browser Geolocation API otomatis pada konteks aman. Tombol
  "Gunakan lokasi saya" dapat mencoba kembali setelah penolakan, timeout, atau
  lokasi tidak tersedia. Semua restoran tetap dapat dijelajahi ketika lokasi gagal.
- Marker hijau (✓): paket tersedia untuk dipesan; abu-abu (−): stok habis;
  kuning (◷): masih ada stok, tetapi di luar waktu pickup.
- Stok berasal dari `SurpriseBox` aktif. Harga minimum hanya memakai paket aktif
  dengan stok positif dan waktu pickup yang sesuai dengan aturan modul order.
  Batas waktu kosong tidak membatasi ketersediaan. Harga nol tetap valid.
- Popup dan daftar menampilkan foto, nama, status stok, harga minimum jika tersedia,
  alamat, jam buka, serta CTA detail restoran.
- `GET /map/restaurants/` mengembalikan data database terbaru dengan cache dimatikan.
  Halaman memperbarui data setiap 30 detik saat terlihat, ketika tab kembali aktif,
  dan melalui tombol "Perbarui stok". Pembaruan mempertahankan filter serta popup
  yang sedang terbuka. Ketika jaringan gagal, data sebelumnya tetap terlihat
  dengan pesan bahwa pembaruan gagal. Status bukan jaminan reservasi; checkout
  tetap memvalidasi stok di server.
- Peta tidak menggunakan fallback fixture. Database kosong menghasilkan daftar kosong.

## Foto restoran

Model `map.RestaurantMapProfile` menyimpan URL foto HTTPS melalui relasi satu-ke-satu
ke `food.Restaurant`. Model/migrasi milik food tidak diubah.

Pemilik restoran dan staf dapat membuka "Ubah foto restoran" pada kartu/popup.
Form mendukung penambahan, penggantian, dan penghapusan URL foto. Pengunjung lain
tidak dapat mengubahnya. Model juga tersedia di Django admin. URL harus menuju
gambar yang dapat diakses publik melalui HTTPS; aplikasi tidak mengunggah foto.

Foto yang belum diisi atau gagal dimuat memakai ilustrasi lokal dan label
"Foto belum tersedia", tanpa mengarang foto restoran.

## Menjalankan

```powershell
.\env\Scripts\python.exe -B manage.py migrate --settings=config.settings.dev
.\env\Scripts\python.exe -B manage.py test --settings=config.settings.test
```

Migrasi baru: `map/0001_initial`. Jalankan migrasi dengan settings deployment juga
sebelum merilis kode ke produksi.

Tes Django meliputi stok aktual, harga termurah, stok nol, waktu pickup, perubahan
stok setelah order/cancel, koordinat, escaping, cache API, foto, izin edit, CSRF,
serta regresi angka JavaScript dan stok nol di halaman detail tujuan CTA.

## Navigasi eksternal (FR-2.5)

Popup marker dan kartu restoran menyediakan tombol **Arahkan ke Lokasi** yang
membuka Google Maps di tab/aplikasi eksternal. URL dibuat di backend dari
koordinat valid restoran yang sama dengan marker:
`https://www.google.com/maps/dir/?api=1&destination=<lat>,<lng>&dir_action=navigate`.
Parameter di-encode memakai `urlencode`; angka memakai titik desimal dan tidak
berubah oleh locale Indonesia. Tidak ada API key atau layanan routing berbayar.

Parameter origin sengaja tidak ditentukan: Google Maps menggunakan lokasi
perangkat jika tersedia atau meminta titik keberangkatan. Tombol tetap tersedia
ketika izin lokasi ditolak, stok habis, JavaScript dimatikan, atau Leaflet gagal
dimuat. Pembaruan stok juga memperbarui URL jika koordinat database berubah.
Link memakai `target="_blank"` dan `rel="noopener noreferrer"`.

Verifikasi manual: pilih dua marker berbeda, klik tombol navigasi, dan cocokkan
tujuan Google Maps dengan koordinat masing-masing restoran. Ulangi setelah
menolak izin lokasi dan dari kartu daftar. Di perangkat mobile, periksa pembukaan
aplikasi Google Maps jika terpasang; pada desktop periksa tab browser.
Tes otomatis memeriksa URL/koordinat dan integrasi DOM, tanpa membuka layanan
Google Maps publik. Perhitungan rute dan perpindahan ke aplikasi Maps di perangkat
nyata belum diuji otomatis. Lihat
[dokumentasi Google Maps URLs](https://developers.google.com/maps/documentation/urls/get-started#directions).

FR-2.5 tidak memerlukan migrasi database tambahan. Geolocation perangkat nyata
tetap bergantung izin pengguna, konteks aman, dan kemampuan browser.

## Hasil verifikasi implementasi

- 104 tes Django lulus, termasuk 30 tes pada modul map.
- Model dan migrasi konsisten: `makemigrations --check --dry-run` tidak menemukan perubahan.
- 72 pemeriksaan Chrome headless lulus menggunakan Leaflet 1.9.4 asli, halaman
  hasil render Django, API stok aktual, database di memori, geolocation simulasi,
  serta tile lokal pengganti. Ini bukan pengujian GPS perangkat atau layanan tile OSM.
- Browser memverifikasi marker, popup, harga, CTA detail, perubahan stok, kegagalan
  pembaruan, penolakan/timeout lokasi, fallback gambar/Leaflet, dan lebar mobile/desktop.

Ulangi pemeriksaan browser dengan Chrome/Chromium terpasang:

```powershell
.\env\Scripts\python.exe -B map/browser_checks.py
```

Runner memakai pustaka standar Python, mengunduh aset Leaflet resmi dengan
pemeriksaan SHA-256, serta membuat profil Chrome sementara. Set environment
variable `CHROME_BINARY` jika Chrome tidak berada di lokasi standar.

## Perbaikan tile OSM dan kebijakan referrer

Pemeriksaan sebelum perbaikan menemukan header `Referrer-Policy: same-origin`
pada respons `/map/` HTTP dan HTTPS. Ini berasal dari default Django
`SecurityMiddleware`, karena settings belum menentukan `SECURE_REFERRER_POLICY`.
Chrome dengan Leaflet asli dan server tile lokal berbeda origin membuktikan
bahwa request tile tidak mengirim `Referer`. Kondisi ini melanggar
[OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/).
Ini adalah kesalahan konfigurasi yang terverifikasi; status blokir OSM pada
jaringan pengguna/deployment belum dapat dipastikan dari pengujian lokal.

Perbaikan berlaku pada settings bersama dev/production:
`SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"`.
Tile layer juga memakai opsi Leaflet `referrerPolicy` yang sama. Browser mengirim
origin situs (tanpa path/query) untuk request lintas origin, termasuk dari
localhost HTTP ke tile HTTPS dan dari deployment HTTPS ke tile HTTPS.
URL tetap `https://tile.openstreetmap.org/{z}/{x}/{y}.png`; atribusi terlihat
sebagai © OpenStreetMap contributors dengan tautan copyright.

Tidak ditemukan meta referrer, middleware kustom penghapus Referer, proxy tile,
prefetch, atau cache-busting tile dalam repository. `no-referrer` pada thumbnail
restoran tetap berlaku khusus foto. `no-store` pada fetch API restoran hanya
untuk pembaruan stok; tile tetap menggunakan cache HTTP browser. Konfigurasi
reverse proxy/CDN di luar repository perlu diperiksa pada deployment sebenarnya.

Tes tambahan memeriksa header HTTP/HTTPS, forwarded HTTPS dan SSL redirect,
serta memastikan header nosniff dan X-Frame-Options DENY tetap berlaku.
Runner browser meneruskan header Django, mengamati Referer dari server tile lokal
berbeda port, memastikan origin saja dikirim, gambar tile termuat, identitas
browser/caching tidak diganti, serta atribusi dan konfigurasi URL tetap benar.
Runner memakai X-Frame-Options SAMEORIGIN hanya dalam harness yang membutuhkan
iframe; aplikasi tetap DENY. Tidak ada tile OSM publik yang diminta oleh tes.

### Verifikasi manual local dan deployment

1. Restart `python manage.py runserver` setelah perubahan settings. Perbaikan tile
   ini tidak memerlukan migrasi database tambahan.
2. Saat deployment, jalankan `collectstatic --noinput` dengan settings production
   dan restart proses aplikasi. Pastikan reverse proxy/CDN tidak menimpa header
   dengan `same-origin` atau `no-referrer`.
3. Buka `/map/` dan DevTools > Network. Biarkan opsi **Disable cache tidak dicentang**,
   lalu muat ulang halaman secara normal.
4. Periksa respons dokumen: `Referrer-Policy: strict-origin-when-cross-origin`.
   Periksa request PNG ke `tile.openstreetmap.org`: URL HTTPS, `Referer` berisi
   origin aplikasi (misalnya `http://127.0.0.1:8000/`), dan tile berhasil dimuat
   dari respons 200, 304, atau cache. Pastikan gambar peta, bukan pesan blokir,
   terlihat; periksa juga marker, lokasi, radius, popup, dan CTA.
5. Bila 403 masih muncul meskipun header sudah benar, periksa header aktual,
   ekstensi privasi, VPN/proxy, dan respons blokir pada jaringan tersebut.
   Jangan memalsukan User-Agent/Referer, mengganti hostname untuk mengakali
   blokir, mematikan cache, atau menambah retry agresif.

Pengujian otomatis tidak membuktikan akses tile publik OSM sudah dipulihkan.
Geolocation perangkat nyata dan konfigurasi reverse proxy produksi juga
memerlukan browser/deployment sebenarnya. Jika layanan tetap menolak akses,
opsi yang sah adalah provider berbasis OSM dengan paket, kuota, API key, atribusi,
dan izin penggunaan yang sesuai, atau tile yang di-host sendiri; lihat
[daftar provider](https://switch2osm.org/providers/) dan
[panduan self-hosting](https://switch2osm.org/serving-tiles/).
Provider tidak diganti oleh perbaikan ini.
