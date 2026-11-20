from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse

LOGIN_LIMIT = 10
LOGIN_WINDOW = 300


def client_ip(request):
    """ambil ip pengunjung, utamakan header x-forwarded-for dari proxy"""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def rate_limit(scope, limit, window, key_func=client_ip):
    """batasi post per ip: lebih dari limit dalam window detik dijawab 429"""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method != "POST":
                return view(request, *args, **kwargs)
            key = f"rl:{scope}:{key_func(request)}"
            cache.add(key, 0, window)
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, window)
                count = 1
            if count > limit:
                return HttpResponse("Terlalu banyak percobaan. Coba lagi nanti.", status=429)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
