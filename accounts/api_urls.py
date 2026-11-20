from django.urls import path

from . import api

urlpatterns = [
    path("login/", api.login_api),
    path("register/", api.register_api),
    path("logout/", api.logout_api),
    path("me/", api.me_api),
]
