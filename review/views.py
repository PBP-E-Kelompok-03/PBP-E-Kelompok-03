
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db import IntegrityError, transaction
from django.db.models import Avg
from django.views.decorators.http import require_GET, require_POST
from food.models import Restaurant

from order.models import Order
from .models import Review
from .forms import ReviewForm


# Membuat review untuk pesanan yang sudah selesai
@login_required
def create_review(request, order_id):
    # Hanya akun pembeli yang boleh membuat review
    if not request.user.is_buyer:
        raise PermissionDenied(
            "Hanya pembeli yang boleh membuat review."
        )

    # Mengambil pesanan berdasarkan ID
    order = get_object_or_404(Order, id=order_id)

    # Memastikan pesanan milik pengguna yang sedang login
    if order.pembeli_id != request.user.pk:
        raise PermissionDenied(
            "Anda tidak dapat mereview pesanan orang lain."
        )

    # Review hanya boleh dibuat setelah pesanan selesai
    if order.status != Order.Status.COMPLETED:
        raise PermissionDenied(
            "Review hanya dapat diberikan setelah pesanan selesai."
        )
    
    # Respons ketika pesanan sudah memiliki review
    def sudah_review():
         # Jika pembeli membuka halaman Tulis Review lagi,
        # kembalikan ke halaman voucher, bukan tampilkan JSON.
        if request.method == "GET":
            return redirect("order:confirmation", order.id)

        # Untuk pengiriman review duplikat, tetap ditolak
        return JsonResponse({
            "success": False,
            "error": "Pesanan ini sudah memiliki review."
        }, status=409)


    # Memproses data review yang dikirim pengguna
    if request.method == "POST":
        form = ReviewForm(request.POST)

        # Menyimpan review jika data sudah valid
        if not form.is_valid():
            return JsonResponse({
                "success": False,
                "errors": form.errors
            }, status=400)
        
        try:
            # Pengecekan dan penyimpanan dalam satu transaksi
            with transaction.atomic():

                # Mengunci Order selama transaksi,
                # pada database yang mendukung row locking
                order = get_object_or_404(
                    Order.objects.select_for_update(),
                    pk=order_id
                )

                # Periksa ulang kepemilikan pesanan
                if order.pembeli_id != request.user.pk:
                    raise PermissionDenied(
                        "Kamu tidak boleh mereview pesanan orang lain."
                    )

                # Periksa ulang status pesanan
                if order.status != Order.Status.COMPLETED:
                    raise PermissionDenied(
                        "Review hanya dapat diberikan setelah pesanan selesai."
                    )

                # Cek duplikasi setelah mendapatkan lock
                if Review.objects.filter(order=order).exists():
                    return sudah_review()

                # Menyimpan review
                review = form.save(commit=False)
                review.order = order
                review.save()

        except (IntegrityError, ValidationError):
            # Menangani duplikasi akibat request bersamaan
            if Review.objects.filter(order_id=order_id).exists():
                return sudah_review()

            # Error database lainnya  yang tetap diteruskan
            raise

        return JsonResponse({
            "success": True,
            "message": "Review berhasil dikirim!"
        })
 

     # Mencegah membuka form untuk order yang sudah direview
    if Review.objects.filter(order=order).exists():
        return sudah_review()

    # Menampilkan form review ketika halaman dibuka
    form = ReviewForm()

    return render(request, "review/create_review.html", {
        "form": form,
        "order": order
    })


# Mengambil daftar review dan rata-rata rating suatu Surprise Box
def list_reviews(request, surprise_box_id):

    # Mengambil review aktif sesuai ID Surprise Box
    reviews = Review.objects.filter(
        order__surprise_box_id=surprise_box_id,
        active=True
    ).select_related(
        "order__pembeli"
    ).order_by("-created_at")

    # Menghitung rata-rata rating dan jumlah ulasan
    rata_rata = reviews.aggregate(
        Avg("rating")
    )["rating__avg"]

    jumlah_ulasan = reviews.count()

    # Menyiapkan data review untuk ditampilkan
    data_reviews = []

    for review in reviews[:50]:
        data_reviews.append({
            "nama": review.order.pembeli.username,
            "rating": review.rating,
            "komentar": review.comment,
            "tanggal": review.created_at.strftime("%d/%m/%Y"),
            "owner_reply": review.owner_reply,
            "restaurant_name": (review.order.surprise_box.restaurant.nama
               if review.order.surprise_box_id else ""),
        })

    # Mengirim data review ke frontend menggunakan JSON
    return JsonResponse({
        "rata_rata": round(rata_rata, 1) if rata_rata is not None else 0,
        "jumlah_ulasan": jumlah_ulasan,
        "reviews": data_reviews
    })


