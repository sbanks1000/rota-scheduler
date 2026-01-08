from django.contrib import admin
from .models import (
    Schedule, Shift, ShiftAssignment, ConstraintViolation,
    ScheduleConfiguration, ShiftRequirement
)


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'status', 'generated_at', 'solver_status')
    list_filter = ('status', 'year', 'month')
    search_fields = ('notes',)
    readonly_fields = ('generated_at', 'solver_time_seconds', 'objective_value')


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('date', 'shift_type', 'min_doctors')
    list_filter = ('shift_type', 'date')
    date_hierarchy = 'date'


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'shift', 'assignment_type', 'schedule')
    list_filter = ('assignment_type', 'schedule__status')
    search_fields = ('doctor__username', 'doctor__first_name', 'doctor__last_name')


@admin.register(ConstraintViolation)
class ConstraintViolationAdmin(admin.ModelAdmin):
    list_display = ('violation_type', 'severity', 'doctor', 'schedule', 'detected_at')
    list_filter = ('severity', 'violation_type')
    readonly_fields = ('detected_at',)


class ShiftRequirementInline(admin.TabularInline):
    model = ShiftRequirement
    extra = 1
    fields = ('applies_to', 'required_specialty', 'min_with_specialty', 'priority')


@admin.register(ScheduleConfiguration)
class ScheduleConfigurationAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'min_shifts_per_doctor', 'max_shifts_per_doctor', 'max_consecutive_shifts', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ShiftRequirementInline]

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Doctor Constraints (Per Month)', {
            'fields': ('min_shifts_per_doctor', 'max_shifts_per_doctor')
        }),
        ('Shift Pattern Constraints', {
            'fields': ('max_consecutive_shifts', 'min_rest_hours_between_shifts')
        }),
        ('Days Off Constraints', {
            'fields': ('max_consecutive_days_off', 'avoid_single_day_off')
        }),
        ('Default Shift Requirements', {
            'fields': ('default_min_doctors_per_shift',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ShiftRequirement)
class ShiftRequirementAdmin(admin.ModelAdmin):
    list_display = ('configuration', 'applies_to', 'required_specialty', 'min_with_specialty', 'priority')
    list_filter = ('applies_to', 'configuration')
    search_fields = ('configuration__name',)
