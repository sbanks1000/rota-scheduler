import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class LeaveRequest(models.Model):
    """
    Requests for vacation, study leave, or practice development days.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Leave type choices
    TYPE_VACATION = 'vacation'
    TYPE_STUDY_LEAVE = 'study_leave'
    TYPE_PRACTICE_DEVELOPMENT = 'practice_development'
    TYPE_SICK = 'sick'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = {
        TYPE_VACATION: 'Vacation',
        TYPE_STUDY_LEAVE: 'Study Leave',
        TYPE_PRACTICE_DEVELOPMENT: 'Practice Development',
        TYPE_SICK: 'Sick Leave',
        TYPE_OTHER: 'Other',
    }

    # Status choices
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = {
        STATUS_PENDING: 'Pending',
        STATUS_APPROVED: 'Approved',
        STATUS_REJECTED: 'Rejected',
        STATUS_CANCELLED: 'Cancelled',
    }

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leave_requests',
    )
    start_date = models.DateField()
    end_date = models.DateField()
    leave_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_leave_requests',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['doctor', 'start_date', 'end_date']),
            models.Index(fields=['status']),
            models.Index(fields=['leave_type']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='end_date_after_start_date'
            )
        ]

    def __str__(self):
        return f"{self.doctor} - {self.get_leave_type_display()} ({self.start_date} to {self.end_date})"


class ShiftRequest(models.Model):
    """
    Requests for extra shifts or shift preferences.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Request type choices
    TYPE_EXTRA = 'extra'
    TYPE_PREFERENCE = 'preference'
    TYPE_CHOICES = {
        TYPE_EXTRA: 'Extra Shift',
        TYPE_PREFERENCE: 'Preference',
    }

    # Status choices
    STATUS_PENDING = 'pending'
    STATUS_FULFILLED = 'fulfilled'
    STATUS_UNFULFILLED = 'unfulfilled'
    STATUS_CHOICES = {
        STATUS_PENDING: 'Pending',
        STATUS_FULFILLED: 'Fulfilled',
        STATUS_UNFULFILLED: 'Unfulfilled',
    }

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shift_requests',
    )
    shift = models.ForeignKey(
        'schedules.Shift',
        on_delete=models.CASCADE,
        related_name='requests',
    )
    request_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
    )
    priority = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['doctor']),
            models.Index(fields=['shift']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.doctor} - {self.shift} ({self.get_request_type_display()})"


class ShiftSwap(models.Model):
    """
    Requests to swap shifts between doctors.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Status choices
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_APPROVED = 'approved'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = {
        STATUS_PENDING: 'Pending',
        STATUS_ACCEPTED: 'Accepted by Target',
        STATUS_REJECTED: 'Rejected by Target',
        STATUS_APPROVED: 'Approved by Admin',
        STATUS_CANCELLED: 'Cancelled',
    }

    schedule = models.ForeignKey(
        'schedules.Schedule',
        on_delete=models.CASCADE,
        related_name='swaps',
    )
    requesting_doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='initiated_swaps',
    )
    target_doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_swaps',
    )
    shift = models.ForeignKey(
        'schedules.Shift',
        on_delete=models.CASCADE,
        related_name='swaps',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    admin_reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_swaps',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['requesting_doctor']),
            models.Index(fields=['target_doctor']),
        ]

    def __str__(self):
        return f"{self.requesting_doctor} ↔ {self.target_doctor} - {self.shift}"
