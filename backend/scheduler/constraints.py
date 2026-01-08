"""
Constraint builder for OR-Tools CP-SAT solver.
Implements all hard and soft constraints for physician scheduling.
"""
from ortools.sat.python import cp_model
from typing import Dict, List, Tuple

from .data_preparation import SchedulerData


class ConstraintBuilder:
    """Builds all constraints for the scheduling problem."""

    def __init__(self, model: cp_model.CpModel, data: SchedulerData, variables: Dict):
        self.model = model
        self.data = data
        self.vars = variables  # x[(doctor_idx, shift_idx)] = BoolVar

    def build_all_hard_constraints(self):
        """Build all hard constraints that MUST be satisfied."""
        print("Building hard constraints...")
        self.add_coverage_constraints()
        self.add_leave_constraints()
        self.add_shift_count_constraints()
        self.add_consecutive_shift_constraints()
        self.add_rest_period_constraints()
        self.add_single_day_off_constraints()
        self.add_max_consecutive_days_off_constraints()
        self.add_skill_mix_constraints()
        print("✓ Hard constraints built")

    def add_coverage_constraints(self):
        """Ensure minimum number of doctors per shift."""
        for shift_idx, shift in enumerate(self.data.shifts):
            min_doctors = shift.min_doctors or self.data.configuration.default_min_doctors_per_shift

            self.model.Add(
                sum(self.vars[(d_idx, shift_idx)] for d_idx in range(len(self.data.doctors))) >= min_doctors
            )

    def add_leave_constraints(self):
        """Doctors cannot work on days they have approved leave."""
        for d_idx, doctor in enumerate(self.data.doctors):
            for s_idx, shift in enumerate(self.data.shifts):
                if self.data.is_doctor_on_leave(doctor.id, shift):
                    self.model.Add(self.vars[(d_idx, s_idx)] == 0)

    def add_shift_count_constraints(self):
        """Each doctor works between min and max shifts per month."""
        config = self.data.configuration

        for d_idx in range(len(self.data.doctors)):
            total_shifts = sum(
                self.vars[(d_idx, s_idx)] for s_idx in range(len(self.data.shifts))
            )
            self.model.Add(total_shifts >= config.min_shifts_per_doctor)
            self.model.Add(total_shifts <= config.max_shifts_per_doctor)

    def add_consecutive_shift_constraints(self):
        """No more than max_consecutive_shifts in a row."""
        max_consecutive = self.data.configuration.max_consecutive_shifts

        for d_idx in range(len(self.data.doctors)):
            # Check each window of (max_consecutive + 1) shifts
            for start_idx in range(len(self.data.shifts) - max_consecutive):
                window = range(start_idx, start_idx + max_consecutive + 1)
                self.model.Add(
                    sum(self.vars[(d_idx, s_idx)] for s_idx in window) <= max_consecutive
                )

    def add_rest_period_constraints(self):
        """Enforce minimum rest hours between shifts (prevent night → day transitions)."""
        min_rest = self.data.configuration.min_rest_hours_between_shifts

        if min_rest < 12:
            return  # No restriction needed

        # Prevent night shift followed immediately by day shift
        for d_idx in range(len(self.data.doctors)):
            for s_idx in range(len(self.data.shifts) - 1):
                current_shift = self.data.shifts[s_idx]
                next_shift = self.data.shifts[s_idx + 1]

                # If current is night and next is day on same or next day, forbid both
                if current_shift.shift_type == 'night' and next_shift.shift_type == 'day':
                    days_apart = (next_shift.date - current_shift.date).days
                    if days_apart <= 1:
                        self.model.Add(
                            self.vars[(d_idx, s_idx)] + self.vars[(d_idx, s_idx + 1)] <= 1
                        )

    def add_single_day_off_constraints(self):
        """Avoid single days off between working shifts."""
        if not self.data.configuration.avoid_single_day_off:
            return

        daily_shifts = self.data.get_daily_shifts()
        dates = sorted(daily_shifts.keys())

        for d_idx in range(len(self.data.doctors)):
            # Check each 3-day window
            for i in range(len(dates) - 2):
                day_i = dates[i]
                day_i_plus_1 = dates[i + 1]
                day_i_plus_2 = dates[i + 2]

                # Skip if days are not consecutive
                if (day_i_plus_1 - day_i).days != 1 or (day_i_plus_2 - day_i_plus_1).days != 1:
                    continue

                # Get shift indices for each day
                shifts_day_i = [self.data.shift_index[s.id] for s in daily_shifts[day_i]]
                shifts_day_i_plus_1 = [self.data.shift_index[s.id] for s in daily_shifts[day_i_plus_1]]
                shifts_day_i_plus_2 = [self.data.shift_index[s.id] for s in daily_shifts[day_i_plus_2]]

                # Create variables for working each day
                works_i = self.model.NewBoolVar(f'works_d{d_idx}_day{i}')
                works_i_plus_1 = self.model.NewBoolVar(f'works_d{d_idx}_day{i+1}')
                works_i_plus_2 = self.model.NewBoolVar(f'works_d{d_idx}_day{i+2}')

                # Works day i if any shift on that day
                self.model.AddMaxEquality(
                    works_i,
                    [self.vars[(d_idx, s_idx)] for s_idx in shifts_day_i]
                )
                self.model.AddMaxEquality(
                    works_i_plus_1,
                    [self.vars[(d_idx, s_idx)] for s_idx in shifts_day_i_plus_1]
                )
                self.model.AddMaxEquality(
                    works_i_plus_2,
                    [self.vars[(d_idx, s_idx)] for s_idx in shifts_day_i_plus_2]
                )

                # If works day i AND day i+2, must work day i+1
                # works_i + works_i_plus_2 <= 1 + works_i_plus_1
                self.model.Add(works_i + works_i_plus_2 <= 1 + works_i_plus_1)

    def add_max_consecutive_days_off_constraints(self):
        """No more than max_consecutive_days_off without working."""
        max_days_off = self.data.configuration.max_consecutive_days_off
        daily_shifts = self.data.get_daily_shifts()
        dates = sorted(daily_shifts.keys())

        for d_idx in range(len(self.data.doctors)):
            # Check each window of (max_days_off + 1) consecutive days
            for i in range(len(dates) - max_days_off):
                window_dates = dates[i:i + max_days_off + 1]

                # Check if dates are truly consecutive
                is_consecutive = all(
                    (window_dates[j + 1] - window_dates[j]).days == 1
                    for j in range(len(window_dates) - 1)
                )

                if not is_consecutive:
                    continue

                # Collect all shifts in this window
                window_shifts = []
                for day in window_dates:
                    window_shifts.extend([self.data.shift_index[s.id] for s in daily_shifts[day]])

                # Must work at least one shift in this window
                self.model.Add(
                    sum(self.vars[(d_idx, s_idx)] for s_idx in window_shifts) >= 1
                )

    def add_skill_mix_constraints(self):
        """Ensure required skill mix per shift based on ShiftRequirements."""
        for s_idx, shift in enumerate(self.data.shifts):
            requirements = self.data.get_requirements_for_shift(shift)

            for req in requirements:
                # Specialty requirement
                if req.required_specialty and req.min_with_specialty > 0:
                    specialty_doctors = self.data.doctors_by_specialty.get(req.required_specialty.id, [])
                    specialty_indices = [self.data.doctor_index[d.id] for d in specialty_doctors]

                    if specialty_indices:
                        self.model.Add(
                            sum(self.vars[(d_idx, s_idx)] for d_idx in specialty_indices) >= req.min_with_specialty
                        )

    def build_objective_function(self) -> cp_model.LinearExpr:
        """Build the objective function to maximize (soft constraints)."""
        objective_terms = []

        # TODO: Add soft constraints like:
        # - Fulfill shift requests (weighted by priority)
        # - Fair distribution of weekends/bank holidays
        # - Prefer 2-3 consecutive shift runs
        # - Extra coverage on Mon/Tue

        # For now, just maximize total coverage (slight preference for more doctors)
        for s_idx in range(len(self.data.shifts)):
            for d_idx in range(len(self.data.doctors)):
                objective_terms.append(self.vars[(d_idx, s_idx)])

        return sum(objective_terms)
