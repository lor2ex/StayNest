from django.db import models
from django.conf import settings


class PropertyView(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="property_views",
    )
    property = models.ForeignKey(
        "my_app.Property",
        on_delete=models.CASCADE,
        related_name="views",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_viewed_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user} viewed {self.property}"

    class Meta:
        db_table = "property_views"
        ordering = ["-last_viewed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "property"],
                name="unique_user_property_view",
            )
        ]


class SearchQuery(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="search_queries",
    )
    term = models.CharField(max_length=255)
    count = models.PositiveIntegerField(default=1)
    last_searched_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user}: {self.term} ({self.count})"

    class Meta:
        db_table = "search_queries"
        ordering = ["-last_searched_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "term"],
                name="unique_user_search_term",
            )
        ]