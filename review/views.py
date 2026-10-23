
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Avg

from order.models import Order
from .models import Review
from .forms import ReviewForm


# Membuat review untuk pesanan yang sudah selesai
@login_required
def create_review(request, order_id):

    # Mengambil pesanan berdasarkan ID
    order = get_object_or_404(Order, id=order_id)

    # Memastikan pesanan milik pengguna yang sedang login
    if order.pembeli != request.user:
        raise PermissionDenied(
            "Kamu tidak boleh mereview pesanan orang lain."
        )

    # Review hanya boleh dibuat setelah pesanan selesai
    if order.status != Order.Status.COMPLETED:
        raise PermissionDenied(
            "Review hanya dapat diberikan setelah pesanan selesai."
        )

    # Mencegah satu pesanan memiliki lebih dari satu review
    if Review.objects.filter(order=order).exists():
        return JsonResponse({
            "error": "Pesanan ini sudah memiliki review."
        }, status=400)

    # Memproses data review yang dikirim pengguna
    if request.method == "POST":
        form = ReviewForm(request.POST)

        # Menyimpan review jika data sudah valid
        if form.is_valid():
            review = form.save(commit=False)
            review.order = order
            review.save()

            return JsonResponse({
                "success": True,
                "message": "Review berhasil dikirim!"
            })

        # Mengembalikan pesan jika form tidak valid
        return JsonResponse({
            "success": False,
            "errors": form.errors
        }, status=400)

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
            "nama": str(review.order.pembeli),
            "rating": review.rating,
            "komentar": review.comment,
            "tanggal": review.created_at.strftime("%d/%m/%Y")
        })

    # Mengirim data review ke frontend menggunakan JSON
    return JsonResponse({
        "rata_rata": round(rata_rata, 1) if rata_rata is not None else 0,
        "jumlah_ulasan": jumlah_ulasan,
        "reviews": data_reviews
    })


# Mengubah rating dan komentar review yang sudah dibuat
@login_required
def update_review(request, review_id):

    # Mengambil review aktif berdasarkan ID
    review = get_object_or_404(Review, id=review_id, active=True)

    # Memastikan review milik pengguna yang sedang login
    if review.order.pembeli != request.user:
        raise PermissionDenied(
            "Kamu tidak boleh mengedit review orang lain."
        )

    # Review hanya dapat diedit untuk pesanan selesai
    if review.order.status != Order.Status.COMPLETED:
        raise PermissionDenied(
            "Review hanya dapat diedit setelah pesanan selesai."
        )

    # Perubahan review hanya boleh dikirim menggunakan POST
    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "error": "Metode tidak diizinkan."
        }, status=405)

    # Mengisi form dengan review lama untuk diperbarui
    form = ReviewForm(request.POST, instance=review)

    # Menyimpan perubahan jika data valid
    if form.is_valid():
        form.save()

        return JsonResponse({
            "success": True,
            "message": "Review berhasil diperbarui!"
        })

    # Mengembalikan pesan jika data tidak valid
    return JsonResponse({
        "success": False,
        "errors": form.errors
    }, status=400)


