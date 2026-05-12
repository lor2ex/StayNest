from django.utils import timezone
from rest_framework import serializers
from django.db import IntegrityError

from my_app.models import Booking, Property, Review
from my_app.serializers.auth import UserPublicSerializer


class ReviewReadSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ("id", "user", "property", "rating", "comment", "created_at")


class ReviewWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ("id", "property", "rating", "comment")
        read_only_fields = ("id",)

    def validate(self, attrs: dict) -> dict:
        user = self.context["request"].user
        prop: Property = attrs.get("property", getattr(self.instance, "property", None))

        has_valid_stay = Booking.objects.filter(
            user=user,
            property=prop,
            status=Booking.Status.CONFIRMED,
            check_in__lte=timezone.localdate(),
        ).exists()

        if not has_valid_stay:
            raise serializers.ValidationError(
                "You can only review a property after a confirmed stay."
            )

        return attrs

    def create(self, validated_data: dict) -> Review:
        validated_data["user"] = self.context["request"].user
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {"non_field_errors": "You have already reviewed this property."}
            )