# ============================================================
# EDIT REVIEW PEMBELI
# ============================================================

@login_required
@require_POST
def update_review(request, review_id):

    # Hanya pembeli yang boleh mengedit review
    if not request.user.is_buyer:
        raise PermissionDenied(
            "Hanya pembeli yang boleh mengedit review."
        )

    # Mengambil review yang masih aktif
    review = get_object_or_404(
        Review.objects.select_related("order"),
        pk=review_id,
        active=True
    )

    # Memastikan review milik pembeli yang sedang login
    if review.order.pembeli_id != request.user.pk:
        raise PermissionDenied(
            "Kamu tidak boleh mengedit review orang lain."
        )

    # Hanya pesanan completed yang boleh direview
    if review.order.status != Order.Status.COMPLETED:
        raise PermissionDenied(
            "Review hanya dapat diedit setelah pesanan selesai."
        )

    # Review tidak dapat diedit setelah restoran membalas
    if review.owner_reply.strip():
        return JsonResponse({
            "success": False,
            "error": "Review tidak dapat diedit karena restoran sudah membalas."
        }, status=403)

    # Memvalidasi rating dan komentar baru
    form = ReviewForm(request.POST, instance=review)

    if not form.is_valid():
        return JsonResponse({
            "success": False,
            "errors": form.errors
        }, status=400)

    # UPDATE dilakukan langsung oleh database dengan kondisi.
    # Jika restoran sudah membalas saat request berlangsung,
    # perubahan tidak akan disimpan.
    updated = Review.objects.filter(
        pk=review_id,
        active=True,
        owner_reply=""
    ).update(
        rating=form.cleaned_data["rating"],
        comment=form.cleaned_data["comment"]
    )

    # Jika restoran membalas sebelum UPDATE berhasil
    if not updated:
        return JsonResponse({
            "success": False,
            "error": (
                "Review sudah dibalas atau tidak lagi aktif. "
                "Silakan muat ulang ulasan."
            )
        }, status=403)

    return JsonResponse({
        "success": True,
        "message": "Review berhasil diperbarui!"
    })


# ============================================================
# HAPUS REVIEW PEMBELI (SOFT DELETE)
# ============================================================

@login_required
@require_POST
def delete_review(request, review_id):

    # Hanya pembeli yang boleh menghapus review
    if not request.user.is_buyer:
        raise PermissionDenied(
            "Hanya pembeli yang boleh menghapus review."
        )

    # Mengambil review yang masih aktif
    review = get_object_or_404(
        Review.objects.select_related("order"),
        pk=review_id,
        active=True
    )

    # Review hanya boleh dihapus oleh pembeli pemiliknya
    if review.order.pembeli_id != request.user.pk:
        raise PermissionDenied(
            "Kamu tidak boleh menghapus review pengguna lain."
        )

    # Review tidak dapat dihapus setelah restoran membalas
    if review.owner_reply.strip():
        return JsonResponse({
            "success": False,
            "error": "Review tidak dapat dihapus."
        }, status=403)

    # Soft delete bersyarat.
    # Jika restoran sudah membalas terlebih dahulu,
    # UPDATE akan gagal dan review tetap aktif.
    updated = Review.objects.filter(
        pk=review_id,
        active=True,
        owner_reply=""
    ).update(
        active=False
    )

    if not updated:
        return JsonResponse({
            "success": False,
            "error": (
                "Review sudah dibalas atau tidak lagi aktif. "
                "Silakan muat ulang ulasan."
            )
        }, status=403)

    return JsonResponse({
        "success": True,
        "message": "Review berhasil dihapus!"
    })

