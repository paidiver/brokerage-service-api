# Brokerage Service API

## Purpose
A REST API and tile-enabled backend for spatial and temporal oceanographic data, built with FastAPI, PostgreSQL/PostGIS/TimescaleDB, Redis, and Martin.

## Scope in AtlantiS
- Primary geospatial/time-series API backend.
- OGC-compatible endpoint surface for standards-driven integrations.
- Data/admin routes for ingestion, updates, and operations.

## Access
- API docs: https://postgis-api-dev.atlantisvis.xyz/docs
- Martin catalog: https://martin-dev.atlantisvis.xyz/

## Architecture Summary
- FastAPI application exposes API and OGC routes.
- PostgreSQL (with PostGIS + TimescaleDB) stores geospatial/time-series data.
- Redis provides caching.
- Martin serves vector tiles.

## Key Capabilities
- Public OGC API under `/v1/ogc`
- CRUD and bulk routes under `/v1/...`
- Tile and map preview integration
- Alembic migrations for schema versioning
- Test suite with high coverage targets

## Local Setup (Docker)

### Prerequisites
- Docker >= 24
- Optional Docker network for local multi-container integration

```bash
docker network create postgisapi_network
```

### 1. Clone repository

```bash
git clone https://gitlab.com/nocacuk/ocean-informatics/atlantis/services/postgis-api.git
cd postgis-api
```

### 2. Create `.env`

```env
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
POSTGRES_DB=brokerage_service_api
POSTGRES_PORT=5432
POSTGRES_HOST=db
REDIS_HOST=redis
REDIS_PORT=6379
DATABASE_URL=postgresql://myuser:mypassword@db:5432/brokerage_service_api
CESIUM_ION_TOKEN=token
MARTIN_PUBLIC_URL=http://localhost:3000
```

### 3. Build and run stack

```bash
docker compose -f dockerfiles/docker-compose.yml build
docker compose -f dockerfiles/docker-compose.yml up -d
```

### 4. Apply migrations

```bash
docker compose -f dockerfiles/docker-compose.yml run --rm app poetry run alembic upgrade head
```

### 5. Optional: seed development data

```bash
docker compose -f dockerfiles/docker-compose.yml run --rm app poetry run seed-dev-db --stations 20
```

### 6. Basic checks

```bash
curl "http://localhost:8081/healthz"
curl "http://localhost:8081/v1/ogc/collections"
curl "http://localhost:3000/health"
curl "http://localhost:3000/catalog"
```

## Development

### Lint and format

```bash
docker compose -f dockerfiles/docker-compose.yml run --rm app poetry run tox -e lint
docker compose -f dockerfiles/docker-compose.yml run --rm app poetry run tox -e format
```

### Tests

```bash
docker compose -f dockerfiles/docker-compose.yml run --rm app poetry run tox -e py312
```

### Generate migration

```bash
docker compose -f dockerfiles/docker-compose.yml run --rm app poetry run alembic revision --autogenerate -m "Update schema"
```

Apply migration:

```bash
docker compose -f dockerfiles/docker-compose.yml run --rm app poetry run alembic upgrade head
```

## OGC Validation
The `/v1/ogc` surface is designed for OGC API compatibility checks.

### Team Engine (local)
```bash
docker run -p 8082:8080 --network postgisapi_network ogccite/ets-ogcapi-features10
```

### Custom validator
```bash
docker compose -f dockerfiles/docker-compose.yml run --rm app poetry run validate-ogc-api --base-url http://app:8081/v1/ogc --timeout 30
```

## Documentation
- Database details: `docs/database.md`
- API endpoints: `docs/api.md`

## CI
Typical pipeline responsibilities include:
- Linting and formatting validation.
- Test execution against containerized dependencies.
- Docker image build and publish.
- On tag, Helm/Helmfile generation, linting, and release publication.

## Deployment
- Deployment follows the shared AtlantiS model: release on tag, then manual deployment from the Kubernetes package.
- Use the released tag produced by CI.
- Select/update that tag in the Kubernetes package and deploy manually.

## Runtime Troubleshooting
- If API startup fails, verify database and Redis connectivity first.
- If migrations fail, validate Alembic revision history and connection URL.
- If OGC responses are slow, inspect query plans and index coverage.
- If map preview is broken, verify Martin service health and public URL configuration.
