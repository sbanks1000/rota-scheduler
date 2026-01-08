import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Schedule(models.Model):
    """
    Monthly schedule for doctor shift assignments.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Status choices
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_FINALIZED = 'finalized'
    STATUS_CHOICES = {
        STATUS_DRAFT: 'Draft',
        STATUS_PUBLISHED: 'Published',
        STATUS_FINALIZED: 'Finalized',
    }

    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year = models.IntegerField(validators=[MinValueValidator(2024)])
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_schedules',
    )

    # Solver metadata
    solver_status = models.CharField(max_length=50, blank=True)
    solver_time_seconds = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    objective_value = models.BigIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(
                fields=['month', 'year'],
                name='unique_month_year'
            )
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['year', 'month']),
        ]

    def __str__(self):
        return f"Schedule {self.year}-{self.month:02d} ({self.get_status_display()})"


class Shift(models.Model):
    """
    Individual shifts (day or night) that doctors can be assigned to.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Shift type choices
    SHIFT_DAY = 'day'
    SHIFT_NIGHT = 'night'
    SHIFT_TYPE_CHOICES = {
        SHIFT_DAY: 'Day Shift (7am-7pm)',
        SHIFT_NIGHT: 'Night Shift (7pm-7am)',
    }

    date = models.DateField()
    shift_type = models.CharField(
        max_length=10,
        choices=SHIFT_TYPE_CHOICES,
    )
    start_time = models.TimeField(default='07:00:00')
    end_time = models.TimeField(default='19:00:00')
    min_doctors = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'shift_type']
        constraints = [
            models.UniqueConstraint(
                fields=['date', 'shift_type'],
                name='unique_date_shift_type'
            )
        ]
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['date', 'shift_type']),
        ]

    def __str__(self):
        return f"{self.date} - {self.get_shift_type_display()}"

    @property
    def is_day_shift(self):
        """Helper property to check if this is a day shift."""
        return self.shift_type == self.SHIFT_DAY


class ShiftAssignment(models.Model):
    """
    Assignment of a doctor to a specific shift within a schedule.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Assignment type choices
    TYPE_SCHEDULED = 'scheduled'
    TYPE_MANUAL = 'manual'
    TYPE_SWAP = 'swap'
    TYPE_EXTRA = 'extra'
    TYPE_CHOICES = {
        TYPE_SCHEDULED: 'Scheduled',
        TYPE_MANUAL: 'Manual',
        TYPE_SWAP: 'Swap',
        TYPE_EXTRA: 'Extra',
    }

    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shift_assignments',
    )
    assignment_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_SCHEDULED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['shift__date', 'shift__shift_type']
        constraints = [
            models.UniqueConstraint(
                fields=['schedule', 'shift', 'doctor'],
                name='unique_schedule_shift_doctor'
            )
        ]
        indexes = [
            models.Index(fields=['schedule']),
            models.Index(fields=['doctor']),
            models.Index(fields=['shift']),
        ]

    def __str__(self):
        return f"{self.doctor} - {self.shift}"


class ConstraintViolation(models.Model):
    """
    Tracks constraint violations for auditing and reporting.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Severity choices
    SEVERITY_ERROR = 'error'
    SEVERITY_WARNING = 'warning'
    SEVERITY_INFO = 'info'
    SEVERITY_CHOICES = {
        SEVERITY_ERROR: 'Error',
        SEVERITY_WARNING: 'Warning',
        SEVERITY_INFO: 'Info',
    }

    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='violations',
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='constraint_violations',
        null=True,
        blank=True,
    )
    violation_type = models.CharField(max_length=50)
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
    )
    description = models.TextField()
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['schedule']),
            models.Index(fields=['severity']),
        ]

    def __str__(self):
        return f"{self.violation_type} - {self.get_severity_display()}"
