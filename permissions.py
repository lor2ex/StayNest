from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsLandlord(BasePermission):
    """Only the landlord (any action)."""
    message = "Only landlords can perform this action."

    def has_permission(self, request, view) -> bool:
        return (
            request.user.is_authenticated
            and request.user.role == "landlord"
            and not request.user.deleted
        )


class IsLandlordOwner(BasePermission):
    """The landlord, and only the owner of the specific listing."""
    message = "You can only modify your own properties."

    def has_object_permission(self, request, view, obj) -> bool:
        return obj.owner_id == request.user.pk


class IsOwnerOrReadOnly(BasePermission):
    """Only the creator of an object can edit it; anyone can read it."""
    message = "You can only edit your own content."

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        return obj.user_id == request.user.pk


class IsBookingParticipant(BasePermission):
    """
    The following users can view a reservation:
        - the renter who created it (booking.user)
        - the property owner whose listing it is (booking.property.owner)
    """
    message = "You are not a participant of this booking."

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        return obj.user_id == user.pk or obj.property.owner_id == user.pk


class IsPropertyOwnerForBooking(BasePermission):
    """Only the host of this listing can confirm or cancel a reservation."""
    message = "Only the property owner can confirm or reject bookings."

    def has_object_permission(self, request, view, obj) -> bool:
        return obj.property.owner_id == request.user.pk
