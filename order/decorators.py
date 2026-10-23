from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Order


def _order_guard(check, message):
    def decorator(view):
        @wraps(view)
        def wrapper(request, order_id, *args, **kwargs):
            order = get_object_or_404(
                Order.objects.select_related("surprise_box__restaurant"), id=order_id
            )
            if not check(order, request.user):
                raise PermissionDenied(message)
            return view(request, order_id, *args, **kwargs)

        return wrapper

    return decorator


def _is_owner(order, user):
    return user.is_authenticated and order.pembeli_id == user.id


def _is_seller(order, user):
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    box = order.surprise_box
    return bool(box and box.restaurant.owner_id == user.id)


owner_required = _order_guard(_is_owner, "Kamu tidak berhak mengakses pesanan ini.")
seller_required = _order_guard(
    _is_seller, "Hanya pemilik restoran yang boleh menyelesaikan pesanan."
)
