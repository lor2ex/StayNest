from __future__ import annotations

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from my_app.models import PropertyView, SearchQuery
from my_app.serializers import PropertyViewSerializer, SearchQuerySerializer


class MyViewHistoryView(generics.ListAPIView):
    """
    GET /stats/views/
    View history of the current user.
    Listings with the highest views_count appear first.
    """
    serializer_class = PropertyViewSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return (
            PropertyView.objects
            .filter(user=self.request.user)
            .select_related("property", "property__owner")
            .order_by("-property__views_count")
        )


class MySearchHistoryView(generics.ListAPIView):
    """
    GET /stats/searches/
    Search query history of the current user.
    The most frequent queries appear first.
    """
    serializer_class = SearchQuerySerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return (
            SearchQuery.objects
            .filter(user=self.request.user)
            .order_by("-count", "-last_searched_at")
        )