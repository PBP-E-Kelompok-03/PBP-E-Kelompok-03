from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from django.db.models import Avg
from django.core.exceptions import ValidationError

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from order.models import Order
from .models import Review


# Menampilkan review berdasarkan Surprise Box
@api_view(["GET"])
@permission_classes([AllowAny])
def api_list_reviews(request, surprise_box_id):
    reviews = Review.objects.filter(
        order__surprise_box_id=surprise_box_id,
        active=True
    ).select_related("order__pembeli").order_by("-created_at")

    rata_rata = reviews.aggregate(
        Avg("rating")
    )["rating__avg"]

    data_reviews = [
        {
            "id": review.id,
            "nama": review.order.pembeli.username,
            "rating": review.rating,
            "komentar": review.comment,
            "tanggal": review.created_at.strftime("%d/%m/%Y"),
            "owner_reply": review.owner_reply,
        }
        for review in reviews[:50]
    ]

    return Response({
        "rata_rata": round(rata_rata, 1) if rata_rata is not None else 0,
        "jumlah_ulasan": reviews.count(),
        "reviews": data_reviews,
    })


# Membuat review untuk pesanan yang sudah selesai
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_create_review(request, order_id):
    if not request.user.is_buyer:
        return Response(
            {"error": "Hanya pembeli yang boleh membuat review."},
            status=status.HTTP_403_FORBIDDEN
        )

    order = get_object_or_404(Order, pk=order_id)

    if order.pembeli_id != request.user.pk:
        return Response(
            {"error": "Pesanan bukan milik kamu."},
            status=status.HTTP_403_FORBIDDEN
        )

    if order.status != Order.Status.COMPLETED:
        return Response(
            {"error": "Pesanan belum selesai."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        rating = int(request.data.get("rating", 0))
    except (TypeError, ValueError):
        return Response(
            {"error": "Rating harus berupa angka 1 sampai 5."},
            status=status.HTTP_400_BAD_REQUEST
        )

    comment = request.data.get("comment", "")

    if not 1 <= rating <= 5:
        return Response(
            {"error": "Rating harus antara 1 sampai 5."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not isinstance(comment, str) or not comment.strip():
        return Response(
            {"error": "Komentar tidak boleh kosong."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(),
                pk=order_id
            )

            if order.pembeli_id != request.user.pk:
                return Response(
                    {"error": "Pesanan bukan milik kamu."},
                    status=status.HTTP_403_FORBIDDEN
                )

            if order.status != Order.Status.COMPLETED:
                return Response(
                    {"error": "Pesanan belum selesai."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if Review.objects.filter(order=order).exists():
                return Response(
                    {"error": "Pesanan sudah memiliki review."},
                    status=status.HTTP_409_CONFLICT
                )

            review = Review(
                order=order,
                rating=rating,
                comment=comment.strip()
            )
            review.save()

    except IntegrityError:
        return Response(
            {"error": "Pesanan sudah memiliki review."},
            status=status.HTTP_409_CONFLICT
        )
    except ValidationError as error:
        return Response(
            {"error": error.messages},
            status=status.HTTP_400_BAD_REQUEST
        )

    return Response(
        {
            "success": True,
            "message": "Review berhasil dikirim!",
            "review_id": review.id,
        },
        status=status.HTTP_201_CREATED
    )