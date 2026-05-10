from rest_framework import serializers

from models import PropertyView, SearchQuery
from serializers import PropertyListSerializer


class PropertyViewSerializer(serializers.ModelSerializer):
    property = PropertyListSerializer(read_only=True)

    class Meta:
        model = PropertyView
        fields = ("id", "property", "created_at", "last_viewed_at")
        read_only_fields = fields


class SearchQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchQuery
        fields = ("id", "term", "count", "last_searched_at")
        read_only_fields = ("id", "count", "last_searched_at")