# Mengambil ulasan dan menghitung rata-rata rating per restoran
def restaurant_reviews(request, restaurant_id):

    # Mengambil semua review aktif dari Surprise Box milik restoran
    reviews = Review.objects.filter(
        order__surprise_box__restaurant_id=restaurant_id,
        active=True
    ).select_related(
        "order__pembeli"
    ).order_by("-created_at")

    # Menghitung rata-rata rating dan jumlah ulasan restoran
    rata_rata = reviews.aggregate(
        Avg("rating")
    )["rating__avg"]

    jumlah_ulasan = reviews.count()

    # Menyiapkan data ulasan untuk ditampilkan
    data_reviews = []

    for review in reviews[:50]:
        data_reviews.append({
            # ID untuk menentukan review yang diedit atau dihapus
            "id": review.id,
            "nama":  review.order.pembeli.username,
            "rating": review.rating,
            "komentar": review.comment,
            "tanggal": review.created_at.strftime("%d/%m/%Y"),
            "owner_reply": review.owner_reply,

            # Balasan restoran
            "restaurant_name": (
                review.order.surprise_box.restaurant.nama
                if review.order.surprise_box_id else ""
            ),

            # Tombol Edit dan Hapus hanya muncul jika:
            # 1. Pengguna sudah login
            # 2. Pengguna merupakan pembeli
            # 3. Review merupakan milik pembeli tersebut
            # 4. Restoran belum membalas review
            "can_manage": (
                request.user.is_authenticated
                and request.user.is_buyer
                and review.order.pembeli_id == request.user.pk
                and not review.owner_reply.strip()
            )
        })

    # Mengirim data review restoran dalam format JSON
    return JsonResponse({
        "rata_rata": round(rata_rata, 1) if rata_rata is not None else 0,
        "jumlah_ulasan": jumlah_ulasan,
        "reviews": data_reviews
    })


# ============================================================
# MENAMPILKAN REVIEW UNTUK PEMILIK RESTORAN
# ============================================================

@login_required
@require_GET
def owner_restaurant_reviews(request, restaurant_id):

    # Hanya akun mitra restoran yang boleh mengakses halaman
    if not request.user.is_partner:
        raise PermissionDenied(
            "Hanya mitra restoran yang dapat melihat halaman ini."
        )

    # Mengambil restoran yang dimiliki oleh pengguna yang login
    restaurant = get_object_or_404(
        Restaurant,
        id=restaurant_id,
        owner_id=request.user.pk
    )

    # Mengambil review aktif milik restoran tersebut
    reviews = Review.objects.filter(
        order__surprise_box__restaurant=restaurant,
        active=True
    ).select_related(
        "order__pembeli"
    ).order_by("-created_at")

    # Menghitung rata-rata rating
    rata_rata = reviews.aggregate(
        Avg("rating")
    )["rating__avg"]

    # Menghitung jumlah review aktif
    jumlah_ulasan = reviews.count()

    # Menampilkan halaman ulasan untuk restoran
    return render(request, "review/owner_reviews.html", {
        "restaurant": restaurant,
        "reviews": reviews,
        "rata_rata": round(rata_rata, 1) if rata_rata is not None else 0,
        "jumlah_ulasan": jumlah_ulasan
    })

# ============================================================
# PEMILIK RESTORAN MEMBALAS REVIEW PEMBELI
# ============================================================

@login_required
@require_POST
def reply_review(request, review_id):

    # Hanya mitra restoran yang boleh membalas review
    if not request.user.is_partner:
        raise PermissionDenied(
            "Hanya mitra restoran yang boleh membalas review."
        )

    # Mengambil review yang masih aktif
    review = get_object_or_404(
        Review.objects.select_related(
            "order__surprise_box__restaurant"
        ),
        id=review_id,
        active=True
    )

    # Memastikan pesanan masih memiliki Surprise Box
    if review.order.surprise_box_id is None:
        raise PermissionDenied(
            "Restoran untuk review ini tidak ditemukan."
        )

    # Mengambil restoran yang menerima review
    restaurant = review.order.surprise_box.restaurant

    # Memastikan pengguna adalah pemilik restoran tersebut
    if restaurant.owner_id != request.user.pk:
        raise PermissionDenied(
            "Kamu bukan pemilik restoran ini."
        )

    # Mengambil isi balasan dari form
    balasan = request.POST.get("owner_reply", "").strip()

    # Balasan restoran tidak boleh kosong
    if not balasan:
        return JsonResponse({
            "success": False,
            "error": "Balasan restoran tidak boleh kosong."
        }, status=400) 

    # Membatasi panjang balasan
    if len(balasan) > 1000:
        return JsonResponse({
            "success": False,
            "error": "Balasan maksimal 1000 karakter."
        }, status=400)

    # Menyimpan balasan tanpa mengubah komentar pembeli
    updated = Review.objects.filter(
        id=review.id,
        active=True
    ).update(
        owner_reply=balasan
    )

    # Jika review ternyata sudah dinonaktifkan
    if not updated:
        return JsonResponse({
            "success": False,
            "error": "Review sudah tidak aktif."
        }, status=404)

    return JsonResponse({
        "success": True,
        "message": "Balasan restoran berhasil disimpan!",
        "owner_reply": balasan
    })
