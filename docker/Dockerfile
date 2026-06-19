FROM python:3.13-slim

# Set environment varibles
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /code/

RUN apt-get update
RUN apt-get install -y apt-utils build-essential
RUN rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

RUN pip install poetry

ENV POETRY_VIRTUALENVS_CREATE=false
ENV POETRY_VIRTUALENVS_IN_PROJECT=false

COPY . /code/

# RUN poetry config virtualenvs.create false
# RUN poetry install -vvv --no-interaction --no-ansi
RUN poetry install -vvv --with dev,test,lint --no-interaction --no-ansi
EXPOSE 8081
CMD ["poetry", "run", "uvicorn", "brokerage_service_api.api.app:app", "--host", "0.0.0.0", "--port", "8081", "--workers", "5", "--reload"]
