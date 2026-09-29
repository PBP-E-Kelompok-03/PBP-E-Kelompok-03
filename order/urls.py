from django.urls import path

from . import views

app_name = "order"

urlpatterns = [
    path("history/", views.order_history, name="history"),
    path("create/<int:box_id>/", views.create_order, name="create"),
    path("<int:order_id>/cancel/", views.cancel_order, name="cancel"),
]
