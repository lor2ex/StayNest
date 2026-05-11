from django.urls import include, path
from django.contrib import admin
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from my_app.views.auth import LoginView, LogoutView, MeView, RegisterView
from my_app.views.bookings import BookingViewSet
from my_app.views.properties import PropertyViewSet
from my_app.views.reviews import ReviewViewSet
from my_app.views.stats import MySearchHistoryView, MyViewHistoryView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView
)


router = DefaultRouter()
router.register(r"properties", PropertyViewSet, basename="property")
router.register(r"bookings", BookingViewSet, basename="booking")

# Nested route for reviews: /properties/{property_pk}/reviews/
reviews_router = DefaultRouter()
reviews_router.register(r"reviews", ReviewViewSet, basename="review")


urlpatterns = [
    path('admin/', admin.site.urls),
    # ── Auth ───
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    # ── Properties + Reviews (nested) ──
    path("", include(router.urls)),
    path("properties/<int:property_pk>/", include(reviews_router.urls),),
    # ── Stats ───
    path("stats/views/", MyViewHistoryView.as_view(), name="stats-views"),
    path("stats/searches/", MySearchHistoryView.as_view(), name="stats-searches"),
    # ── Swagger ───
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
