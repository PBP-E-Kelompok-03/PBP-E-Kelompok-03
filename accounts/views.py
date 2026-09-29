from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import RegisterForm

# TODO: redirect ke landing page + url masih pakai food:list


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def logout_view(request):
    logout(request)
    return redirect("food:list")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("food:list")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("food:list")

    return render(request, "accounts/register.html", {"form": form})
