# Brokerage Service API

Brokerage Service API provides a federated api access to multiple sources related to image annotations.

## Overview

The app is available in these links:

- Development: [https://paidiver-brokerage-service-dev.noc.ac.uk](https://paidiver-brokerage-service.noc.ac.uk)
- Live: [https://paidiver-brokerage-service.noc.ac.uk](https://paidiver-brokerage-service.noc.ac.uk)

The service provides one API over multiple annotation sources, including source discovery, federated searches, cached search sessions, and health reporting.

## Documentation

* [API examples](docs/API_EXAMPLES.md)
* [Search sessions](docs/search-sessions.md)
* [Deployment guide](docs/DEPLOYMENT.md)
* [Detailed Helmfile deployment](deployment/README.md)

## Requirements

### Runtime

* Docker
* Docker Compose

### Local development (without Docker)

* Python 3.13
* [uv](https://docs.astral.sh/uv/getting-started/installation/) (CI and Docker use 0.9.22)

## Architecture

### Project Structure

```text
.
├── docker
│   ├── docker-compose.yml # Docker compose file for local development
│   └── Dockerfile      # Dockerfile for the API service
├── LICENSE
├── pyproject.toml      # Project metadata & dependencies
├── README.md
├── ruff.toml           # Ruff configuration
├── src
│   └── brokerage_service_api
│       ├── api         # Main API package
│       │   ├── app.py
│       │   ├── exceptions.py
│       │   └── v1 # API V1 endpoints
│       ├── fixtures    # Fixtures for source data
│       ├── registry    # Registry for upstream services
│       ├── models  # Models
│       ├── schemas # Pydantic schemas
│       └── upstream # Clients for upstream services
├── tests # Test suite
│   └── __init__.py
└── tox.ini
```

### Dependency Management

This project uses **uv** for dependency management, environments and building packages.

Key points:

* Dependencies are defined in `pyproject.toml`
* Locked versions live in `uv.lock`
* Development tools (linting, formatting, testing) are installed via dependency groups

### Deployment

The [deployment](deployment) directory contains the Helm chart and Helmfile configuration used to deploy this app. For information about deployment, configuration options, usage instructions, and Docker images, see the [deployment guide](docs/DEPLOYMENT.md).

### Upstream Services (External APIs)

The Brokerage Service API interacts with several upstream services, called **sources**. In this implementation, the primary sources are the JNCC Annotations API and the BODC Annotations API.

Upstream API sources are managed within the configuration file located at [*fixtures/source.yaml*](./src/brokerage_service_api/fixtures/source.yaml). This file is parsed and loaded into the application's memory during initialization (startup) and remains immutable throughout the application's lifespan.

#### Example source:

```yaml
sources:
  bodc:
    source_name: "bodc"
    label: "BRITISH OCEANOGRAPHIC DATA CENTRE"
    base_url: "BODC_ANNOTATIONS_API_URL"
    enabled: true
    kind: "annotations_v1"
    timeout:
      connect: 5.0
      read: 30.0
      write: 30.0
      pool: 5.0
  jncc:
    source_name: "jncc"
    label: "JOINT NATURE CONSERVATION COMMITTEE"
    base_url: "JNCC_ANNOTATIONS_API_URL"
    enabled: true
    kind: "annotations_v1"
    timeout:
      connect: 5.0
      read: 30.0
      write: 30.0
      pool: 5.0
```

#### Configuring new source

To onboard a new upstream source, follow these steps:

1. Update the YAML Configuration:

Add the new source block under the `sources` key in [*fixtures/source.yaml*](./src/brokerage_service_api/fixtures/source.yaml). Set the `base_url` value to match the corresponding environment variable name.

2. Define Environment Variables:

Declare the environment variable name and its value in your locally managed [.env] file.

3. Register the Environment Mapping:

Add a new key-value entry to the `ENV_SOURCE_URL_MAP` dictionary inside [*fixtures/constants.py*](./src/brokerage_service_api/fixtures/constants.py). This maps the source identifier to its environment variable name and an isolated container fallback URL.

```python
ENV_SOURCE_URL_MAP = {
    # Existing mappings...
    "new_source_name": ("EXAMPLE_ANNOTATIONS_API_URL", "http://example-api:8000/api/"),
}
```

### Cache Layer (Redis)

The API creates one async Redis client at startup, checks it with `PING`, and
closes it at shutdown. Routes can inject it with `Depends(get_redis)` from
`brokerage_service_api.utilities.redis`, or access `request.app.state.redis`.
The client returns decoded strings. `/api/sources` responses are cached using keys
that include query parameters and source configuration. Set `REDIS_ENABLED=false`
to disable caching, or `REDIS_DEFAULT_TTL_SECONDS=300` to configure the lifetime.

Local runs default to `REDIS_BACKEND=fake`, using `fakeredis` without a server.
Fake data is isolated per application process and lost on restart, so use real
Redis when multiple workers need shared state.

To connect to a server, set `REDIS_BACKEND=redis` and
`REDIS_URL=redis://localhost:6379/0`. Export these variables in your shell, or
start Uvicorn with `--env-file .env` to load them from a file. If real Redis is unreachable, the API starts and cache failures fall back to
normal upstream calls. Subsequent requests can use Redis when it recovers.

Docker Compose explicitly selects real Redis at `redis://redis:6379/0`, waits
for its health check, and persists data in the `redis_data` volume. Redis is
accessible within the Compose network, with no host port exposed.

## Quick Start

### Docker (Recommended)

In this quick start, it will run all the services locally using Docker Compose. This includes:

- An annotations api + PostgreSQL that simulates the JNCC API service
- An annotations api + PostgreSQL that simulates the BODC API service
- A Worms cache API service + PostgreSQL that simulates the WoRMS cache API service
- The Brokerage Service API service

In production, you would typically run the Brokerage Service API service only, and point it to the real JNCC and BODC API services.

1. Create environment file

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

RUN_LIVE_UPSTREAM_TESTS=1 # flag to run tests that require live upstream services (JNCC, BODC). Set to 0 to skip these tests or if you are not running the upstream services locally.

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

# Local DEV: Redis
REDIS_BACKEND=fake
REDIS_URL=redis://localhost:6379/0
REDIS_ENABLED=true
REDIS_DEFAULT_TTL_SECONDS=300
```

2. Build and run the stack

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

3. Test the API

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

### Running Locally Without Docker

To run the application without Docker, you need to have a Python environment set up and `uv` installed. You also need to have the credentials for the various services configured in your environment.

1. Install dependencies

```bash
uv sync --locked
```

2. Run the application

```bash
uv run --locked uvicorn brokerage_service_api.api.app:app --reload --port 8020
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
