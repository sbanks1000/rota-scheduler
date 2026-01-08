"""
Data preparation module for OR-Tools solver.
Converts Django models into solver-ready data structures.
"""
from datetime import date, timedelta
from typing import Dict, List, Tuple
from collections import defaultdict

from doctors.models import Doctor
from schedules.models import Shift, ScheduleConfiguration, ShiftRequirement
from requests.models import LeaveRequest


class SchedulerData:
    """Container for all data needed by the scheduler."""

    def __init__(self, month: int, year: int, configuration: ScheduleConfiguration = None):
        self.month = month
        self.year = year
        self.configuration = configuration or ScheduleConfiguration.objects.filter(is_active=True).first()

        if not self.configuration:
            raise ValueError("No active schedule configuration found")

        # Load all data
        self.doctors = list(Doctor.objects.filter(active=True).prefetch_related('specialties'))
        self.shifts = list(Shift.objects.filter(
            date__year=year,
            date__month=month
        ).order_by('date', 'shift_type'))

        self.shift_requirements = list(self.configuration.shift_requirements.all().select_related('required_specialty'))
        self.approved_leave = self._load_approved_leave()

        # Create lookup indices
        self.doctor_ids = [d.id for d in self.doctors]
        self.shift_ids = [s.id for s in self.shifts]
        self.doctor_index = {d.id: idx for idx, d in enumerate(self.doctors)}
        self.shift_index = {s.id: idx for idx, s in enumerate(self.shifts)}

        # Group doctors by specialty
        self.doctors_by_specialty = defaultdict(list)
        for doctor in self.doctors:
            for specialty in doctor.specialties.all():
                self.doctors_by_specialty[specialty.id].append(doctor)

    def _load_approved_leave(self) -> Dict[str, List[date]]:
        """Load approved leave requests for all doctors."""
        leave_dates = defaultdict(list)

        # Get all approved leave that overlaps with this month
        first_day = date(self.year, self.month, 1)
        if self.month == 12:
            last_day = date(self.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(self.year, self.month + 1, 1) - timedelta(days=1)

        approved_requests = LeaveRequest.objects.filter(
            status='approved',
            start_date__lte=last_day,
            end_date__gte=first_day
        ).select_related('doctor')

        for request in approved_requests:
            current = max(request.start_date, first_day)
            end = min(request.end_date, last_day)

            while current <= end:
                leave_dates[request.doctor.id].append(current)
                current += timedelta(days=1)

        return leave_dates

    def is_doctor_on_leave(self, doctor_id: str, shift: Shift) -> bool:
        """Check if a doctor is on approved leave for a shift."""
        return shift.date in self.approved_leave.get(doctor_id, [])

    def get_consecutive_shifts(self, start_idx: int, count: int) -> List[Shift]:
        """Get a list of consecutive shifts starting from an index."""
        if start_idx + count > len(self.shifts):
            return []
        return self.shifts[start_idx:start_idx + count]

    def shift_matches_requirement(self, shift: Shift, requirement: ShiftRequirement) -> bool:
        """Check if a shift requirement applies to a given shift."""
        # Check applies_to filter
        if requirement.applies_to == 'all':
            return True
        elif requirement.applies_to == 'day':
            return shift.shift_type == 'day'
        elif requirement.applies_to == 'night':
            return shift.shift_type == 'night'
        elif requirement.applies_to == 'weekday':
            return shift.date.weekday() < 5  # Mon-Fri
        elif requirement.applies_to == 'weekend':
            return shift.date.weekday() >= 5  # Sat-Sun

        return False

    def get_requirements_for_shift(self, shift: Shift) -> List[ShiftRequirement]:
        """Get all requirements that apply to a specific shift."""
        return [req for req in self.shift_requirements if self.shift_matches_requirement(shift, req)]

    def doctor_has_specialty(self, doctor: Doctor, specialty_id: str) -> bool:
        """Check if a doctor has a specific specialty."""
        return any(spec.id == specialty_id for spec in doctor.specialties.all())

    def get_shift_by_index(self, idx: int) -> Shift:
        """Get shift by index."""
        return self.shifts[idx]

    def get_doctor_by_index(self, idx: int) -> Doctor:
        """Get doctor by index."""
        return self.doctors[idx]

    def get_adjacent_shifts(self, shift_idx: int) -> Tuple[Shift, Shift]:
        """Get the shift before and after a given shift index."""
        prev_shift = self.shifts[shift_idx - 1] if shift_idx > 0 else None
        next_shift = self.shifts[shift_idx + 1] if shift_idx < len(self.shifts) - 1 else None
        return prev_shift, next_shift

    def get_daily_shifts(self) -> Dict[date, List[Shift]]:
        """Group shifts by date."""
        daily = defaultdict(list)
        for shift in self.shifts:
            daily[shift.date].append(shift)
        return daily

    def __str__(self):
        return (f"SchedulerData({self.year}-{self.month:02d}: "
                f"{len(self.doctors)} doctors, {len(self.shifts)} shifts)")
