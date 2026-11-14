"""Views for the dashboard app."""

import json
import logging
import ssl
import urllib.error
import urllib.request

import certifi
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

CACHE_KEY = "kilo_models_data"


def fetch_models_from_api():
    """Fetch and normalize the model list from the Kilo Gateway API.

    Returns a dict with:
      - "models": normalized model dicts (no raw payload embedded)
      - "raw_text": the exact upstream response body, for verbatim copying
      - "raw_by_id": {model_id: raw upstream dict} for O(1) detail lookups
      - "providers", "reasoning_options", "modalities": precomputed filter options

    The whole normalized result is cached for a short TTL so the per-request
    work is reduced to filtering + rendering rather than re-parsing.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    api_url = settings.KILO_GATEWAY_API_URL
    try:
        # On Wasmer/WASIX there is no system CA bundle, so HTTPS certificate
        # verification fails by default. Use certifi's bundled CA roots.
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        req = urllib.request.Request(api_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15, context=ssl_context) as response:
            raw_text = response.read().decode("utf-8")
        data = json.loads(raw_text)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        logger.exception("Failed to fetch models from %s", api_url)
        return {
            "models": [],
            "raw_text": "",
            "raw_by_id": {},
            "providers": [],
            "reasoning_options": [],
            "modalities": [],
        }

    # Normalize the response into a list of model dicts
    if isinstance(data, dict):
        # API might wrap results in a key like "models", "data", "results"
        for key in ("models", "data", "results", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            # If no list found, wrap the single dict
            data = [data] if data else []

    models = []
    raw_by_id = {}
    all_providers = set()
    reasoning_values_set = set()
    modalities_set = set()

    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            model = normalize_model(item)
            models.append(model)

            # Index raw payloads once for O(1) detail lookups instead of
            # scanning the model list per request.
            model_id = model["id"]
            if model_id and model_id not in raw_by_id:
                raw_by_id[model_id] = item

            # Precompute filter options while we already have each model at hand.
            for provider in model["provider"].split(","):
                provider = provider.strip()
                if provider:
                    all_providers.add(provider)
            reasoning_values_set.update(model["reasoning_values"])
            modalities_set.update(model["architecture_input"])

    result = {
        "models": models,
        "raw_text": raw_text,
        "raw_by_id": raw_by_id,
        "providers": sorted(all_providers),
        "reasoning_options": sorted(reasoning_values_set, key=_reasoning_sort_key),
        "modalities": sorted(modalities_set),
    }
    cache.set(CACHE_KEY, result, timeout=settings.KILO_GATEWAY_CACHE_TIMEOUT)
    return result


# Token-priced fields mapped to human-friendly labels. The API returns
# per-token prices; we display them per 1M tokens (the industry standard).
PRICING_LABELS = [
    ("prompt", "Input"),
    ("completion", "Output"),
    ("input_cache_read", "Cache read"),
    ("input_cache_write", "Cache write"),
]


def _to_per_million(raw):
    """Convert a per-token price to dollars per 1M tokens, or None."""
    if raw is None or raw == "":
        return None
    try:
        return float(raw) * 1_000_000
    except (TypeError, ValueError):
        return None


def _fmt_usd(value):
    """Format a dollar amount with sensible precision."""
    if value >= 1:
        return f"${value:,.2f}"
    if value >= 0.01:
        return f"${value:.2f}"
    return f"${value:.4f}"


def _format_number(value):
    """Format a large integer into a scannable form (1M, 131K, etc.)."""
    if value is None or value == "":
        return ""
    try:
        num = int(float(value))
    except (TypeError, ValueError):
        return str(value)
    if num >= 1_000_000:
        return f"{round(num / 1_000_000)}M"
    if num >= 1_000:
        return f"{round(num / 1_000)}K"
    return str(num)


def _format_pricing(pricing):
    """Format a pricing object into a readable, per-1M-token string."""
    if not isinstance(pricing, dict) or not pricing:
        return ""
    parts = []
    for key, label in PRICING_LABELS:
        per_million = _to_per_million(pricing.get(key))
        if per_million is not None:
            parts.append(f"{label} {_fmt_usd(per_million)}/1M")
    # web_search is a flat per-request price, not per-token.
    web_search = pricing.get("web_search")
    if web_search not in (None, ""):
        try:
            parts.append(f"Web search {_fmt_usd(float(web_search))}/req")
        except (TypeError, ValueError):
            pass
    return "\n".join(parts)


# Logical complexity order for reasoning effort values (none -> max)
REASONING_ORDER = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]


def _reasoning_sort_key(value):
    """Sort reasoning values by logical complexity, unknown values last."""
    key = str(value).lower()
    if key in REASONING_ORDER:
        return (0, REASONING_ORDER.index(key), key)
    return (1, 0, key)


def _reasoning_values_from_entry(entry):
    """Return the individual reasoning values from an option entry's `values` key.

    Only the `values` key is used. Entries like `{"type": "toggle"}` that have
    no `values` list contribute nothing to the dropdown.
    """
    if not isinstance(entry, dict):
        if entry is None or entry == "":
            return []
        return [str(entry)]

    vals = entry.get("values")
    if not isinstance(vals, list):
        return []

    result = []
    for v in vals:
        if isinstance(v, bool):
            result.append("on" if v else "off")
        else:
            result.append(str(v))
    return result


def _extract_reasoning_values(val):
    """Extract individual reasoning option values from the raw structure.

    The API nests options like:
        [{"type": "effort", "values": ["low", "medium", ...]}]
    Returns a flat list of individual values (e.g. ["low", "medium", ...]).
    """
    values = []
    if isinstance(val, list):
        for r in val:
            values.extend(_reasoning_values_from_entry(r))
    else:
        values.extend(_reasoning_values_from_entry(val))
    return values


def _format_reasoning_values(values):
    """Format an extracted reasoning-values list into a readable, sorted string."""
    if not values:
        return ""
    unique = sorted(set(values), key=_reasoning_sort_key)
    return ", ".join(unique)


def normalize_model(item):
    """Normalize a raw API model dict into a consistent shape."""
    opencode = item.get("opencode") if isinstance(item.get("opencode"), dict) else {}

    # reasoning_options — nested under opencode.reasoning_options
    reasoning_opts = item.get("reasoning_options") or opencode.get("reasoning_options")
    reasoning_values = _extract_reasoning_values(reasoning_opts)
    reasoning_str = _format_reasoning_values(reasoning_values)

    # pricing — format the object into a readable string
    pricing_raw = item.get("pricing") or {}
    pricing_str = _format_pricing(pricing_raw)

    # provider — from inference_provider_ids (array) or opencode.ai_sdk_provider
    provider_ids = item.get("inference_provider_ids")
    if isinstance(provider_ids, list) and provider_ids:
        provider_str = ", ".join(str(p) for p in provider_ids)
    else:
        provider_str = (
            opencode.get("ai_sdk_provider")
            or item.get("provider")
            or item.get("organization")
            or ""
        )

    # context_length — top level or nested under top_provider
    context_len = item.get("context_length")
    if context_len is None and isinstance(item.get("top_provider"), dict):
        context_len = item["top_provider"].get("context_length")

    # architecture modality
    arch = item.get("architecture")
    arch_modality = arch.get("modality") if isinstance(arch, dict) else ""
    arch_input = arch.get("input_modalities") if isinstance(arch, dict) else []
    arch_output = arch.get("output_modalities") if isinstance(arch, dict) else []
    arch_input = arch_input if isinstance(arch_input, list) else []

    # supported parameters / capabilities
    supported_params = item.get("supported_parameters") or []

    name = item.get("name") or item.get("display_name") or item.get("id", "")

    return {
        "id": item.get("id") or item.get("model_id") or name,
        "name": name,
        # Lowercased copies precomputed once so per-request filtering does not
        # re-run .lower() (or build new lists) for every model on every request.
        "name_lower": name.lower(),
        "provider": provider_str,
        "provider_lower": provider_str.lower(),
        "pricing": pricing_str,
        "reasoning_options": reasoning_str,
        "reasoning_values": reasoning_values,
        "reasoning_values_lower": tuple(v.lower() for v in reasoning_values),
        "context_length": context_len if context_len is not None else "",
        "context_length_display": _format_number(context_len),
        "capabilities": supported_params,
        "description": item.get("description") or "",
        "architecture": arch_modality,
        "architecture_input": arch_input,
        "architecture_input_lower": tuple(v.lower() for v in arch_input),
        "architecture_output": arch_output if isinstance(arch_output, list) else [],
        "created": item.get("created"),
    }


@require_GET
def api_models(request):
    """Return the raw upstream API response verbatim."""
    data = fetch_models_from_api()
    payload = data["raw_text"] if data["raw_text"] else "[]"
    return HttpResponse(payload.encode("utf-8"), content_type="application/json")


@require_GET
def api_model_detail(request, model_id):
    """Return the raw upstream dict for a single model as JSON."""
    data = fetch_models_from_api()
    raw = data["raw_by_id"].get(model_id)
    if raw is None:
        return JsonResponse({"error": "Model not found"}, status=404)
    return JsonResponse(raw)


def model_list(request):
    """Display the list of models with search and filtering."""
    data = fetch_models_from_api()
    all_models = data["models"]

    # Search filter (model name only)
    search_query = request.GET.get("search", "").strip()
    if search_query:
        tokens = [t.lower() for t in search_query.split()]
        models = [
            m for m in all_models
            if all(t in m["name_lower"] for t in tokens)
        ]
    else:
        models = all_models

    # Provider filter (substring match since provider is comma-joined)
    provider_filter = request.GET.get("provider", "").strip()
    if provider_filter:
        provider_lower = provider_filter.lower()
        models = [
            m for m in models
            if provider_lower in m["provider_lower"]
        ]

    # Modality filter (match individual input modalities)
    modality_filter = request.GET.get("modality", "").strip()
    if modality_filter:
        modality_lower = modality_filter.lower()
        models = [
            m for m in models
            if modality_lower in m["architecture_input_lower"]
        ]

    # Reasoning options filter (match individual values)
    reasoning_filter = request.GET.get("reasoning", "").strip()
    if reasoning_filter:
        reasoning_lower = reasoning_filter.lower()
        models = [
            m for m in models
            if reasoning_lower in m["reasoning_values_lower"]
        ]

    # Determine which view to render server-side. The client can request a
    # specific view via query param; otherwise fall back to a cookie so the
    # last chosen view persists across navigations.
    active_view = request.GET.get("view", "").strip()
    if active_view not in ("grid", "table"):
        active_view = request.COOKIES.get("kilo_view", "grid")
    if active_view not in ("grid", "table"):
        active_view = "grid"

    context = {
        "models": models,
        "search_query": search_query,
        "provider_filter": provider_filter,
        "modality_filter": modality_filter,
        "reasoning_filter": reasoning_filter,
        "providers": data["providers"],
        "modalities": data["modalities"],
        "reasoning_options": data["reasoning_options"],
        "total_count": len(models),
        "active_view": active_view,
    }
    response = render(request, "dashboard/index.html", context)
    response.set_cookie("kilo_view", active_view, max_age=60 * 60 * 24 * 365)
    return response
