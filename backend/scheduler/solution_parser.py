"""
Solution parser for converting OR-Tools solution to Django models.
"""
from django.db import transaction
from django.utils import timezone
from typing import List, Tuple, Optional
from datetime import datetime

from schedules.models import Schedule, ShiftAssignment, ConstraintViolation
from .solver import ScheduleSolution
from .data_preparation import SchedulerData


class SolutionParser:
    """Parses solver solution and saves to database."""

    def __init__(self, solution: ScheduleSolution, data: SchedulerData):
        self.solution = solution
        self.data = data
        self.violations = []

    @transaction.atomic
    def save_to_database(self, generated_by=None) -> Schedule:
        """
        Save the solution to the database.

        Args:
            generated_by: User who generated the schedule (optional)

        Returns:
            Schedule object with all assignments
        """
        print("\n" + "=" * 60)
        print("SAVING SCHEDULE TO DATABASE")
        print("=" * 60)

        # Create or get Schedule object
        schedule = self._create_or_update_schedule(generated_by)

        if not self.solution.is_feasible:
            print("⚠️  Solution is not feasible - no assignments saved")
            schedule.solver_status = self.solution.status
            schedule.solver_time_seconds = self.solution.solver_time
            schedule.notes = "Schedule generation failed - no feasible solution found"
            schedule.save()
            return schedule

        # Delete existing assignments if regenerating
        deleted_count = schedule.assignments.all().delete()[0]
        if deleted_count:
            print(f"Deleted {deleted_count} existing assignments")

        # Create shift assignments
        print(f"Creating {len(self.solution.assignments)} shift assignments...")
        assignments = self._create_assignments(schedule)
        print(f"✓ Created {len(assignments)} shift assignments")

        # Validate and detect violations
        print("\nValidating schedule...")
        self._detect_violations(schedule)

        if self.violations:
            print(f"⚠️  Detected {len(self.violations)} constraint violations")
            self._save_violations(schedule)
        else:
            print("✓ No constraint violations detected")

        # Update schedule metadata
        schedule.solver_status = self.solution.status
        schedule.solver_time_seconds = self.solution.solver_time
        schedule.objective_value = self.solution.objective_value
        schedule.generated_at = timezone.now()
        schedule.save()

        print(f"\n✓ Schedule saved: {schedule}")
        print("=" * 60 + "\n")

        return schedule

    def _create_or_update_schedule(self, generated_by) -> Schedule:
        """Create or get existing schedule for the month/year."""
        schedule, created = Schedule.objects.get_or_create(
            month=self.data.month,
            year=self.data.year,
            defaults={
                'status': Schedule.STATUS_DRAFT,
                'generated_by': generated_by,
            }
        )

        if not created:
            print(f"Found existing schedule: {schedule}")
        else:
            print(f"Created new schedule: {schedule}")

        return schedule

    def _create_assignments(self, schedule: Schedule) -> List[ShiftAssignment]:
        """Create ShiftAssignment objects from solution."""
        assignments = []

        for doctor_idx, shift_idx in self.solution.assignments:
            doctor = self.data.get_doctor_by_index(doctor_idx)
            shift = self.data.get_shift_by_index(shift_idx)

            assignment = ShiftAssignment.objects.create(
                schedule=schedule,
                shift=shift,
                doctor=doctor,
                assignment_type=ShiftAssignment.TYPE_SCHEDULED
            )
            assignments.append(assignment)

        return assignments

    def _detect_violations(self, schedule: Schedule):
        """
        Detect any constraint violations in the solution.

        This validates the solution against all hard constraints to catch
        any solver bugs or configuration issues.
        """
        self.violations = []

        # Check coverage violations
        self._check_coverage_violations(schedule)

        # Check doctor workload violations
        self._check_workload_violations(schedule)

        # Check consecutive shift violations
        self._check_consecutive_shift_violations(schedule)

        # Check rest period violations
        self._check_rest_period_violations(schedule)

    def _check_coverage_violations(self, schedule: Schedule):
        """Check if any shifts are under-covered."""
        for shift in self.data.shifts:
            assignments = schedule.assignments.filter(shift=shift)
            actual_count = assignments.count()
            min_required = shift.min_doctors or self.data.configuration.default_min_doctors_per_shift

            if actual_count < min_required:
                self.violations.append({
                    'violation_type': 'under_coverage',
                    'severity': ConstraintViolation.SEVERITY_ERROR,
                    'description': (f"Shift {shift} has only {actual_count} doctors "
                                  f"(minimum: {min_required})"),
                    'doctor': None,
                })

    def _check_workload_violations(self, schedule: Schedule):
        """Check if any doctors exceed min/max shift counts."""
        config = self.data.configuration

        for doctor in self.data.doctors:
            shift_count = schedule.assignments.filter(doctor=doctor).count()

            if shift_count < config.min_shifts_per_doctor:
                self.violations.append({
                    'violation_type': 'under_min_shifts',
                    'severity': ConstraintViolation.SEVERITY_WARNING,
                    'description': (f"Doctor {doctor.get_full_name()} has only {shift_count} shifts "
                                  f"(minimum: {config.min_shifts_per_doctor})"),
                    'doctor': doctor,
                })

            if shift_count > config.max_shifts_per_doctor:
                self.violations.append({
                    'violation_type': 'over_max_shifts',
                    'severity': ConstraintViolation.SEVERITY_ERROR,
                    'description': (f"Doctor {doctor.get_full_name()} has {shift_count} shifts "
                                  f"(maximum: {config.max_shifts_per_doctor})"),
                    'doctor': doctor,
                })

    def _check_consecutive_shift_violations(self, schedule: Schedule):
        """Check for too many consecutive shifts."""
        max_consecutive = self.data.configuration.max_consecutive_shifts

        for doctor in self.data.doctors:
            # Get doctor's shifts in order
            doctor_assignments = schedule.assignments.filter(doctor=doctor).select_related('shift').order_by('shift__date', 'shift__shift_type')
            shift_indices = [self.data.shift_index[a.shift.id] for a in doctor_assignments]

            # Check for consecutive runs
            if len(shift_indices) < 2:
                continue

            consecutive_count = 1
            for i in range(1, len(shift_indices)):
                if shift_indices[i] == shift_indices[i-1] + 1:
                    consecutive_count += 1

                    if consecutive_count > max_consecutive:
                        self.violations.append({
                            'violation_type': 'too_many_consecutive_shifts',
                            'severity': ConstraintViolation.SEVERITY_ERROR,
                            'description': (f"Doctor {doctor.get_full_name()} has {consecutive_count} "
                                          f"consecutive shifts (maximum: {max_consecutive})"),
                            'doctor': doctor,
                        })
                        break
                else:
                    consecutive_count = 1

    def _check_rest_period_violations(self, schedule: Schedule):
        """Check for insufficient rest between shifts (night->day transitions)."""
        min_rest = self.data.configuration.min_rest_hours_between_shifts

        if min_rest < 12:
            return  # No restriction

        for doctor in self.data.doctors:
            doctor_assignments = schedule.assignments.filter(doctor=doctor).select_related('shift').order_by('shift__date', 'shift__shift_type')

            for i in range(len(doctor_assignments) - 1):
                current_shift = doctor_assignments[i].shift
                next_shift = doctor_assignments[i+1].shift

                # Check for night->day violation
                if current_shift.shift_type == 'night' and next_shift.shift_type == 'day':
                    days_apart = (next_shift.date - current_shift.date).days

                    if days_apart <= 1:
                        self.violations.append({
                            'violation_type': 'insufficient_rest',
                            'severity': ConstraintViolation.SEVERITY_ERROR,
                            'description': (f"Doctor {doctor.get_full_name()} has night shift on "
                                          f"{current_shift.date} followed by day shift on {next_shift.date} "
                                          f"(less than {min_rest} hours rest)"),
                            'doctor': doctor,
                        })

    def _save_violations(self, schedule: Schedule):
        """Save detected violations to database."""
        # Delete existing violations for this schedule
        schedule.violations.all().delete()

        # Create new violation records
        violation_objects = [
            ConstraintViolation(
                schedule=schedule,
                doctor=v['doctor'],
                violation_type=v['violation_type'],
                severity=v['severity'],
                description=v['description']
            )
            for v in self.violations
        ]

        ConstraintViolation.objects.bulk_create(violation_objects)
        print(f"✓ Saved {len(violation_objects)} violations")


def save_solution(solution: ScheduleSolution, data: SchedulerData,
                  generated_by=None) -> Schedule:
    """
    Convenience function to parse and save a solution.

    Args:
        solution: ScheduleSolution from solver
        data: SchedulerData used to generate solution
        generated_by: User who generated the schedule

    Returns:
        Schedule object
    """
    parser = SolutionParser(solution, data)
    return parser.save_to_database(generated_by)
