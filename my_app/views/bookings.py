from __future__ import annotations

from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from my_app.models import Booking
from my_app.permissions import IsBookingParticipant, IsPropertyOwnerForBooking
from my_app.serializers import (
    BookingCreateSerializer,
    BookingReadSerializer,
    BookingStatusSerializer,
)


class BookingViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    create   POST /bookings/               — create booking (any authenticated user)
    list     GET  /bookings/               — my bookings (tenant sees own, landlord — bookings for their properties)
    retrieve GET  /bookings/{id}/          — detail view (booking participant)
    update_status PATCH /bookings/{id}/status/ — change booking status
    incoming  GET /bookings/incoming/      — landlord: incoming booking requests
    """

    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        qs = (
            Booking.objects.select_related("user", "property", "property__owner")
            .order_by("-created_at")
        )

        if self.action == "incoming":
            # Landlord views booking requests for their properties
            return qs.filter(property__owner=user)

        if self.action in ("retrieve", "update_status"):
            # Booking participants (checked at object permission level)
            return qs

        # list — свои брони + фильтр по статусу если передан
        qs = qs.filter(user=user)

        status_filter = self.request.query_params.get("status", "").lower()
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return BookingCreateSerializer
        if self.action == "update_status":
            return BookingStatusSerializer
        return BookingReadSerializer

    def get_permissions(self):
        if self.action == "retrieve":
            return [IsAuthenticated(), IsBookingParticipant()]
        if self.action == "update_status":
            return [IsAuthenticated()]   # detailed checks — inside serializer and action
        return [IsAuthenticated()]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create booking with select_for_update — protection against race conditions
        when multiple requests attempt to book the same dates simultaneously.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        prop = serializer.validated_data["property"]
        check_in = serializer.validated_data["check_in"]
        check_out = serializer.validated_data["check_out"]

        # Lock rows for the duration of the transaction — must evaluate the queryset
        list(
            Booking.objects.select_for_update().filter(
                property=prop,
                status__in=(Booking.Status.PENDING, Booking.Status.CONFIRMED),
                check_in__lt=check_out,
                check_out__gt=check_in,
            )
        )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, pk=None):
        """
        PATCH /bookings/{id}/status/
        - Landlord: pending → confirmed | rejected
        - Tenant:   confirmed → cancelled  (only if more than 1 day before check_out)
        Role validation is implemented in BookingStatusSerializer.validate_status().
        """
        booking = self.get_object()

        # Landlord can manage only bookings for their own properties
        if request.data.get("status") in (
            Booking.Status.CONFIRMED,
            Booking.Status.REJECTED,
        ):
            perm = IsPropertyOwnerForBooking()
            if not perm.has_object_permission(request, self, booking):
                return Response(
                    {"detail": perm.message},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = BookingStatusSerializer(
            booking, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="incoming")
    def incoming(self, request):
        """
        GET /bookings/incoming/
        Landlord only: list of incoming booking requests.
        Filter by status: ?status=pending|confirmed|rejected|cancelled
        """
        if request.user.role != "landlord":
            return Response(
                {"detail": "Only landlords can view incoming bookings."},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = self.get_queryset()
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = BookingReadSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = BookingReadSerializer(qs, many=True)
        return Response(serializer.data)
