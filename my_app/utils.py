from datetime import datetime, timezone

from django.http import HttpResponse
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from config import settings
from my_app.models import User

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
COOKIE_HTTPONLY = True
COOKIE_SECURE = not settings.DEBUG # False in dev, True in prod.
COOKIE_SAMESITE = "Lax"
COOKIE_PATH = "/"


def get_token_expiry_datetime(token: AccessToken | RefreshToken) -> datetime:
    return datetime.fromtimestamp(int(token["exp"]), tz=timezone.utc)


def build_cookie_kwargs(expires: datetime) -> dict[str, object]:
    return {
        "httponly": COOKIE_HTTPONLY,
        "secure": COOKIE_SECURE,
        "samesite": COOKIE_SAMESITE,
        "path": COOKIE_PATH,
        "expires": expires,
    }


def set_access_cookie(response: HttpResponse, access_token: str) -> None:
    token = AccessToken(access_token)

    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        **build_cookie_kwargs(get_token_expiry_datetime(token))
    )


def set_refresh_cookie(response: HttpResponse, refresh_token: str) -> None:
    token = RefreshToken(refresh_token)

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        **build_cookie_kwargs(get_token_expiry_datetime(token))
    )


def set_jwt_cookies(response: HttpResponse, user: User) -> None:
    refresh_token = RefreshToken.for_user(user)
    access_token = refresh_token.access_token

    set_access_cookie(response, str(access_token))
    set_refresh_cookie(response, str(refresh_token))


def clear_jwt_cookies(response: HttpResponse) -> None:
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path=COOKIE_PATH)
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=COOKIE_PATH)
