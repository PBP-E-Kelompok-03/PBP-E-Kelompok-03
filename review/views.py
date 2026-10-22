
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

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
