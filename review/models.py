
# Mengimpor models dari Django.
# Setiap class yang mewarisi models.Model akan menjadi tabel database.
from django.db import models

# Mengimpor validator bawaan Django untuk membatasi nilai rating.
# MinValueValidator(1) memastikan rating tidak kurang dari 1.
# MaxValueValidator(5) memastikan rating tidak lebih dari 5.
from django.core.validators import MinValueValidator, MaxValueValidator

# Mengimpor ValidationError untuk memberikan pesan kesalahan
# ketika data review tidak memenuhi aturan validasi.
from django.core.exceptions import ValidationError


# Model Review digunakan untuk menyimpan penilaian dan komentar
# yang diberikan pengguna setelah menyelesaikan pesanan.
class Review(models.Model):

    # RELASI REVIEW DENGAN ORDER
    # OneToOneField menghubungkan satu review dengan satu order.
    # Artinya, satu pesanan hanya dapat memiliki satu review.
    #
    # "order.Order" menunjuk model Order di aplikasi order.
    # Penulisan string digunakan agar tidak perlu mengimpor
    # model Order secara langsung.
    #
    # on_delete=models.CASCADE:
    # Jika order dihapus dari database, review yang berkaitan
    # dengan order tersebut juga akan ikut dihapus.
    #
    # related_name="review":
    # Memungkinkan kita mengakses review melalui objek order,
    # misalnya: order.review
    order = models.OneToOneField(
        "order.Order",
        on_delete=models.CASCADE,
        related_name="review"
    )

    # RATING PENGGUNA
    # Menyimpan nilai rating berupa angka bulat positif.
    #
    # PositiveSmallIntegerField cocok digunakan karena rating
    # hanya membutuhkan angka kecil, yaitu 1 sampai 5.
    #
    # validators digunakan untuk membatasi nilai yang diterima.
    # Rating 0 atau 6 akan dianggap tidak valid saat validasi.
    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ]
    )

    # KOMENTAR PENGGUNA
    # TextField digunakan untuk menyimpan komentar atau ulasan
    # dalam bentuk teks dengan panjang yang fleksibel.
    #
    # Contoh komentar:
    # "Makanannya enak, porsinya banyak, dan harganya murah."
    comment = models.TextField()

    # BALASAN PEMILIK RESTORAN
    # Balasan bersifat opsional sehingga restoran tidak wajib membalas.
    owner_reply = models.TextField(
        blank=True,
        default=""
    )

    # WAKTU PEMBUATAN REVIEW
    # DateTimeField menyimpan tanggal dan waktu.
    #
    # auto_now_add=True berarti Django otomatis mengisi
    # tanggal dan waktu ketika review pertama kali dibuat.
    #
    # Nilai ini tidak otomatis berubah saat review diedit.
    created_at = models.DateTimeField(auto_now_add=True)

    # STATUS REVIEW (SOFT DELETE)
    # BooleanField menyimpan nilai True atau False.
    #
    # True  = review aktif dan boleh ditampilkan.
    # False = review tidak aktif atau dianggap sudah dihapus.
    #
    # Soft delete berarti review tidak benar-benar dihapus
    # dari database, tetapi hanya diubah statusnya.
    #
    # Ketika menampilkan review, kita perlu memfilter
    # data dengan active=True.
    active = models.BooleanField(default=True)

    # VALIDASI DATA REVIEW
    # clean() digunakan untuk menjalankan aturan validasi
    # tambahan yang tidak cukup diperiksa melalui field saja.
    def clean(self):

        # Menjalankan validasi clean() dari class induk.
        super().clean()

        # Memastikan review sudah terhubung dengan sebuah order.
        # Jika order_id belum ada, pemeriksaan status dilewati.
        if self.order_id:

            # Memeriksa apakah status pesanan sudah completed.
            #
            # Status "completed" berasal dari model Order.
            # Review hanya boleh dibuat ketika pesanan selesai.
            if self.order.status != "completed":

                # Menolak review jika order masih pending,
                # confirmed, atau cancelled.
                raise ValidationError(
                    "Review hanya dapat diberikan "
                    "untuk pesanan yang sudah selesai."
                )

        # Memastikan pengguna mengisi komentar.
        #
        # self.comment mengambil isi komentar review.
        # strip() menghapus spasi di awal dan akhir teks.
        #
        # Jika komentar kosong atau hanya berisi spasi,
        # sistem akan menolak data tersebut.
        if not self.comment or not self.comment.strip():

            # Mengaitkan pesan error dengan field comment
            # agar dapat ditampilkan pada form komentar.
            raise ValidationError({
                "comment": "Komentar tidak boleh kosong."
            })

    # MENYIMPAN REVIEW KE DATABASE
    # Method save() dipanggil ketika objek review disimpan.
    #
    # Method ini ditambahkan agar validasi model dijalankan
    # sebelum penyimpanan melalui review.save().
    def save(self, *args, **kwargs):

        # full_clean() memeriksa:
        # 1. Validasi tiap field, termasuk rating 1-5.
        # 2. Validasi tambahan di method clean().
        # 3. Pemeriksaan constraint dan keunikan model.
        #
        # Jika ada kesalahan, Django menghasilkan
        # ValidationError dan penyimpanan dibatalkan.
        self.full_clean()

        # Jika validasi berhasil, jalankan save() asli Django
        # untuk menyimpan review ke database.
        return super().save(*args, **kwargs)

    # REPRESENTASI STRING REVIEW
    # __str__() menentukan teks yang muncul ketika
    # objek Review ditampilkan, misalnya di Django Admin.
    #
    # self.order.kode_pickup mengambil kode pesanan.
    # self.rating mengambil nilai bintang yang diberikan.
    #
    # Contoh hasil: Review DS-12345 - 5/5
    def __str__(self):
        return f"Review {self.order.kode_pickup} - {self.rating}/5"
