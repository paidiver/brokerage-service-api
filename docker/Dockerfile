FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.9.22 /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /code
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-install-project

FROM base AS development
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group test --group lint --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --group test --group lint
EXPOSE 8020
CMD ["uvicorn", "brokerage_service_api.api.app:app", "--host", "0.0.0.0", "--port", "8020", "--reload"]

FROM base AS runtime
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-editable
EXPOSE 8020
CMD ["uvicorn", "brokerage_service_api.api.app:app", "--host", "0.0.0.0", "--port", "8020", "--workers", "5"]
