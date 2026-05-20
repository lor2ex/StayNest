from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from my_app.models import Booking, Property
from my_app.serializers.auth import UserPublicSerializer
from my_app.serializers.properties import PropertyListSerializer


class BookingReadSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    property = PropertyListSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id",
            "user",
            "property",
            "check_in",
            "check_out",
            "status",
            "checked_in",
            "created_at",
        )


class BookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ("id", "property", "check_in", "check_out")
        read_only_fields = ("id",)

    def validate(self, attrs: dict) -> dict:
        user = self.context["request"].user
        prop: Property = attrs["property"]
        check_in = attrs["check_in"]
        check_out = attrs["check_out"]

        if check_in >= check_out:
            raise serializers.ValidationError(
                {"check_out": "Check-out must be after check-in."}
            )
        if check_in < timezone.localdate():
            raise serializers.ValidationError(
                {"check_in": "Check-in date cannot be in the past."}
            )

        if not prop.is_active:
            raise serializers.ValidationError(
                {"property": "This property is not available for booking."}
            )

        if prop.owner_id == user.pk:
            raise serializers.ValidationError(
                {"property": "You cannot book your own property."}
            )

        overlapping = Booking.objects.filter(
            property=prop,
            status__in=(Booking.Status.PENDING, Booking.Status.CONFIRMED),
            check_in__lt=check_out,
            check_out__gt=check_in,
        )
        if self.instance:
            overlapping = overlapping.exclude(pk=self.instance.pk)
        if overlapping.exists():
            raise serializers.ValidationError(
                "Selected dates are already taken for this property."
            )

        return attrs

    def create(self, validated_data: dict) -> Booking:
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class BookingStatusSerializer(serializers.ModelSerializer):
    """PATCH — landlord confirms/rejects; tenant cancels."""

    class Meta:
        model = Booking
        fields = ("id", "status")
        read_only_fields = ("id",)

    def validate_status(self, value: str) -> str:
        instance: Booking = self.instance
        request_user = self.context["request"].user
        is_landlord = request_user.role == "landlord"
        is_tenant = request_user == instance.user

        # A landlord can only act on bookings for their own properties
        if is_landlord and instance.property.owner_id != request_user.pk:
            raise serializers.ValidationError(
                "You can only manage bookings for your own properties."
            )

        # Role-based transition matrix
        allowed_transitions: dict[str, set[str]] = {}

        if is_landlord:
            allowed_transitions = {
                Booking.Status.PENDING: {
                    Booking.Status.CONFIRMED,
                    Booking.Status.REJECTED,
                },
            }
        elif is_tenant:
            allowed_transitions = {
                Booking.Status.PENDING: {Booking.Status.CANCELLED},
                Booking.Status.CONFIRMED: {Booking.Status.CANCELLED},
            }

        if instance.status not in allowed_transitions:
            raise serializers.ValidationError(
                f"Cannot change status from \"{instance.status}\" with your role."
            )
        if value not in allowed_transitions[instance.status]:
            raise serializers.ValidationError(
                f"Transition \"{instance.status}\" → \"{value}\" is not allowed."
            )

        # Tenant cannot cancel less than 1 day before check-out
        if value == Booking.Status.CANCELLED and is_tenant:
            delta = instance.check_out - timezone.localdate()
            if delta.days <= 1:
                raise serializers.ValidationError(
                    "Cancellation is only allowed more than 1 day before check-out."
                )

        return value