import requests
from authlib.integrations.base_client import OAuthError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import RegisterForm
from .google import fetch_google_keys
from .models import User
from .oauth import oauth


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    next_page = "landing"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["google_enabled"] = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
        return context


def google_login(request):
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        messages.error(request, "Login dengan Google belum dikonfigurasi.")
        return redirect("accounts:login")
    redirect_uri = request.build_absolute_uri(reverse("accounts:google_callback"))
    return oauth.google.authorize_redirect(request, redirect_uri)


def google_callback(request):
    keys = fetch_google_keys()
    if keys:
        oauth.google.server_metadata["jwks"] = keys
    try:
        token = oauth.google.authorize_access_token(request)
    except OAuthError:
        messages.error(request, "Login dengan Google gagal. Coba lagi.")
        return redirect("accounts:login")
    except requests.RequestException:
        messages.error(request, "Google sedang tidak bisa dihubungi. Masuk dengan username dan password.")
        return redirect("accounts:login")

    info = token.get("userinfo") or {}
    sub = info.get("sub")
    email = info.get("email") or ""
    if not sub or not email or not info.get("email_verified"):
        messages.error(request, "Akun Google kamu tidak punya email yang terverifikasi.")
        return redirect("accounts:login")

    username = f"google_{sub}"
    if User.objects.filter(email__iexact=email).exclude(username=username).exists():
        messages.error(request, "Email ini sudah dipakai akun lain. Masuk dengan username dan password.")
        return redirect("accounts:login")

    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "first_name": (info.get("name") or "")[:150]},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])

    login(request, user)
    return redirect("landing")


def logout_view(request):
    logout(request)
    return redirect("landing")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("landing")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("landing")

    return render(request, "accounts/register.html", {"form": form})
