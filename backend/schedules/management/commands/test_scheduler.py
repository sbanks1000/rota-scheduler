"""
Django management command to test the scheduler.
"""
from django.core.management.base import BaseCommand
from datetime import date

from scheduler.solver import generate_schedule
from scheduler.solution_parser import save_solution
from scheduler.data_preparation import SchedulerData
from schedules.models import Schedule


class Command(BaseCommand):
    help = 'Test the OR-Tools scheduler'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=int,
            default=None,
            help='Month to generate schedule for (1-12, default: next month)'
        )
        parser.add_argument(
            '--year',
            type=int,
            default=None,
            help='Year to generate schedule for (default: current or next)'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=300,
            help='Solver timeout in seconds (default: 300)'
        )

    def handle(self, *args, **options):
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

        timeout = options['timeout']

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(f"TESTING SCHEDULER FOR {year}-{month:02d}")
        self.stdout.write("=" * 60 + "\n")

        try:
            # Load data
            self.stdout.write("Loading data...")
            data = SchedulerData(month, year)
            self.stdout.write(self.style.SUCCESS(f"✓ Loaded {len(data.doctors)} doctors, {len(data.shifts)} shifts"))

            # Generate schedule
            self.stdout.write(f"\nGenerating schedule (timeout: {timeout}s)...\n")
            solution = generate_schedule(month, year, timeout)

            # Save to database
            self.stdout.write("\nSaving solution to database...")
            schedule = save_solution(solution, data)

            # Display results
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("SCHEDULER TEST COMPLETE"))
            self.stdout.write("=" * 60)

            if solution.is_feasible:
                self.stdout.write(self.style.SUCCESS(f"Status: {solution.status} ✓"))
                self.stdout.write(f"Schedule ID: {schedule.id}")
                self.stdout.write(f"Solver Time: {solution.solver_time:.2f} seconds")
                self.stdout.write(f"Objective Value: {solution.objective_value}")
                self.stdout.write(f"Assignments: {schedule.assignments.count()}")
                self.stdout.write(f"Violations: {schedule.violations.count()}")

                if schedule.violations.exists():
                    self.stdout.write(self.style.WARNING("\n⚠️  Constraint Violations:"))
                    for violation in schedule.violations.all()[:10]:
                        self.stdout.write(f"  [{violation.severity}] {violation.violation_type}")
                        self.stdout.write(f"    {violation.description}")
                else:
                    self.stdout.write(self.style.SUCCESS("\n✓ No constraint violations"))

                # Show sample assignments
                self.stdout.write("\nSample Assignments (first 10):")
                for assignment in schedule.assignments.all().select_related('doctor', 'shift')[:10]:
                    self.stdout.write(
                        f"  {assignment.shift.date} {assignment.shift.shift_type}: "
                        f"{assignment.doctor.get_full_name()}"
                    )

                self.stdout.write("\nTo view full schedule:")
                self.stdout.write(f"  python manage.py shell")
                self.stdout.write(f"  >>> from schedules.models import Schedule")
                self.stdout.write(f"  >>> schedule = Schedule.objects.get(id='{schedule.id}')")
                self.stdout.write(f"  >>> for a in schedule.assignments.all(): print(a)")

            else:
                self.stdout.write(self.style.ERROR(f"Status: {solution.status} ✗"))
                self.stdout.write(self.style.ERROR("\n⚠️  No feasible solution found!"))
                self.stdout.write("\nPossible causes:")
                self.stdout.write("  - Too many constraints (try relaxing max_consecutive_shifts)")
                self.stdout.write("  - Not enough doctors for shift requirements")
                self.stdout.write("  - Conflicting skill mix requirements")

            self.stdout.write("=" * 60 + "\n")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Error: {str(e)}"))
            raise
