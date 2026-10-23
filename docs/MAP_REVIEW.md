# Review Location & Map

Tanggal: 4 Oktober 2026.

## Status requirement

Poin 21–23 telah diimplementasikan dan diuji. Review implementasi untuk poin 24
telah dilakukan terhadap permintaan yang tersedia dan deskripsi modul dalam README.
Teks resmi FR-2.1, FR-2.2, FR-2.3, FR-2.4, dan FR-2.5 tidak ditemukan dalam repository
dan belum diberikan dalam percakapan. Karena itu, pemenuhan kelima ID tersebut
**belum dapat dikonfirmasi**. Checklist berikut bukan pengganti spesifikasi resmi.

| Aspek yang dapat diperiksa | Hasil | Implementasi |
| --- | --- | --- |
| Halaman peta publik dan navigasi | Lulus | `/map/`, namespace `map:map`, tautan Peta Restoran |
| Peta interaktif dan marker restoran | Lulus | Leaflet/OpenStreetMap; hanya restoran aktif dengan koordinat valid |
| Informasi restoran | Lulus | Popup serta daftar berisi nama, alamat, jam buka, dan tautan detail |
| Lokasi pengguna dan fallback | Lulus | Tombol meminta lokasi; penanda pengguna; penolakan/error mengembalikan semua restoran |
| Radius 1/3/5 km | Lulus | Jarak koordinat pengguna–restoran; marker dan daftar memakai seleksi yang sama |
| Hasil kosong | Lulus | Pesan jelas dan pilihan kembali ke Semua restoran |
| Ketahanan tampilan | Lulus | Daftar dari server tetap tersedia saat JavaScript/Leaflet tidak tersedia |

## Perilaku dan integrasi

- Sebelum lokasi tersedia, Semua restoran ditampilkan dan filter radius dinonaktifkan.
- Setelah lokasi tersedia, pengguna dapat memilih 1, 3, atau 5 km. Restoran dengan
  jarak kurang dari atau sama dengan radius ditampilkan.
- Perhitungan memakai `LatLng.distanceTo` dalam meter; ini jarak garis lurus,
  bukan jarak rute jalan. Lihat [referensi Leaflet](https://leafletjs.com/reference.html#latlng-distanceto).
- Penolakan izin, lokasi tidak tersedia, dan timeout menampilkan pesan serta
  mempertahankan navigasi peta, daftar, dan detail restoran. Pengguna dapat mencoba lagi.
- Browser tanpa geolocation/konteks aman tetap menampilkan semua restoran.
  Geolocation membutuhkan izin dan konteks aman; lihat
  [dokumentasi Geolocation](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/getCurrentPosition).
- Data mengikuti pola modul food: restoran aktif dari database, atau fixture jika tidak
  ada restoran aktif. Database tetap perlu dimigrasikan sebelum menjalankan aplikasi.
- Model dan migrasi antarmodul tidak diubah.

## Validasi yang dijalankan

```powershell
.\env\Scripts\python.exe -B manage.py test --settings=config.settings.test
```

Hasil: **56 test Django lulus**, termasuk **7 test baru** pada `map/tests.py`.
Test mencakup resolusi route, akses anonim, template/data restoran, opsi radius,
validasi koordinat (termasuk nol), fallback fixture, keadaan kosong, dan escaping.

Pemeriksaan tambahan melalui Chrome headless pada viewport 390 × 844:
**28 assertion lulus** untuk filter 1/3/5 km dan Semua restoran, kesamaan marker/daftar,
popup detail, konten berbahaya sebagai teks, penolakan/ketidaktersediaan/timeout lokasi,
retry, hasil kosong, lebar mobile, browser tanpa geolocation, dan kegagalan Leaflet.
Pemeriksaan ini memakai Leaflet 1.9.4 asli, koordinat restoran deterministik,
geolocation simulasi, serta tile pengganti lokal. Ini bukan pengujian GPS perangkat
atau ketersediaan layanan tile OpenStreetMap. Harness browser bersifat sementara;
test regresi yang disimpan dalam repository adalah test Django di atas.

Untuk pengecekan manual, buka `/map/`, gunakan lokasi saya, lalu ganti radius.
Tolak izin setelah mengatur ulang permission browser dan pastikan semua restoran
tetap dapat dijelajahi. Status pemenuhan FR perlu diperbarui setelah teks aslinya tersedia.
