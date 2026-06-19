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
├── api/                # Django app (API)
├── config/             # Django project configuration
├── docker/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── scripts/
│       └── wait-for-it.sh
├── manage.py
├── pyproject.toml      # Project metadata & dependencies (Poetry)
├── poetry.lock         # Locked dependency versions
├── tox.ini             # Test, lint, and format automation
├── ruff.toml           # Ruff configuration
├── README.md
├── LICENSE
└── .env.example
```

## Dependency Management

This project uses **Poetry** for dependency management and packaging.

Key points:

* Dependencies are defined in `pyproject.toml`
* Locked versions live in `poetry.lock`
* Development tools (linting, formatting, testing) are installed via Poetry groups

## Quick Start (Docker – Recommended)

### 1. Create environment file

Configuration is provided via environment variables defined in `.env`.

Start from the example file:

```bash
cp .env.example .env
```

Example contents:

```bash
# ENV APIS
JNCC_URL=http://annotations-api1:8000/api
BODC_URL=http://annotations-api2:8000/api


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

* Start PostgreSQL/PostGIS
* Run Django migrations
* Start the Django development server

### 3. Test the API

Health endpoint:

```
http://localhost:8000/api/health/
```

Expected response:

```json
{"status": "ok"}
```

API schema and documentation:

```
http://localhost:8000/api/docs/
```

### 4. Worms cache API

If you set the environment variable `CACHED_WORMS_API_BASE_URL` to point to a local instance of the WoRMS cache API, you may need to start that separately. Please follow the instructions in the [worms-cache repo](https://github.com/paidiver/worms-cache).


## Running Locally Without Docker

### 1. Install dependencies

```bash
poetry install
```

### 2. Start only the database via Docker

```bash
docker compose -f docker/docker-compose.yml up -d db
```

### 3. Apply migrations

```bash
python manage.py migrate
```

### 4. Run the development server

```bash
python manage.py runserver
```

## Database Migrations

Create new migrations after modifying models:

```bash
docker compose -f docker/docker-compose.yml exec api python manage.py makemigrations
```

To add some descriptive name to migration file that is going to generate, use `--name` flag while running migration command. And once the migration file is created, make sure to add some descriptive docstring on top of the file as well.

```bash
docker compose -f docker/docker-compose.yml exec api python manage.py makemigrations --name migration_description
```

Apply migrations:

```bash
docker compose -f docker/docker-compose.yml exec api python manage.py migrate
```

## Development Workflow

### Formatting

Format code using Ruff:

```bash
tox -e format

# or using Docker
docker compose -f docker/docker-compose.yml run --rm api tox -e format
```

### Linting

Run lint checks:

```bash
tox -e lint

# or using Docker
docker compose -f docker/docker-compose.yml run --rm api tox -e lint
```

### Tests

Run the test suite with coverage:

```bash
tox
```

or explicitly:

```bash
docker compose -f docker/docker-compose.yml run --rm api tox -e py313
```

Coverage reports are written to `coverage_reports/`.

## API Token Generation

This project is configured to use [TokenAuthentication](https://www.django-rest-framework.org/api-guide/authentication/#tokenauthentication)
for any requests that modify data. Anonymous users may only use "safe" methods (`GET`, `HEAD` or `OPTIONS`).
The project includes a management command to create a new user with an auth token:

```bash
python manage.py create_user_with_token <username> <password>
```

The created API token is returned in the command output. Please ensure to store this token safely.
Remove shell history to keep sensitive data like passwords safe.

Example output:
```
User created: myUser. API token (please store this securely): 1fa4a1e49e43bad0b96bf26e8bbcde0379892374
```

Clearing shell history:
```bash
paidiver@annotations-api:/app$ python manage.py create_user_with_token <user> <password>
User created: <user>. API token (please store this securely): <token>
paidiver@annotations-api:/app$ history
    1  python manage.py create_user_with_token <user> <password>
    2  history
paidiver@annotations-api-f45db94cc-p2fsm:/app$ history -d 1
paidiver@annotations-api-f45db94cc-p2fsm:/app$ clear
paidiver@annotations-api-f45db94cc-p2fsm:/app$ history
    1  history
    2  history -d 1
    3  clear
    4  history
```

## Fake Data Generation

For development and testing, the project includes a management command that seeds the database with realistic fake data:

```bash
docker compose -f docker/docker-compose.yml run --rm api \
  python manage.py seed_demo_data
```

### Customising the amount of data

```bash
python manage.py seed_demo_data \
  --image-annotation-sets 3 \
  --images-per-image-set 15 \
  --labels-per-annotation-set 25 \
  --annotators 12 \
  --annotations-per-image 3 \
  --annotation-labels 150
```

⚠️ IMPORTANT: Development use only. Do not run against production databases.

## Dumping All Data (JSON)

To export **all database data as JSON** for inspection or debugging, use the endpoint:

```
http://localhost:8000/api/debug/db-dump/
```

This will return a JSON object containing all records from all tables, structured by model name.


## API Examples

A collection of example API requests and responses is available in the [API Examples](docs/API_EXAMPLES.md) document.

## Acknowledgements

This project was supported by the UK Natural Environment Research Council (NERC) through the *Tools for automating image analysis for biodiversity monitoring (AIAB)* Funding Opportunity, reference code **UKRI052**.
