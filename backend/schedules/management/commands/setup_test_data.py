"""
Django management command to create test data for schedule generation.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from doctors.models import Doctor, Specialty
from schedules.models import Schedule, Shift, ScheduleConfiguration, ShiftRequirement


class Command(BaseCommand):
    help = 'Create test data for schedule generation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=int,
            default=None,
            help='Month to create shifts for (1-12, default: next month)'
        )
        parser.add_argument(
            '--year',
            type=int,
            default=None,
            help='Year to create shifts for (default: current year or next)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing test data first'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write("Clearing existing test data...")
            ShiftRequirement.objects.all().delete()
            ScheduleConfiguration.objects.all().delete()
            Shift.objects.all().delete()
            Doctor.objects.all().delete()
            Specialty.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("✓ Cleared existing data"))

        # Determine month/year
        today = date.today()
        if options['month'] and options['year']:
            month = options['month']
            year = options['year']
        elif options['month']:
            month = options['month']
            year = today.year if month >= today.month else today.year + 1
        else:
            # Default to next month
            if today.month == 12:
                month = 1
                year = today.year + 1
            else:
                month = today.month + 1
                year = today.year

        self.stdout.write(f"\nCreating test data for {year}-{month:02d}...\n")

        # Create specialties
        self.stdout.write("Creating specialties...")
        em_specialty, _ = Specialty.objects.get_or_create(
            name='Emergency Medicine',
            defaults={'description': 'Emergency and acute care'}
        )
        gp_specialty, _ = Specialty.objects.get_or_create(
            name='General Practice',
            defaults={'description': 'Primary care and family medicine'}
        )
        uc_specialty, _ = Specialty.objects.get_or_create(
            name='Urgent Care Physician',
            defaults={'description': 'Blend of EM and GP for urgent care settings'}
        )
        self.stdout.write(self.style.SUCCESS(f"✓ Created 3 specialties"))

        # Create doctors
        self.stdout.write("Creating doctors...")
        doctors_data = [
            ('Dr. Sarah Johnson', 'sjohnson', [em_specialty, uc_specialty]),
            ('Dr. Michael Chen', 'mchen', [gp_specialty, uc_specialty]),
            ('Dr. Emily Rodriguez', 'erodriguez', [em_specialty]),
            ('Dr. James Wilson', 'jwilson', [gp_specialty]),
            ('Dr. Anna Kim', 'akim', [uc_specialty]),
            ('Dr. David Brown', 'dbrown', [gp_specialty]),
            ('Dr. Lisa Martinez', 'lmartinez', [em_specialty, uc_specialty]),
            ('Dr. Robert Taylor', 'rtaylor', [uc_specialty]),
            ('Dr. Jennifer Lee', 'jlee', [gp_specialty]),
            ('Dr. Thomas Anderson', 'tanderson', [em_specialty]),
        ]

        doctors = []
        for full_name, username, specialties in doctors_data:
            first_name, last_name = full_name.replace('Dr. ', '').rsplit(' ', 1)
            doctor, created = Doctor.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f'{username}@doctorsexpress.com',
                    'active': True,
                }
            )
            if created:
                doctor.set_password('password123')
                doctor.save()

            doctor.specialties.set(specialties)
            doctors.append(doctor)

        self.stdout.write(self.style.SUCCESS(f"✓ Created {len(doctors)} doctors"))

        # Create schedule configuration
        self.stdout.write("Creating schedule configuration...")
        config, created = ScheduleConfiguration.objects.get_or_create(
            name='Default Configuration',
            defaults={
                'description': 'Standard urgent care scheduling rules',
                'min_shifts_per_doctor': 14,
                'max_shifts_per_doctor': 16,
                'max_consecutive_shifts': 4,
                'min_rest_hours_between_shifts': 12,
                'max_consecutive_days_off': 5,
                'avoid_single_day_off': True,
                'default_min_doctors_per_shift': 2,
                'is_active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Created configuration: {config.name}"))
        else:
            self.stdout.write(f"  Using existing configuration: {config.name}")

        # Create shift requirements
        self.stdout.write("Creating shift requirements...")

        # Requirement: Weekend shifts need urgent care specialty
        ShiftRequirement.objects.get_or_create(
            configuration=config,
            applies_to='weekend',
            required_specialty=uc_specialty,
            defaults={
                'min_with_specialty': 1,
                'priority': 90,
            }
        )

        self.stdout.write(self.style.SUCCESS(f"✓ Created shift requirements"))

        # Create shifts for the month
        self.stdout.write(f"Creating shifts for {year}-{month:02d}...")

        # Get first and last day of month
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year, 12, 31)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)

        shift_count = 0
        current_date = first_day

        while current_date <= last_day:
            # Create day shift
            Shift.objects.get_or_create(
                date=current_date,
                shift_type='day',
                defaults={
                    'start_time': '07:00:00',
                    'end_time': '19:00:00',
                    'min_doctors': 2,
                }
            )
            shift_count += 1

            # Create night shift
            Shift.objects.get_or_create(
                date=current_date,
                shift_type='night',
                defaults={
                    'start_time': '19:00:00',
                    'end_time': '07:00:00',
                    'min_doctors': 2,
                }
            )
            shift_count += 1

            current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"✓ Created {shift_count} shifts ({last_day.day} days × 2 shifts/day)"))

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("TEST DATA SETUP COMPLETE"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Period: {year}-{month:02d}")
        self.stdout.write(f"Doctors: {Doctor.objects.filter(active=True).count()} active")
        self.stdout.write(f"Shifts: {Shift.objects.filter(date__year=year, date__month=month).count()}")
        self.stdout.write(f"Configuration: {config.name}")
        self.stdout.write(f"Shift Requirements: {config.shift_requirements.count()}")
        self.stdout.write("\nNext steps:")
        self.stdout.write("  1. Run: python manage.py test_scheduler")
        self.stdout.write("  2. Or use Django shell to generate schedule:")
        self.stdout.write(f"     from scheduler.solver import generate_schedule")
        self.stdout.write(f"     solution = generate_schedule({month}, {year})")
        self.stdout.write("=" * 60 + "\n")
