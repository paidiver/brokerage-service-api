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
│   ├── docker-compose.yml # Docker compose file for local development
│   └── Dockerfile      # Dockerfile for the API service
├── LICENSE
├── pyproject.toml      # Project metadata & dependencies (Poetry)
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


## Deployment

The [charts](charts/) directory contains Helm charts and files that can be used to deploy this app.

### Helm Chart Versioning & Release Process

Helm chart releases are automated and driven by Git tags.

To release a new Helm Chart version, create a Git tag in the format:

`vMAJOR.MINOR.PATCH[-PRERELEASE]`

Examples:
- `v1.2.3` → stable release
- `v1.3.0-alpha.1` → prerelease

The workflow triggers on tag creation.
The CI workflow:

- Reads the tag version (1.2.3 from v1.2.3)
- Patches charts/api/Chart.yaml at package time (does not commit to the repo)
- Packages the Helm chart with the correct version
- Publishes the chart via [helm/chart-releaser-action](https://github.com/helm/chart-releaser-action)

Whenever you make any change to a Chart, you must update the version in `Chart.yaml`.

* Increment the version to a higher value (e.g. `0.0.0-dev` → `0.0.1-dev`)
* This is required because the lint process checks that the new version is greater than the previous one
* If the version is not increased, linting will fail and the release will not run

> Note: The `Chart.yaml` version does not need to match the Git tag, but it must always be higher than the previous version.

To tag a git commit:

```bash
git tag vX.X.X
git push origin vX.X.X
```


## Releasing Docker Images

### Production release
A new `latest` Docker image is build and published to https://ghcr.io/paidiver/annotations-api on each push to main.

### Development release
Development versions of Docker images can be released manually, driven by Git tags.
To release a new Docker image, create a Git tag in the format:

`docker-vMAJOR.MINOR.PATCH[-PRERELEASE]`

Examples:
- `v1.2.3` → stable release
- `v1.3.0-alpha.1` → prerelease

The workflow triggers on tag creation.
The CI workflow:

- Reads the tag version (1.2.3 from docker-v1.2.3)
- Builds a new Docker image
- Tags the Docker image with the tag version as well as the tagged commit SHA
- Pushes the images to the GitHub Container Repository

To tag a git commit:

```bash
git tag docker-vX.X.X
git push origin docker-vX.X.X
```


## Deploying locally with Kubernetes

For local Kubernetes, use Helm directly against the API chart. The Helmfile in [charts/helmfile.yaml.gotmpl](charts/helmfile.yaml.gotmpl) is intended for the JASMIN `dev` and `live` deployments because it creates namespaces, GHCR pull secrets, and ClusterIssuers.

The local values file is [charts/env/local/values.yaml](charts/env/local/values.yaml). It disables ingress and image pull secrets, and uses a local image named `brokerage-service-api:local`.

### 1. Build the local image

```bash
docker build -f docker/Dockerfile -t brokerage-service-api:local .
```

If you use `kind`, load the image into the cluster:

```bash
kind load docker-image brokerage-service-api:local
```

If you use Minikube, build inside the Minikube Docker daemon instead:

```bash
eval "$(minikube docker-env)"
docker build -f docker/Dockerfile -t brokerage-service-api:local .
```

### 2. Install or upgrade the chart

```bash
helm upgrade --install brokerage-service-api charts/api \
  --namespace brokerage-service-api-local \
  --create-namespace \
  -f charts/env/local/values.yaml
```

To use a published GHCR image instead of a local image:

```bash
helm upgrade --install brokerage-service-api charts/api \
  --namespace brokerage-service-api-local \
  --create-namespace \
  -f charts/env/local/values.yaml \
  --set image.repository=ghcr.io/paidiver/brokerage-service-api \
  --set image.tag=latest
```

To point the local deployment at different upstream services, override the chart values:

```bash
helm upgrade --install brokerage-service-api charts/api \
  --namespace brokerage-service-api-local \
  --create-namespace \
  -f charts/env/local/values.yaml \
  --set env.bodcAnnotationsApiUrl=https://annotationsdev.bodc.ac.uk/api \
  --set env.jnccAnnotationsApiUrl=https://annotations-api.paidiver.site
```

### 3. Check and connect

```bash
kubectl get pods -n brokerage-service-api-local
kubectl get svc -n brokerage-service-api-local
kubectl port-forward -n brokerage-service-api-local svc/brokerage-service-api-service 8080:80
```

Health endpoint:

```
http://localhost:8080/health/
```

API schema and documentation:

```
http://localhost:8080/docs/
```

To remove the local release:

```bash
helm uninstall brokerage-service-api -n brokerage-service-api-local
```

## Upstream Sources

Upstream API sources are managed within the configuration file located at [*fixtures/source.yaml*](./src/brokerage_service_api/fixtures/source.yaml). This file is parsed and loaded into the application's memory during initialization (startup) and remains immutable throughout the application's lifespan.

### Example source:

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

### Configuring new source

To onboard a new upstream source, follow these steps:

#### 1. Update the YAML Configuration:

Add the new source block under the `sources` key in [*fixtures/source.yaml*](./src/brokerage_service_api/fixtures/source.yaml). Set the `base_url` value to match the corresponding environment variable name.

#### 2. Define Environment Variables:

Declare the environment variable name and its value in your locally managed [.env] file.

#### 3. Register the Environment Mapping:

Add a new key-value entry to the `ENV_SOURCE_URL_MAP` dictionary inside [*fixtures/constants.py*](./src/brokerage_service_api/fixtures/constants.py). This maps the source identifier to its environment variable name and an isolated container fallback URL.

```python
ENV_SOURCE_URL_MAP = {
    # Existing mappings...
    "new_source_name": ("EXAMPLE_ANNOTATIONS_API_URL", "http://example-api:8000/api/"),
}
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
