from django.contrib import admin
from .models import Schedule, Shift, ShiftAssignment, ConstraintViolation


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
