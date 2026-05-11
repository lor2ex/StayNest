from __future__ import annotations

from django.db.models import Avg, Count, F, Q
from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from my_app.models import Property, PropertyView, SearchQuery
from my_app.permissions import IsLandlord, IsLandlordOwner
from my_app.serializers import (
    PropertyAvailabilitySerializer,
    PropertyDetailSerializer,
    PropertyListSerializer,
    PropertyWriteSerializer,
)


class PropertyViewSet(viewsets.ModelViewSet):
    """
    list   GET  /properties/          — list of active listings
    create POST /properties/          — create (landlord only)
    retrieve GET /properties/{id}/    — detail view + view counter
    update  PUT/PATCH /properties/{id}/ — edit (own listings only)
    destroy DELETE /properties/{id}/  — delete (own listings only)
    toggle  PATCH /properties/{id}/toggle/ — toggle listing on/off

    Filtering: city, district, type, is_active
    Ranges:    price_min, price_max, rooms_min, rooms_max
    Search:    ?search=  (by title and description)
    Ordering:  ?ordering= price | -price | date_created | -date_created | views_count | -views_count | avg_rating
    """

    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)

    # Keyword search
    search_fields = ("title", "description")

    # Exact value filtering
    filterset_fields = ("city", "district", "type", "is_active")

    # Ordering
    ordering_fields = ("price", "date_created", "views_count", "avg_rating")
    ordering = ("-date_created",)

    def get_queryset(self):
        qs = (
            Property.objects.select_related("owner")
            .annotate(
                avg_rating=Avg("reviews__rating"),
                reviews_count=Count("reviews"),
            )
        )

        # Regular users see only active listings; owners see all their own listings
        user = self.request.user
        if not (user.is_authenticated and user.role == "landlord"):
            qs = qs.filter(is_active=True)
        elif self.action == "list":
            # Landlords see all active listings + their own inactive ones in the list
            qs = qs.filter(Q(is_active=True) | Q(owner=user))

        # Range filters
        params = self.request.query_params
        if price_min := params.get("price_min"):
            qs = qs.filter(price__gte=price_min)
        if price_max := params.get("price_max"):
            qs = qs.filter(price__lte=price_max)
        if rooms_min := params.get("rooms_min"):
            qs = qs.filter(rooms__gte=rooms_min)
        if rooms_max := params.get("rooms_max"):
            qs = qs.filter(rooms__lte=rooms_max)

        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PropertyDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return PropertyWriteSerializer
        if self.action == "toggle":
            return PropertyAvailabilitySerializer
        return PropertyListSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsLandlord()]
        if self.action in ("update", "partial_update", "destroy", "toggle"):
            return [IsLandlord(), IsLandlordOwner()]
        # list, retrieve — accessible by everyone (including anonymous users for reading)
        return [IsAuthenticatedOrReadOnly()]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        """
        Detail view of a listing.
        If the user is authenticated, record the view (preventing artificial inflation).
        """
        instance = self.get_object()

        if request.user.is_authenticated:
            view_obj, created = PropertyView.objects.get_or_create(
                user=request.user,
                property=instance,
            )
            if created:
                # Atomic increment only on the first view
                Property.objects.filter(pk=instance.pk).update(
                    views_count=F("views_count") + 1
                )
                instance.refresh_from_db(fields=["views_count"])
            else:
                # Update the last viewed timestamp without incrementing the counter
                PropertyView.objects.filter(pk=view_obj.pk).update(
                    last_viewed_at=timezone.now()
                )

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        """
        List of listings.
        If authenticated and ?search= is provided, save the search query.
        """
        response = super().list(request, *args, **kwargs)

        if request.user.is_authenticated:
            term = request.query_params.get("search", "").strip().lower()
            if term:
                obj, created = SearchQuery.objects.get_or_create(
                    user=request.user,
                    term=term,
                    defaults={"count": 1},
                )
                if not created:
                    SearchQuery.objects.filter(pk=obj.pk).update(
                        count=F("count") + 1
                    )

        return response

    @action(detail=True, methods=["patch"], url_path="toggle")
    def toggle(self, request, pk=None):
        """PATCH /properties/{id}/toggle/ — toggle the is_active status."""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)