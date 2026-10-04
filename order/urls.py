from django.urls import path

from . import views

app_name = "order"

urlpatterns = [
    path("history/", views.order_history, name="history"),
    path("incoming/", views.incoming_orders, name="incoming"),
    path("checkout/<int:box_id>/", views.checkout_view, name="checkout"),
    path("create/<int:box_id>/", views.create_order, name="create"),
    path("<int:order_id>/cancel/", views.cancel_order, name="cancel"),
    path("<int:order_id>/complete/", views.complete_order, name="complete"),
    path("<int:order_id>/confirmation/", views.order_confirmation, name="confirmation"),
]
