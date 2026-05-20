from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from my_app.serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    UserProfileSerializer,
)
from my_app.utils import clear_jwt_cookies, set_jwt_cookies

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """
    POST /auth/register/
    Register a new user. Available to everyone.
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)


class LoginView(APIView):
    """
    POST /auth/login/
    Login via email + password.
    Tokens are written to httpOnly cookies; only role and detail are returned in the body.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = CustomTokenObtainPairSerializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        # serializer.user is already populated after successful validation
        user = serializer.user

        response = Response(
            {
                "detail": "Login successful.",
                "role": user.role,
                "full_name": user.full_name,
            },
            status=status.HTTP_200_OK,
        )
        set_jwt_cookies(response, user)  # access + refresh → httpOnly cookies
        return response


class LogoutView(APIView):
    """
    POST /auth/logout/
    Reads refresh from cookie, blacklists it, clears both cookies.
    permission_classes = AllowAny — we read tokens from cookies ourselves,
    we do not rely on DRF authentication.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")  # read from cookie

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass  # token is already invalid — just clear cookies

        response = Response(
            {"detail": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )
        clear_jwt_cookies(response)
        return response


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET  /auth/me/ — current user profile
    PATCH /auth/me/ — update full_name
    """
    serializer_class = UserProfileSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user