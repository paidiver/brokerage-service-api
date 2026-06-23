# Brokerage Service API

Brokerage Service API provides a federated api access to multiple services.

## Requirements

### Runtime

* Docker
* Docker Compose

### Local development (without Docker)

* Python ≥ 3.13
* Poetry

## Project Structure

```text
.
├── docker
│   ├── docker-compose.yml # Docker compose file for local development
│   └── Dockerfile      # Dockerfile for the API service
├── LICENSE
├── pyproject.toml      # Project metadata & dependencies (Poetry)
├── README.md
├── ruff.toml           # Ruff configuration
├── src
│   └── brokerage_service_api
│       ├── api         # Main API package
│       │   ├── app.py
│       │   ├── exceptions.py
│       │   ├── __init__.py
│       │   └── v1
│       │       └── __init__.py # API V1 endpoints
│       ├── crud    # CRUD operations for models
│       │   └── __init__.py
│       ├── __init__.py
│       ├── models  # Models
│       │   └── __init__.py
│       └── schemas # Pydantic schemas
│           └── __init__.py
├── tests # Test suite
│   └── __init__.py
└── tox.ini
```

## Dependency Management

This project uses **Poetry** for dependency management and packaging.

Key points:

* Dependencies are defined in `pyproject.toml`
* Locked versions live in `poetry.lock`
* Development tools (linting, formatting, testing) are installed via Poetry groups

## Quick Start (Docker)

In this quick start, it will run all the services locally using Docker Compose. This includes:

- An annotations api + PostgreSQL that simulates the JNCC API service
- An annotations api + PostgreSQL that simulates the BODC API service
- A Worms cache API service + PostgreSQL that simulates the WoRMS cache API service
- The Brokerage Service API service

In production, you would typically run the Brokerage Service API service only, and point it to the real JNCC and BODC API services.

### 1. Create environment file

Configuration is provided via environment variables defined in `.env`.

Start from the example file:

```bash
cp .env.example .env
```

Example contents:

```bash
# ENV APIS
JNCC_ANNOTATIONS_API_URL=http://annotations-api1:8000/api # URL for the JNCC API service. It is using the docker service name as hostname to allow inter-container communication.
BODC_ANNOTATIONS_API_URL=http://annotations-api2:8000/api # URL for the BODC API service. It is using the docker service name as hostname to allow inter-container communication.

# Local DEV: Annotation API and Worms-cache configuration
DJANGO_SECRET_KEY=dev-secret-key-change-me
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,worms-cache,192.168.134.132
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:3000,https://paidiver.github.io
DJANGO_CORS_ALLOW_ALL=1
WORMS_API_BASE_URL=https://marinespecies.org/rest
CACHED_WORMS_API_BASE_URL=http://worms-cache:8000/api
TAXAMATCH_URL=http://taxamatch:8080
INGEST_API_TOKEN=mysecrettoken
CACHED_WORMS_API_TOKEN=mysecrettoken

# Local DEV: PostgreSQL
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
POSTGRES_PORT=5432
```

### 2. Build and run the stack

First, ensure you have a shared Docker network named `shared_services` (used for inter-container communication with the WoRMS cache API if necessary):

```bash
docker network create shared_services
```

Then run the stack:

```bash
docker compose -f docker/docker-compose.yml up --build
```

This will:

* Start the Worms Cache API service, together with its associated PostgreSQL database
* Run the migrations and the seed command for the Worms Cache API service
* Start two annotations API services (JNCC and BODC) with their own PostgreSQL databases
* Run the migrations and the seed command for both annotations API services
* Start the Brokerage Service API service

### 3. Test the API

Health endpoint:

```
http://localhost:8020/health/
```

Expected response:

```json
{"status": "ok"}
```

API schema and documentation:

```
http://localhost:8020/docs/
```

## Development Workflow

### Formatting

Format code using Ruff:

```bash
docker compose -f docker/docker-compose.yml run --rm app tox -e format
```

### Linting

Run lint checks:

```bash
docker compose -f docker/docker-compose.yml run --rm app tox -e lint
```

### Tests

Run the test suite with coverage:

```bash
docker compose -f docker/docker-compose.yml run --rm app tox -e py313
```

Coverage reports are written to `coverage_reports/`.

## API Examples

A collection of example API requests and responses is available in the [API Examples](docs/API_EXAMPLES.md) document.

## Acknowledgements

This project was supported by the UK Natural Environment Research Council (NERC) through the *Tools for automating image analysis for biodiversity monitoring (AIAB)* Funding Opportunity, reference code **UKRI052**.
