from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Doctor, Specialty


@admin.register(Doctor)
class DoctorAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'experience_level', 'active')
    list_filter = ('experience_level', 'active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name', 'email')

    fieldsets = UserAdmin.fieldsets + (
        ('Doctor Info', {'fields': ('experience_level', 'phone', 'specialties', 'active')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Doctor Info', {'fields': ('experience_level', 'phone', 'specialties', 'active')}),
    )


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
