 🍲 Dibuang Sayang


> **Platform Penyelamat Makanan Berlebih (Surplus Food) untuk Mengurangi Food Waste dan Menyediakan Pilihan Makanan Terjangkau.**


---


## 📌 Daftar Isi
- [Latar Belakang](#-latar-belakang)
- [Problem Statement](#-problem-statement)
- [Solusi](#-solusi)
- [Fitur Utama (MVP)](#-fitur-utama-mvp)
- [Arsitektur & Modul Sistem](#-arsitektur--modul-sistem)
- [Integrasi Data & API Publik](#-integrasi-data--api-publik)
- [Tech Stack](#-tech-stack-rekomendasi)
- [Struktur Direktori](#-struktur-direktori)
- [Panduan Memulai (Quick Start)](#-panduan-memulai-quick-start)
- [Alur Pengguna (User Flow)](#-alur-pengguna-user-flow)
- [Roadmap Pengembangan](#-roadmap-pengembangan)
- [Lisensi](#-lisensi)


---


## 📖 Latar Belakang


Banyak restoran, *bakery*, kafe, dan toko makanan memiliki stok makanan berlebih yang masih sangat layak dan aman dikonsumsi, namun tidak terjual pada penghujung hari operasional. Makanan-makanan ini sering kali berakhir menjadi limbah organik (*food waste*).


Di sisi lain, terdapat masyarakat, mahasiswa, maupun pekerja yang ingin mendapatkan makanan berkualitas dengan harga yang jauh lebih hemat dan terjangkau. **Dibuang Sayang** hadir sebagai jembatan digital antara mitra penyedia makanan dan konsumen untuk memitigasi pemborosan makanan sekaligus menciptakan dampak ekonomi dan lingkungan yang positif.


---


## 🎯 Problem Statement


> **Bagaimana menyediakan platform yang memudahkan pengguna menemukan makanan berlebih dari restoran di sekitar mereka dengan harga yang lebih murah, sekaligus membantu restoran mengurangi *food waste*?**


---


## 💡 Solusi


Membangun aplikasi web interaktif yang memungkinkan gerai makanan menawarkan surplus makanan harian dalam bentuk **Surprise Box** atau paket makanan hemat berdiskon. Pengguna dapat:
- Menjelajahi restoran terdekat berbasis peta interaktif (*geolocation*).
- Memilih paket makanan sebelum batas waktu operasional berakhir.
- Melakukan reservasi pemesanan secara daring (*online order*).
- Mengambil langsung pesanan di restoran (*in-store self-pickup*) pada jendela waktu (*time window*) yang ditentukan.


---


## 🚀 Fitur Utama (MVP)


| Fitur | Deskripsi |
| :--- | :--- |
| **1. Browse Food** | Pengguna dapat melihat katalog makanan/surprise box yang tersedia dari berbagai mitra, lengkap dengan foto, nama paket, potongan harga (diskon), sisa stok, dan jam operasional. |
| **2. Location & Map** | Visualisasi sebaran mitra restoran di sekitar lokasi pengguna melalui peta interaktif berbasis koordinat lintang & bujur (Latitude/Longitude). |
| **3. Pick Up / Order** | Alur reservasi paket makanan untuk diambil langsung di gerai (*self-pickup*). Dilengkapi dengan ringkasan instruksi penjemputan, batas waktu (*pickup window*), serta detail alamat gerai. |
| **4. Review / Rating** | Pengguna dapat memberikan ulasan (teks) dan rating (bintang 1-5) setelah mendapatkan makanan yang dipesan. Rating dan Review ditampilkan di halaman restoran. |




## 🌐 Integrasi Data & API Publik


- **OpenStreetMap (OSM) via Leaflet.js**
  - **Fungsi:** Menyediakan peta dasar (*base map tile*) gratis, ringan, dan *open-source* untuk menampilkan posisi restoran dan pengguna.
  - **Implementasi:** Library `leaflet` digunakan untuk merender peta interaktif, kustomisasi pin/marker, dan *event listener* klik pada marker.
- **Dummy Restaurant Data (`data/restaurants.json`)**
  - **Fungsi:** Kumpulan dataset simulasi restoran mitra untuk mendukung fitur *Browse*, *Map*, dan *Order*.
- **Google Authentication (Google Identity Services)**
  - **Fungsi:** Menyediakan fitur autentikasi pengguna melalui akun Google sehingga pengguna dapat melakukan login tanpa perlu membuat password secara manual.
- **Browser Geolocation API**
  - **Fungsi:** Mendapatkan koordinat lokasi pengguna berdasarkan izin yang diberikan melalui browser.
---
## 🧩 Modul Aplikasi


Aplikasi terbagi menjadi 4 modul:


| Modul | Tanggung Jawab & Fungsi Utama | PIC
| :--- | :--- | :--- |
| **🍔 Food & Restaurant** | Mengelola dan menampilkan data restoran serta *surprise box* yang tersedia, seperti nama restoran, jenis makanan, harga normal & diskon, sisa stok, serta jam ketersediaan/waktu *pickup*. | Kapitra Fachriza Utomo
| **🗺️ Location & Map** | Menampilkan lokasi restoran pada peta interaktif menggunakan **OpenStreetMap** dan **Leaflet.js**. Pengguna dapat melihat penanda (*marker*) restoran dan mengakses detail ringkasan informasi lokasinya. | Muhammad Akbar Rinaldy 2506586311
| **🛍️ Pick up / Order** | Memfasilitasi alur transaksi pemesanan: memungkinkan pengguna memilih *surprise box*, melakukan reservasi penjemputan (*pickup*), serta menyajikan konfirmasi detail waktu (*pickup window*) dan alamat pengambilan. | Dyah Zhafira Wibowo 2506623723
| **⭐ Review / Rating** | Mengelola pemberian rating (bintang 1-5) dan ulasan teks dari pengguna setelah menerima makanan, menampilkan rating rata-rata dan kumpulan ulasan pada halaman restoran sebagai bahan pertimbangan pengguna lain. | Khansa Nathania Khairunnisa 2506618061
