# API Gateway – Backend

A simplified API Gateway built with **Django REST Framework** that proxies requests to upstream services with API key authentication, Redis-backed rate limiting, and request logging.

## Quick Start

```bash
# 1. Copy env file and adjust if needed
cp .env.example .env

# 2. Start all services
docker compose up --build

# 3. Create a superuser
docker compose exec web python manage.py createsuperuser

# 4. Open Django Admin
open http://localhost:8000/admin/
```

## Architecture

| Component | Technology |
|---|---|
| Framework | Django 5 + DRF |
| Database | PostgreSQL 16 |
| Cache / Rate limiting | Redis 7 |
| Auth | API keys (`X-API-KEY` header) |
| Containerisation | Docker + Docker Compose |

## Usage

1. **Create an API key** in Django Admin → API Keys.
2. **Register an upstream service** in Django Admin → Services (e.g. name=`httpbin`, slug=`httpbin`, base_url=`https://httpbin.org`).
3. **Send proxied requests**:

```bash
curl -i -H "X-API-KEY: <your-key>" http://localhost:8000/proxy/httpbin/get
```

4. **Rate limiting**: each key is limited to **100 requests/hour**. Exceeding the limit returns `429 Too Many Requests`.
5. **Logs**: viewable in Django Admin → Request Logs.


## Tests

```bash
coverage run && coverage report
```
