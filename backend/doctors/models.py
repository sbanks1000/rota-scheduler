import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class Doctor(AbstractUser):
    """
    Extended User model for doctors with additional fields for scheduling.
    Inherits from AbstractUser to get authentication functionality.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    phone = models.CharField(max_length=20, blank=True)
    specialties = models.ManyToManyField(
        'Specialty',
        related_name='doctors',
        blank=True,
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['active']),
        ]

    def __str__(self):
        return f"Dr. {self.get_full_name()}" if self.get_full_name() else self.username


class Specialty(models.Model):
    """
    Medical specialties for doctors (e.g., Emergency Medicine, Pediatrics).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Specialties'
        ordering = ['name']

    def __str__(self):
        return self.name
