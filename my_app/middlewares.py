import time
from typing import Callable

from django.http import HttpRequest, HttpResponse
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from my_app.utils import clear_jwt_cookies, set_access_cookie, ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME


class JWTMiddleware:
    excluded_paths = {
        "/auth/login/",
        "/auth/register/",
        "/auth/token/refresh/",
    }

    excluded_path_prefixes = (
        "/admin/",
    )

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.refresh_window_seconds = self._build_refresh_window_seconds()

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self._should_skip(request):
            return self.get_response(request)

        access_token = self._get_access_cookie(request)
        refresh_token = self._get_refresh_cookie(request)

        minted_access_token: str | None = None
        should_clear_auth_cookies = False

        if self._has_auth_cookies(access_token, refresh_token):

            if not self._is_refresh_token_valid(refresh_token):
                should_clear_auth_cookies = True

            elif access_token and not self._is_access_expiring(access_token):
                self._set_authorization_header(request, access_token)

            else:
                minted_access_token = self._mint_access_token(refresh_token)

                if minted_access_token:
                    self._set_authorization_header(request, minted_access_token)
                else:
                    should_clear_auth_cookies = True

        response = self.get_response(request)

        if should_clear_auth_cookies:
            clear_jwt_cookies(response)
        elif minted_access_token:
            set_access_cookie(response, minted_access_token)

        return response

    def _build_refresh_window_seconds(self) -> int:
        access_lifetime_seconds = int(
            api_settings.ACCESS_TOKEN_LIFETIME.total_seconds()
        )
        return max(1, min(30, access_lifetime_seconds // 4))

    def _should_skip(self, request: HttpRequest) -> bool:
        return request.path in self.excluded_paths or request.path.startswith(
            self.excluded_path_prefixes
        )

    def _has_auth_cookies(
        self,
        access_token: str | None,
        refresh_token: str | None,
    ) -> bool:
        return bool(access_token or refresh_token)

    def _get_access_cookie(self, request: HttpRequest) -> str | None:
        return request.COOKIES.get(ACCESS_COOKIE_NAME)

    def _get_refresh_cookie(self, request: HttpRequest) -> str | None:
        return request.COOKIES.get(REFRESH_COOKIE_NAME)

    def _set_authorization_header(
        self,
        request: HttpRequest,
        access_token: str,
    ) -> None:
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"

    def _is_refresh_token_valid(self, refresh_token: str | None) -> bool:
        if not refresh_token:
            return False

        try:
            RefreshToken(refresh_token)
            return True

        except TokenError:
            return False

        except Exception:
            return False

    def _mint_access_token(self, refresh_token: str | None) -> str | None:
        if not refresh_token:
            return None

        try:
            refresh = RefreshToken(refresh_token)
            return str(refresh.access_token)

        except TokenError:
            return None

        except Exception:
            return None

    def _is_access_expiring(self, access_token: str) -> bool:
        try:
            token = AccessToken(access_token)
            exp_timestamp = int(token["exp"])
            now_timestamp = int(time.time())
            return exp_timestamp <= now_timestamp + self.refresh_window_seconds

        except Exception:
            return True