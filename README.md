# Kilo Models Dashboard

A Django dashboard that lists the models available from the [Kilo Gateway API](https://ai-gateway.kilo.ai/api/v1/models), showing relevant details for each model and making it easy to search, filter, compare, and copy data.

## Features

- **Model cards & table view** — toggle between a card grid and a dense, sortable table for comparing many models at once.
- **Search** — filters by model name only, triggered on Enter (e.g. `deepseek 4.1` matches `DeepSeek V4.1`).
- **Filters** — provider and reasoning-option dropdowns populated from the union of values across all models, sorted by logical complexity.
- **Dark mode** — persisted to `localStorage`, applied before paint to avoid a flash.
- **Copy actions**:
  - Per-model copy button copies that model's full JSON (pretty-printed).
  - Per-ID copy button copies the model ID.
  - **Copy All** copies the raw API response exactly as returned.
- **Short TTL cache** (default 300s) to avoid hammering the upstream API on every request.

## Requirements

- [uv](https://docs.astral.sh/uv/) (Python 3.13 is pinned via `.python-version`)

## Setup

```sh
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Then open http://127.0.0.1:8000/.

## Configuration

Configuration is read from environment variables (all optional):

| Variable | Default | Description |
| --- | --- | --- |
| `KILO_GATEWAY_API_URL` | `https://ai-gateway.kilo.ai/api/v1/models` | Upstream models endpoint |
| `KILO_GATEWAY_CACHE_TIMEOUT` | `300` | Cache TTL in seconds |
| `DJANGO_SECRET_KEY` | dev key | Django secret key (set in production) |
| `DJANGO_DEBUG` | `1` | Set `0` in production |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated allowed hosts |

> The default cache uses Django's in-memory (`locmem`) backend, which is fine for the development server. Use Redis or Memcached behind multiple workers in production.

## Project layout

```
kilo_dashboard/          # Django project package (settings, urls, wsgi/asgi)
dashboard/               # Django app (views, templates, static assets)
  templates/dashboard/   # base.html, index.html
  static/dashboard/      # CSS and JavaScript
manage.py
pyproject.toml           # uv project configuration
```
