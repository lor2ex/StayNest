from __future__ import annotations

import re
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, min_length=8,
        style={"input_type": "password"}, trim_whitespace=False,
    )
    re_password = serializers.CharField(
        write_only=True, required=True, min_length=8,
        style={"input_type": "password"}, trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role", "password", "re_password")
        extra_kwargs = {"id": {"read_only": True}}

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_full_name(self, value: str | None) -> str | None:
        if not value:
            return value
        value = value.strip()
        if not re.fullmatch(r"[\w\s\'\-]+", value, re.UNICODE):
            raise serializers.ValidationError(
                "Full name may only contain letters, spaces, hyphens and apostrophes."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        password = attrs.get("password")
        re_password = attrs.pop("re_password", None)

        if password != re_password:
            raise serializers.ValidationError({"re_password": "Passwords do not match."})

        try:
            validate_password(password)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages[0]})

        return attrs

    def create(self, validated_data: dict) -> User:
        password = validated_data.pop("password")
        try:
            return User.objects.create_user(
                password=password,
                is_staff=False,
                is_active=True,
                deleted=False,
                **validated_data,
            )
        except IntegrityError:
            raise serializers.ValidationError(
                {"email": "A user with this email already exists."}
            )


class UserPublicSerializer(serializers.ModelSerializer):
    """Read-only snapshot embedded in nested responses."""

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role")
        read_only_fields = fields


class UserProfileSerializer(serializers.ModelSerializer):
    """Full profile — returned to the authenticated user themselves."""

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role", "date_joined", "deleted")
        read_only_fields = ("id", "email", "role", "date_joined", "deleted")


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT payload enriched with role and full_name."""

    @classmethod
    def get_token(cls, user: User):
        token = super().get_token(user)
        token["role"] = user.role
        token["full_name"] = user.full_name
        return token

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        if self.user.deleted:
            raise serializers.ValidationError(
                "This account has been deactivated."
            )
        return data