from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated

from my_app.models import Property
from my_app.models import Review
from my_app.permissions import IsOwnerOrReadOnly
from my_app.serializers import ReviewReadSerializer, ReviewWriteSerializer


class ReviewViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    list    GET  /properties/{property_pk}/reviews/     — all reviews (AllowAny)
    create  POST /properties/{property_pk}/reviews/     — create review (IsAuthenticated)
    update  PATCH /properties/{property_pk}/reviews/{id}/ — own review only
    destroy DELETE /properties/{property_pk}/reviews/{id}/ — own review only
    """

    def get_queryset(self):
        return (
            Review.objects.select_related("user", "property")
            .filter(property_id=self.kwargs["property_pk"])
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ReviewWriteSerializer
        return ReviewReadSerializer

    def get_permissions(self):
        if self.action == "list":
            return [AllowAny()]
        if self.action == "create":
            return [IsAuthenticated()]
        # update, destroy — author only
        return [IsAuthenticated(), IsOwnerOrReadOnly()]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["property"] = get_object_or_404(Property, pk=self.kwargs["property_pk"])
        return ctx

    def perform_create(self, serializer):
        prop = self.get_serializer_context()["property"]
        serializer.save(user=self.request.user, property=prop)