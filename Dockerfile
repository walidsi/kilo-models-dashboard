ARG PYTHON_VERSION=3.13-slim

FROM python:${PYTHON_VERSION}

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir -p /code

WORKDIR /code

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

RUN uv run --no-sync python manage.py collectstatic --noinput

ENV SECRET_KEY "OTaTd6uC5uqjDn6YzL5EgGIwWeqgZJxtuWv3ytbBwoQTpqkmEH"

EXPOSE 8080

# Suitable for a temporary test, not production.
CMD ["uv", "run", "--no-sync", "python", "manage.py", "runserver", "0.0.0.0:8080"]COPY . /code

