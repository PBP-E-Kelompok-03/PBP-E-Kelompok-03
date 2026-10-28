import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.db.models import Q

from .models import Restaurant, SurpriseBox

logger = logging.getLogger(__name__)


class FoodApiClientError(Exception):
    """Base exception class for FoodApiClient errors."""
    pass


class FoodApiTimeoutError(FoodApiClientError):
    """Raised when an API call times out."""
    pass


class FoodApiClient:
    """
    API Client Wrapper untuk modul Food & Restaurant.
    
    Fitur utama:
    - Timeout: Membatasi durasi panggilan jaringan/eksternal agar thread tidak menggantung.
    - Caching: Memanfaatkan Django Cache Framework (dengan TTL default 300 detik) untuk efisiensi.
    - Fallback: Menangani timeout/network error dengan mengembalikan data aman (cached atau structured default)
      sehingga aplikasi tetap tangguh (tidak menyebabkan HTTP 500).
    """

    DEFAULT_TIMEOUT: float = 5.0
    DEFAULT_CACHE_TTL: int = 300  # 5 menit

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, cache_ttl: int = DEFAULT_CACHE_TTL):
        self.timeout = timeout
        self.cache_ttl = cache_ttl

    def _cache_get(self, key: str) -> Optional[Any]:
        try:
            return cache.get(key)
        except Exception as e:
            logger.warning(f"Cache get error for key '{key}': {e}")
            return None

    def _cache_set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        try:
            cache.set(key, value, ttl or self.cache_ttl)
        except Exception as e:
            logger.warning(f"Cache set error for key '{key}': {e}")

    def fetch_url(
        self,
        url: str,
        timeout: Optional[float] = None,
        use_cache: bool = True,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Melakukan HTTP request ke endpoint eksternal/internal dengan timeout, cache, dan fallback.
        """
        eff_timeout = timeout if timeout is not None else self.timeout
        cache_key = f"food:api_fetch:{url}"

        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return {
                    "data": cached,
                    "from_cache": True,
                    "status_code": 200,
                    "error": None,
                    "fallback": False,
                }

        req_headers = {
            "User-Agent": "DibuangSayang-FoodApiClient/1.0",
            "Accept": "application/json",
        }
        if headers:
            req_headers.update(headers)

        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=eff_timeout) as response:
                status_code = response.getcode()
                raw_body = response.read().decode("utf-8")
                data = json.loads(raw_body)
                if use_cache and status_code == 200:
                    self._cache_set(cache_key, data)
                return {
                    "data": data,
                    "from_cache": False,
                    "status_code": status_code,
                    "error": None,
                    "fallback": False,
                }
        except (socket.timeout, TimeoutError) as e:
            logger.warning(f"Timeout calling {url} after {eff_timeout}s: {e}")
            fallback_data = self._cache_get(cache_key) or {}
            return {
                "data": fallback_data,
                "from_cache": bool(fallback_data),
                "status_code": 504,
                "error": "timeout",
                "fallback": True,
            }
        except urllib.error.HTTPError as e:
            logger.warning(f"HTTP error {e.code} calling {url}: {e}")
            fallback_data = self._cache_get(cache_key) or {}
            return {
                "data": fallback_data,
                "from_cache": bool(fallback_data),
                "status_code": e.code,
                "error": str(e),
                "fallback": True,
            }
        except urllib.error.URLError as e:
            logger.warning(f"Network URLError calling {url}: {e}")
            fallback_data = self._cache_get(cache_key) or {}
            return {
                "data": fallback_data,
                "from_cache": bool(fallback_data),
                "status_code": 503,
                "error": str(e.reason),
                "fallback": True,
            }
        except Exception as e:
            logger.error(f"Unexpected error calling {url}: {e}")
            fallback_data = self._cache_get(cache_key) or {}
            return {
                "data": fallback_data,
                "from_cache": bool(fallback_data),
                "status_code": 500,
                "error": str(e),
                "fallback": True,
            }

    def get_restaurants(
        self,
        query: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Mengambil daftar restoran aktif dari model database (ORM),
        dengan dukungan cache dan fallback list kosong jika query database gagal.
        """
        cache_key = f"food:restaurants:q_{query or 'all'}"
        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        try:
            qs = Restaurant.objects.filter(is_active=True)
            if query:
                qs = qs.filter(Q(nama__icontains=query) | Q(alamat__icontains=query))

            results = [
                {
                    "id": r.id,
                    "nama": r.nama,
                    "alamat": r.alamat,
                    "lat": float(r.lat) if r.lat is not None else None,
                    "lng": float(r.lng) if r.lng is not None else None,
                    "jam_buka": r.jam_buka.strftime("%H:%M") if r.jam_buka else None,
                    "jam_tutup": r.jam_tutup.strftime("%H:%M") if r.jam_tutup else None,
                }
                for r in qs
            ]
            if use_cache:
                self._cache_set(cache_key, results)
            return results
        except Exception as e:
            logger.error(f"Error querying restaurants from DB: {e}")
            return self._cache_get(cache_key) or []

    def get_restaurant_detail(
        self,
        restaurant_id: int,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Mengambil informasi detail restoran dari model database Restaurant (ORM).
        """
        cache_key = f"food:restaurant:{restaurant_id}"
        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        try:
            r = Restaurant.objects.filter(id=restaurant_id, is_active=True).first()
            if not r:
                return None
            result = {
                "id": r.id,
                "nama": r.nama,
                "alamat": r.alamat,
                "lat": float(r.lat) if r.lat is not None else None,
                "lng": float(r.lng) if r.lng is not None else None,
                "jam_buka": r.jam_buka.strftime("%H:%M") if r.jam_buka else None,
                "jam_tutup": r.jam_tutup.strftime("%H:%M") if r.jam_tutup else None,
            }
            if use_cache:
                self._cache_set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Error querying restaurant {restaurant_id} from DB: {e}")
            return self._cache_get(cache_key)

    def get_surprise_boxes(
        self,
        restaurant_id: Optional[int] = None,
        query: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Mengambil daftar paket surprise box aktif dari model SurpriseBox (ORM).
        """
        cache_key = f"food:boxes:r_{restaurant_id or 'all'}_q_{query or 'all'}"
        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached

        try:
            qs = SurpriseBox.objects.filter(
                is_active=True,
                restaurant__is_active=True,
            ).select_related("restaurant")

            if restaurant_id:
                qs = qs.filter(restaurant_id=restaurant_id)
            if query:
                qs = qs.filter(
                    Q(nama_paket__icontains=query) | Q(restaurant__nama__icontains=query)
                )

            results = [
                {
                    "id": b.id,
                    "restaurant_id": b.restaurant.id,
                    "restaurant_nama": b.restaurant.nama,
                    "nama_paket": b.nama_paket,
                    "harga_normal": float(b.harga_normal),
                    "harga_diskon": float(b.harga_diskon),
                    "diskon_persen": b.diskon_persen,
                    "stok": b.stok,
                }
                for b in qs
            ]
            if use_cache:
                self._cache_set(cache_key, results)
            return results
        except Exception as e:
            logger.error(f"Error querying surprise boxes from DB: {e}")
            return self._cache_get(cache_key) or []
