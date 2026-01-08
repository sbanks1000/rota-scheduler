"""
Main OR-Tools CP-SAT solver for physician scheduling.
"""
from ortools.sat.python import cp_model
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time

from .data_preparation import SchedulerData
from .constraints import ConstraintBuilder


class ScheduleSolution:
    """Container for the solution returned by the solver."""

    def __init__(self, status: str, assignments: List[Tuple[int, int]],
                 solver_time: float, objective_value: int = None):
        self.status = status  # 'OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'UNKNOWN'
        self.assignments = assignments  # List of (doctor_idx, shift_idx) tuples
        self.solver_time = solver_time
        self.objective_value = objective_value

    @property
    def is_feasible(self) -> bool:
        """Check if a valid solution was found."""
        return self.status in ['OPTIMAL', 'FEASIBLE']

    def __str__(self):
        return (f"ScheduleSolution(status={self.status}, "
                f"assignments={len(self.assignments)}, "
                f"time={self.solver_time:.2f}s)")


class ScheduleSolver:
    """OR-Tools CP-SAT solver for physician scheduling."""

    def __init__(self, data: SchedulerData, timeout_seconds: int = 300):
        """
        Initialize the solver.

        Args:
            data: SchedulerData object with all input data
            timeout_seconds: Maximum time to spend searching for a solution
        """
        self.data = data
        self.timeout_seconds = timeout_seconds
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.variables = {}

        # Configure solver parameters
        self.solver.parameters.max_time_in_seconds = timeout_seconds
        self.solver.parameters.num_search_workers = 8  # Parallel search
        self.solver.parameters.log_search_progress = True

    def create_decision_variables(self):
        """
        Create binary decision variables x[(doctor_idx, shift_idx)].
        x[(d, s)] = 1 if doctor d is assigned to shift s, else 0.
        """
        print("Creating decision variables...")

        for d_idx in range(len(self.data.doctors)):
            for s_idx in range(len(self.data.shifts)):
                var_name = f'x_d{d_idx}_s{s_idx}'
                self.variables[(d_idx, s_idx)] = self.model.NewBoolVar(var_name)

        print(f"✓ Created {len(self.variables)} decision variables "
              f"({len(self.data.doctors)} doctors × {len(self.data.shifts)} shifts)")

    def build_constraints(self):
        """Build all hard constraints using the ConstraintBuilder."""
        constraint_builder = ConstraintBuilder(self.model, self.data, self.variables)
        constraint_builder.build_all_hard_constraints()

    def build_objective_function(self):
        """
        Build the objective function to maximize (soft constraints).

        Current implementation:
        - Maximize total coverage (slight preference for more doctors)

        TODO: Add weighted soft constraints for:
        - Shift requests (high priority)
        - Fair bank holiday distribution
        - Preferred shift patterns (2-3 consecutive)
        - Extra coverage on Mon/Tue
        """
        objective_terms = []

        # Simple objective: maximize total assignments
        # This provides slight preference for more coverage when possible
        for (d_idx, s_idx), var in self.variables.items():
            objective_terms.append(var)

        self.model.Maximize(sum(objective_terms))
        print("✓ Objective function built")

    def solve(self) -> ScheduleSolution:
        """
        Run the CP-SAT solver and return the solution.

        Returns:
            ScheduleSolution object with status, assignments, and metadata
        """
        print("\n" + "=" * 60)
        print("STARTING SCHEDULE GENERATION")
        print("=" * 60)
        print(f"Problem size: {len(self.data.doctors)} doctors, {len(self.data.shifts)} shifts")
        print(f"Timeout: {self.timeout_seconds} seconds")
        print(f"Configuration: {self.data.configuration.name}")
        print("=" * 60 + "\n")

        start_time = time.time()

        # Step 1: Create variables
        self.create_decision_variables()

        # Step 2: Add constraints
        self.build_constraints()

        # Step 3: Set objective
        self.build_objective_function()

        # Step 4: Solve
        print("\nInvoking CP-SAT solver...")
        print("-" * 60)
        status = self.solver.Solve(self.model)
        solve_time = time.time() - start_time

        # Step 5: Parse results
        status_name = self.solver.StatusName(status)
        print("-" * 60)
        print(f"\nSolver finished in {solve_time:.2f} seconds")
        print(f"Status: {status_name}")

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            assignments = self._extract_assignments()
            objective_value = self.solver.ObjectiveValue()

            print(f"Objective value: {objective_value}")
            print(f"Total assignments: {len(assignments)}")

            # Print coverage summary
            self._print_coverage_summary(assignments)

            return ScheduleSolution(
                status=status_name,
                assignments=assignments,
                solver_time=solve_time,
                objective_value=objective_value
            )
        else:
            print("\n⚠️  No feasible solution found!")
            self._print_infeasibility_hints()

            return ScheduleSolution(
                status=status_name,
                assignments=[],
                solver_time=solve_time
            )

    def _extract_assignments(self) -> List[Tuple[int, int]]:
        """
        Extract assignments from the solution.

        Returns:
            List of (doctor_idx, shift_idx) tuples for assigned shifts
        """
        assignments = []

        for (d_idx, s_idx), var in self.variables.items():
            if self.solver.Value(var) == 1:
                assignments.append((d_idx, s_idx))

        return assignments

    def _print_coverage_summary(self, assignments: List[Tuple[int, int]]):
        """Print a summary of shift coverage."""
        from collections import Counter

        # Count doctors per shift
        shift_coverage = Counter(s_idx for _, s_idx in assignments)

        print("\nCoverage Summary:")
        print("-" * 60)

        # Check for under-coverage
        min_required = self.data.configuration.default_min_doctors_per_shift
        under_covered = []

        for s_idx, shift in enumerate(self.data.shifts):
            coverage = shift_coverage.get(s_idx, 0)
            min_doctors = shift.min_doctors or min_required

            if coverage < min_doctors:
                under_covered.append((shift, coverage, min_doctors))

        if under_covered:
            print(f"⚠️  {len(under_covered)} shifts are under-covered:")
            for shift, actual, required in under_covered[:5]:  # Show first 5
                print(f"  {shift.date} {shift.shift_type}: {actual}/{required} doctors")
            if len(under_covered) > 5:
                print(f"  ... and {len(under_covered) - 5} more")
        else:
            print("✓ All shifts meet minimum coverage requirements")

        # Doctor workload summary
        doctor_shifts = Counter(d_idx for d_idx, _ in assignments)
        if doctor_shifts:
            avg_shifts = sum(doctor_shifts.values()) / len(self.data.doctors)
            min_shifts = min(doctor_shifts.values())
            max_shifts = max(doctor_shifts.values())

            print(f"\nDoctor Workload:")
            print(f"  Average: {avg_shifts:.1f} shifts")
            print(f"  Range: {min_shifts}-{max_shifts} shifts")

    def _print_infeasibility_hints(self):
        """Print hints about why the problem might be infeasible."""
        print("\nPossible causes:")
        print("1. Too many doctors on leave relative to shift requirements")
        print("2. Constraints are too restrictive (try relaxing max_consecutive_shifts)")
        print("3. Not enough active doctors to cover all shifts")
        print("4. Skill mix requirements cannot be satisfied with available doctors")
        print("\nSuggestions:")
        print("- Review approved leave requests")
        print("- Check ShiftRequirement constraints in ScheduleConfiguration")
        print("- Ensure enough senior doctors and required specialties are active")
        print("- Consider relaxing shift count constraints (min/max shifts per doctor)")


def generate_schedule(month: int, year: int, timeout_seconds: int = 300) -> ScheduleSolution:
    """
    Convenience function to generate a schedule.

    Args:
        month: Month to generate schedule for (1-12)
        year: Year to generate schedule for
        timeout_seconds: Maximum time to spend searching

    Returns:
        ScheduleSolution object
    """
    # Load data
    print(f"Loading data for {year}-{month:02d}...")
    data = SchedulerData(month, year)
    print(f"✓ Loaded {data}")

    # Create and run solver
    solver = ScheduleSolver(data, timeout_seconds)
    solution = solver.solve()

    return solution
