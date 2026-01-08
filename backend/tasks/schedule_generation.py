"""
Celery task for asynchronous schedule generation.
"""
from celery import shared_task
from django.utils import timezone
import logging

from scheduler.data_preparation import SchedulerData
from scheduler.solver import ScheduleSolver
from scheduler.solution_parser import save_solution
from schedules.models import Schedule

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='tasks.generate_schedule')
def generate_schedule_task(self, month: int, year: int, user_id=None, timeout_seconds: int = 300):
    """
    Asynchronous Celery task for generating a monthly schedule.

    Args:
        month: Month to generate schedule for (1-12)
        year: Year to generate schedule for
        user_id: ID of user who initiated generation (optional)
        timeout_seconds: Maximum solver time in seconds (default: 300 = 5 minutes)

    Returns:
        dict: Result summary with status, schedule_id, and statistics
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting schedule generation for {year}-{month:02d}")

    try:
        # Update task state to show progress
        self.update_state(
            state='PROGRESS',
            meta={'step': 'loading_data', 'description': 'Loading doctors, shifts, and constraints...'}
        )

        # Load data
        logger.info(f"[Task {task_id}] Loading data...")
        data = SchedulerData(month, year)
        logger.info(f"[Task {task_id}] Loaded {len(data.doctors)} doctors, {len(data.shifts)} shifts")

        # Check for existing schedule
        schedule = Schedule.objects.filter(month=month, year=year).first()
        if schedule and schedule.status == Schedule.STATUS_FINALIZED:
            logger.warning(f"[Task {task_id}] Schedule already finalized - aborting")
            return {
                'status': 'ERROR',
                'error': 'Schedule is already finalized and cannot be regenerated',
                'schedule_id': str(schedule.id)
            }

        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'building_model',
                'description': f'Building constraint model ({len(data.doctors)} × {len(data.shifts)} variables)...'
            }
        )

        # Create and run solver
        logger.info(f"[Task {task_id}] Running OR-Tools solver (timeout: {timeout_seconds}s)...")
        solver = ScheduleSolver(data, timeout_seconds)
        solution = solver.solve()

        logger.info(f"[Task {task_id}] Solver finished: {solution.status} in {solution.solver_time:.2f}s")

        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'step': 'saving_solution',
                'description': f'Saving {len(solution.assignments)} assignments to database...'
            }
        )

        # Get user object if provided
        generated_by = None
        if user_id:
            from doctors.models import Doctor
            try:
                generated_by = Doctor.objects.get(id=user_id)
            except Doctor.DoesNotExist:
                logger.warning(f"[Task {task_id}] User {user_id} not found")

        # Save solution to database
        schedule = save_solution(solution, data, generated_by)

        logger.info(f"[Task {task_id}] Schedule saved: {schedule.id}")

        # Prepare result summary
        result = {
            'status': 'SUCCESS' if solution.is_feasible else 'INFEASIBLE',
            'schedule_id': str(schedule.id),
            'solver_status': solution.status,
            'solver_time': solution.solver_time,
            'assignment_count': len(solution.assignments),
            'objective_value': solution.objective_value,
            'violation_count': schedule.violations.count(),
            'generated_at': timezone.now().isoformat(),
        }

        if solution.is_feasible:
            logger.info(f"[Task {task_id}] ✓ Schedule generation successful")
        else:
            logger.warning(f"[Task {task_id}] ⚠️  No feasible solution found")
            result['error'] = 'No feasible solution found - constraints may be too restrictive'

        return result

    except Exception as e:
        logger.error(f"[Task {task_id}] Error during schedule generation: {str(e)}", exc_info=True)

        # Try to update schedule status if it exists
        try:
            schedule = Schedule.objects.get(month=month, year=year)
            schedule.solver_status = 'ERROR'
            schedule.notes = f"Generation failed: {str(e)}"
            schedule.save()
        except Schedule.DoesNotExist:
            pass

        return {
            'status': 'ERROR',
            'error': str(e),
            'task_id': task_id
        }


@shared_task(name='tasks.generate_schedule_with_retry')
def generate_schedule_with_retry(month: int, year: int, user_id=None, max_retries: int = 2):
    """
    Generate schedule with automatic retry and relaxed constraints on failure.

    This task will:
    1. Attempt generation with default constraints
    2. If infeasible, retry with relaxed constraints (e.g., max_consecutive_shifts = 5)
    3. If still infeasible, provide detailed error report

    Args:
        month: Month to generate
        year: Year to generate
        user_id: User ID who initiated
        max_retries: Maximum number of retries with relaxed constraints

    Returns:
        dict: Result summary
    """
    logger.info(f"Starting schedule generation with retry for {year}-{month:02d}")

    # First attempt with normal constraints
    result = generate_schedule_task.apply(args=[month, year, user_id]).get()

    if result['status'] == 'SUCCESS':
        return result

    logger.warning(f"Initial attempt failed: {result.get('error', 'Unknown')}")

    # TODO: Implement constraint relaxation logic
    # For now, just return the failure
    return result


@shared_task(name='tasks.validate_schedule')
def validate_schedule_task(schedule_id: str):
    """
    Validate an existing schedule for constraint violations.

    This can be run independently to re-check a schedule after manual edits.

    Args:
        schedule_id: UUID of the schedule to validate

    Returns:
        dict: Validation results
    """
    from schedules.models import Schedule
    from scheduler.solution_parser import SolutionParser
    from scheduler.solver import ScheduleSolution

    logger.info(f"Validating schedule {schedule_id}")

    try:
        schedule = Schedule.objects.get(id=schedule_id)

        # Load data for the schedule's month/year
        data = SchedulerData(schedule.month, schedule.year)

        # Get assignments and convert to solution format
        assignments = [
            (data.doctor_index[a.doctor.id], data.shift_index[a.shift.id])
            for a in schedule.assignments.all()
        ]

        # Create a mock solution for validation
        solution = ScheduleSolution(
            status='FEASIBLE',
            assignments=assignments,
            solver_time=0,
            objective_value=len(assignments)
        )

        # Run validation
        parser = SolutionParser(solution, data)
        parser._detect_violations(schedule)
        parser._save_violations(schedule)

        logger.info(f"Validation complete: {len(parser.violations)} violations found")

        return {
            'status': 'SUCCESS',
            'schedule_id': str(schedule.id),
            'violation_count': len(parser.violations),
            'violations': [
                {
                    'type': v['violation_type'],
                    'severity': v['severity'],
                    'description': v['description']
                }
                for v in parser.violations
            ]
        }

    except Schedule.DoesNotExist:
        logger.error(f"Schedule {schedule_id} not found")
        return {
            'status': 'ERROR',
            'error': f"Schedule {schedule_id} not found"
        }
    except Exception as e:
        logger.error(f"Error validating schedule: {str(e)}", exc_info=True)
        return {
            'status': 'ERROR',
            'error': str(e)
        }
