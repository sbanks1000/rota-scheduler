# Rota Scheduler - Physician Shift Scheduling System

A Django-based physician rota scheduling system for Doctors Express using constraint programming (OR-Tools) to generate optimal schedules.

## Features

- **12-hour shift scheduling** (Day: 7am-7pm, Night: 7pm-7am)
- **Constraint satisfaction** with OR-Tools CP-SAT solver
- **Leave request management** (vacation, study leave, practice development)
- **Shift swap system** with 3-step approval workflow
- **Skill mix requirements** (experience levels + specialties)
- **Django Admin** interface for easy management
- **JWT authentication** for API access
- **Celery** for async schedule generation

## Tech Stack

**Backend:**
- Django 5.0.1
- Django REST Framework 3.14.0
- PostgreSQL 16
- OR-Tools 9.14 (constraint programming)
- Celery + Redis (async tasks)
- JWT authentication

**Frontend (Coming Soon):**
- Next.js 14
- TypeScript
- Tailwind CSS + shadcn/ui
- TanStack Query

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd rota-scheduler
```

2. Start all services:
```bash
docker-compose up -d
```

3. Access the Django Admin:
- URL: http://localhost:8000/admin/
- Username: `admin`
- Password: `admin123`

## Project Structure

```
rota-scheduler/
├── backend/
│   ├── doctors/          # Doctor and Specialty models
│   ├── schedules/        # Schedule, Shift, Assignment models
│   ├── requests/         # Leave, Shift requests, Swaps
│   ├── scheduler/        # OR-Tools scheduling engine (TODO)
│   └── rota_scheduler/   # Django project settings
├── frontend/             # Next.js frontend (TODO)
└── docker-compose.yml
```

## Scheduling Constraints

### Hard Constraints (Must Satisfy)
- No more than 4 consecutive shifts
- Minimum 2 doctors per shift
- No single days off between shifts
- Max 5 consecutive days off without leave
- 14-16 clinical shifts per month per doctor
- Skill mix: ≥1 senior + specialty coverage

### Soft Constraints (Optimized)
- Fulfill shift requests
- Fair bank holiday distribution
- Extra cover on Mon/Tue for clinical work
- Prefer 2-3 consecutive shift runs

## Development

### Run Django Commands
```bash
docker-compose exec backend python manage.py <command>
```

### View Logs
```bash
docker-compose logs -f backend
docker-compose logs -f celery
```

### Stop Services
```bash
docker-compose down
```

## Roadmap

- [x] Phase 1: Django models & admin interface
- [ ] Phase 2: OR-Tools scheduling engine
- [ ] Phase 3: DRF API endpoints
- [ ] Phase 4: Next.js frontend with calendar
- [ ] Phase 5: Reports & analytics
- [ ] Phase 6: Production deployment

## License

MIT

## Author

Doctors Express
