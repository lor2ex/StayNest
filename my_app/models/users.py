from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        LANDLORD = 'landlord', 'Landlord'
        TENANT = 'tenant', 'Tenant'

    username = None
    email = models.EmailField(max_length=80, unique=True)
    full_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=15, choices=Role)
    deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["role"]

    def __str__(self):
        return self.email

    def delete(self, using=None, keep_parents=False):
        self.deleted = True
        self.deleted_at = timezone.now()
        self.save()

    class Meta:
        db_table = "users"