from django.contrib import admin
from .models import LeaveRequest, ShiftRequest, ShiftSwap


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'leave_type', 'start_date', 'end_date', 'status')
    list_filter = ('status', 'leave_type')
    search_fields = ('doctor__username', 'doctor__first_name', 'doctor__last_name')
    readonly_fields = ('requested_at', 'reviewed_at')
    actions = ['approve_requests', 'reject_requests']

    def approve_requests(self, request, queryset):
        queryset.update(status='approved')
    approve_requests.short_description = "Approve selected requests"

    def reject_requests(self, request, queryset):
        queryset.update(status='rejected')
    reject_requests.short_description = "Reject selected requests"


@admin.register(ShiftRequest)
class ShiftRequestAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'shift', 'request_type', 'priority', 'status')
    list_filter = ('status', 'request_type')
    search_fields = ('doctor__username',)


@admin.register(ShiftSwap)
class ShiftSwapAdmin(admin.ModelAdmin):
    list_display = ('requesting_doctor', 'target_doctor', 'shift', 'status')
    list_filter = ('status',)
    search_fields = ('requesting_doctor__username', 'target_doctor__username')
    readonly_fields = ('requested_at', 'responded_at', 'admin_reviewed_at')
