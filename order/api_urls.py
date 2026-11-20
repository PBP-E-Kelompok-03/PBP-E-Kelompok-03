from rest_framework.routers import DefaultRouter

from .api import BoxViewSet, OrderViewSet

router = DefaultRouter()
router.register("boxes", BoxViewSet, basename="api-box")
router.register("orders", OrderViewSet, basename="api-order")

urlpatterns = router.urls
