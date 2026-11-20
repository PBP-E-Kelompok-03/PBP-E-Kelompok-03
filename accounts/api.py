from django.contrib.auth import authenticate, login, logout
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .forms import RegisterForm
from .ratelimit import LOGIN_LIMIT, LOGIN_WINDOW, rate_limit


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    role = serializers.CharField()


@rate_limit("login", LOGIN_LIMIT, LOGIN_WINDOW, as_json=True)
@api_view(["POST"])
@permission_classes([AllowAny])
def login_api(request):
    user = authenticate(
        request,
        username=request.data.get("username", ""),
        password=request.data.get("password", ""),
    )
    if user is None or not user.is_active:
        return Response({"status": False, "message": "Username atau password salah."}, status=status.HTTP_401_UNAUTHORIZED)
    login(request, user)
    return Response({"status": True, "message": "Login berhasil.", **UserSerializer(user).data})


@rate_limit("register", LOGIN_LIMIT, LOGIN_WINDOW, as_json=True)
@api_view(["POST"])
@permission_classes([AllowAny])
def register_api(request):
    data = {
        "username": request.data.get("username", ""),
        "password1": request.data.get("password1", ""),
        "password2": request.data.get("password2", ""),
        "role": request.data.get("role", "buyer"),
    }
    form = RegisterForm(data)
    if not form.is_valid():
        errors = " ".join(msg for msgs in form.errors.values() for msg in msgs)
        return Response({"status": False, "message": errors}, status=status.HTTP_400_BAD_REQUEST)
    user = form.save()
    return Response(
        {"status": True, "message": "Akun berhasil dibuat.", **UserSerializer(user).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def logout_api(request):
    logout(request)
    return Response({"status": True, "message": "Logout berhasil."})


@api_view(["GET"])
def me_api(request):
    return Response(UserSerializer(request.user).data)
