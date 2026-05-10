from __future__ import annotations

from rest_framework import serializers

from my_app.models import Property
from serializers import UserPublicSerializer


class PropertyListSerializer(serializers.ModelSerializer):
    """Lightweight — used in list/search responses."""

    owner = UserPublicSerializer(read_only=True)
    avg_rating = serializers.FloatField(read_only=True, default=None)

    class Meta:
        model = Property
        fields = (
            "id",
            "owner",
            "title",
            "city",
            "district",
            "price",
            "rooms",
            "type",
            "is_active",
            "views_count",
            "avg_rating",
            "date_created",
        )


class PropertyDetailSerializer(serializers.ModelSerializer):
    """Full detail — used on retrieve."""

    owner = UserPublicSerializer(read_only=True)
    avg_rating = serializers.FloatField(read_only=True, default=None)
    reviews_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Property
        fields = (
            "id",
            "owner",
            "title",
            "description",
            "city",
            "district",
            "location",
            "price",
            "rooms",
            "type",
            "is_active",
            "views_count",
            "avg_rating",
            "reviews_count",
            "date_created",
        )
        read_only_fields = ("id", "owner", "views_count", "date_created")


class PropertyWriteSerializer(serializers.ModelSerializer):
    """Create / Update — used by landlords only."""

    class Meta:
        model = Property
        fields = (
            "id",
            "title",
            "description",
            "city",
            "district",
            "location",
            "price",
            "rooms",
            "type",
            "is_active",
        )
        read_only_fields = ("id",)

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def validate_rooms(self, value):
        if value <= 0:
            raise serializers.ValidationError("Number of rooms must be at least 1.")
        return value


class PropertyAvailabilitySerializer(serializers.ModelSerializer):
    """PATCH /properties/{id}/toggle-availability/ — only is_active."""

    class Meta:
        model = Property
        fields = ("id", "is_active")
        read_only_fields = ("id",)