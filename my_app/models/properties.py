from django.db import models
from django.conf import settings


class Property(models.Model):
    class Type(models.TextChoices):
        APARTMENT = "apartment", "Apartment"
        HOUSE = "house", "House"
        STUDIO = "studio", "Studio"
        ROOM = "room", "Room"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="properties",
    )
    title = models.CharField(max_length=200)
    description = models.TextField()

    city = models.CharField(max_length=100)
    district = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    rooms = models.PositiveSmallIntegerField()

    type = models.CharField(
        max_length=20,
        choices=Type,
    )

    is_active = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)
    views_count = models.PositiveIntegerField(default=0, db_index=True)

    def __str__(self) -> str:
        return f"{self.title} ({self.city})"

    class Meta:
        db_table = "properties"
        ordering = ["-date_created"]