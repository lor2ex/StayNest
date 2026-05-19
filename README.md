# StayNest

A REST API backend for a short-term property rental platform. Landlords can list and manage properties; tenants can search, book, and review them.

## Tech Stack

- **Python 3.13** / **Django 6** / **Django REST Framework**
- **MySQL 9.7** — primary database
- **SimpleJWT** — authentication via httpOnly cookies with automatic token rotation
- **drf-spectacular** — OpenAPI 3 / Swagger UI
- **Docker** + **Docker Compose** — containerized deployment
- **Gunicorn** — production WSGI server

## Features

- JWT authentication stored in httpOnly cookies with silent access-token refresh via middleware
- Role-based access control: `landlord` and `tenant` roles with per-action permission checks
- Property listings with filtering (city, type, price range, rooms), full-text search, and ordering
- Booking lifecycle with status transitions and race-condition protection via `SELECT FOR UPDATE`
- Reviews restricted to users with a completed confirmed stay
- View history and search history tracking per user
- Soft delete for user accounts (`deleted` flag + `is_active=False`)

## API Overview

| Group | Endpoints |
|---|---|
| Auth | `POST /auth/register/` `POST /auth/login/` `POST /auth/logout/` `GET\|PATCH /auth/me/` |
| Properties | `GET\|POST /properties/` `GET\|PUT\|PATCH\|DELETE /properties/{id}/` `PATCH /properties/{id}/toggle/` `GET /properties/my/` |
| Bookings | `GET\|POST /bookings/` `GET /bookings/{id}/` `PATCH /bookings/{id}/status/` `GET /bookings/incoming/` |
| Reviews | `GET\|POST /properties/{id}/reviews/` `PATCH\|DELETE /properties/{id}/reviews/{id}/` |
| Stats | `GET /stats/views/` `GET /stats/searches/` |
| Docs | `GET /api/schema/swagger/` `GET /api/schema/redoc/` |

## Getting Started

### Prerequisites

- Docker and Docker Compose installed

### Local setup

1. Clone the repository and create a `.env` file:

```env
SECRET_KEY=your-secret-key
DEBUG=True

DB_NAME=staynest
DB_USER=staynest
DB_PASSWORD=yourpassword
DB_HOST=database
DB_PORT=3306
```

2. Start the services:

```bash
docker compose -f docker-compose.local.yaml up --build
```

The API will be available at `http://localhost:8000`.  
Swagger UI: `http://localhost:8000/api/schema/swagger/`

### Production deployment

```bash
docker compose up -d
```

Requires additional env vars: `DOCKERHUB_USER`, `APP_NAME`, `APP_TAG`, `ALLOWED_HOSTS`.

## Project Structure

```
config/          # Django settings, URLs, WSGI/ASGI
my_app/
  models/        # User, Property, Booking, Review, stats models
  serializers/   # Input validation and output representation
  views/         # ViewSets and API views
  permissions.py # Custom DRF permission classes
  middlewares.py # JWT cookie middleware (silent token refresh)
  utils.py       # Cookie helpers
```

## License

MIT
