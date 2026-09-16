**## 🌐 Integrasi Data & API Publik**

* **🔐 Google Authentication (Google Identity Services)**

  * **Fungsi:** Menyediakan fitur autentikasi pengguna melalui akun Google sehingga pengguna dapat melakukan login tanpa perlu membuat password secara manual.

  * **Implementasi:** Menggunakan **Google Identity Services (GIS)** untuk proses *Sign in with Google*.

  * **Penggunaan:** Digunakan untuk mengidentifikasi pengguna saat melakukan pemesanan serta memberikan *review/rating* setelah mendapatkan makanan.

* **📍 Browser Geolocation API**

  * **Fungsi:** Mendapatkan koordinat lokasi pengguna berdasarkan izin yang diberikan melalui browser.

  * **Implementasi:** Menggunakan `navigator.geolocation` untuk memperoleh koordinat **Latitude & Longitude** pengguna.

  * **Penggunaan:** Membantu menampilkan posisi pengguna pada peta dan menemukan restoran yang berada di sekitar lokasi pengguna.

* **OpenStreetMap (OSM) via Leaflet.js**

  * **Fungsi:** Menyediakan peta dasar (*base map tile*) gratis, ringan, dan *open-source* untuk menampilkan posisi restoran dan pengguna.

  * **Implementasi:** Library `leaflet` digunakan untuk merender peta interaktif, kustomisasi pin/marker, dan *event listener* klik pada marker.

* **Dummy Restaurant Data (`data/restaurants.json`)**

  * **Fungsi:** Kumpulan dataset simulasi restoran mitra untuk mendukung fitur *Browse*, *Map*, dan *Order*.

  * **Data yang disimpan:** Nama restoran, alamat, Latitude/Longitude, nama *surprise box*, harga normal, harga diskon, sisa stok, jam operasional, dan *pickup window*.

**---**

**## 🧩 Modul Aplikasi**

Aplikasi terbagi menjadi **5 modul**:

| Modul                    | Tanggung Jawab & Fungsi Utama                                                                                                                                                                                                       | Nama Penanggung Jawab       |
| :----------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------- |
| **🍔 Food & Restaurant** | Mengelola dan menampilkan data restoran serta *surprise box* yang tersedia, seperti nama restoran, jenis makanan, harga normal & diskon, sisa stok, serta jam ketersediaan/waktu *pickup*.                                          | Kapitra Fachriza Utomo      |
| **🗺️ Location & Map**   | Menampilkan lokasi restoran pada peta interaktif menggunakan **OpenStreetMap** dan **Leaflet.js**. Pengguna dapat melihat penanda (*marker*) restoran, posisi pengguna, serta mengakses detail ringkasan informasi lokasi restoran. | Muhammad Akbar Rinaldy      |
| **🛍️ Pick up / Order**  | Memfasilitasi alur transaksi pemesanan: memungkinkan pengguna memilih *surprise box*, melakukan reservasi penjemputan (*pickup*), serta menyajikan konfirmasi detail waktu (*pickup window*) dan alamat pengambilan.                | Dyah Zhafira Wibowo         |
| **⭐ Review / Rating**    | Mengelola pemberian rating (bintang 1-5) dan ulasan teks dari pengguna setelah menerima makanan, menampilkan rating rata-rata dan kumpulan ulasan pada halaman restoran sebagai bahan pertimbangan pengguna lain.                   | Khansa Nathania Khairunnisa |
