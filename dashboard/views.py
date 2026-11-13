"""Views for the dashboard app."""

import json
import urllib.request
import urllib.error

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render

CACHE_KEY = "kilo_models_data"


def fetch_models_from_api():
    """Fetch model list from the Kilo Gateway API.

    Returns a tuple of (normalized_models, raw_json_text). The raw JSON is
    the exact response body so it can be copied verbatim. Results are cached
    for a short TTL to avoid hammering the upstream API.
    """
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    api_url = settings.KILO_GATEWAY_API_URL
    try:
        req = urllib.request.Request(api_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_text = response.read().decode("utf-8")
        data = json.loads(raw_text)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return [], ""

    # Normalize the response into a list of model dicts
    models = []
    if isinstance(data, dict):
        # API might wrap results in a key like "models", "data", "results"
        for key in ("models", "data", "results", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            # If no list found, wrap the single dict
            data = [data] if data else []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                models.append(normalize_model(item))

    result = (models, raw_text)
    cache.set(CACHE_KEY, result, timeout=settings.KILO_GATEWAY_CACHE_TIMEOUT)
    return result


def _format_pricing(pricing):
    """Format a pricing object into a readable string."""
    if not isinstance(pricing, dict) or not pricing:
        return ""
    parts = []
    if pricing.get("prompt"):
        parts.append(f"prompt: ${pricing['prompt']}")
    if pricing.get("completion"):
        parts.append(f"completion: ${pricing['completion']}")
    if pricing.get("input_cache_read"):
        parts.append(f"cache read: ${pricing['input_cache_read']}")
    if pricing.get("input_cache_write"):
        parts.append(f"cache write: ${pricing['input_cache_write']}")
    if pricing.get("web_search"):
        parts.append(f"web search: ${pricing['web_search']}")
    if pricing.get("discount"):
        parts.append(f"discount: {pricing['discount']}%")
    return " | ".join(parts)


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


def _format_reasoning_options(val):
    """Format reasoning_options into a readable, complexity-sorted string."""
    values = _extract_reasoning_values(val)
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
    reasoning_str = _format_reasoning_options(reasoning_opts)

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

    # supported parameters / capabilities
    supported_params = item.get("supported_parameters") or []

    return {
        "id": item.get("id") or item.get("model_id") or item.get("name", ""),
        "name": item.get("name") or item.get("display_name") or item.get("id", ""),
        "provider": provider_str,
        "pricing": pricing_str,
        "reasoning_options": reasoning_str,
        "reasoning_values": reasoning_values,
        "context_length": context_len if context_len is not None else "",
        "capabilities": supported_params,
        "description": item.get("description") or "",
        "architecture": arch_modality,
        "created": item.get("created"),
        "raw": item,
    }


def model_list(request):
    """Display the list of models with search and filtering."""
    all_models, raw_json = fetch_models_from_api()

    # Collect distinct providers for the filter dropdown from ALL models
    # (union of values, independent of current filters)
    all_providers = set()
    for m in all_models:
        if m["provider"]:
            for p in m["provider"].split(","):
                p = p.strip()
                if p:
                    all_providers.add(p)
    providers = sorted(all_providers)

    # Collect distinct individual reasoning options from ALL models
    # (sorted by logical complexity: none -> max)
    reasoning_options = sorted(
        {v for m in all_models for v in m["reasoning_values"]},
        key=_reasoning_sort_key,
    )

    # Search filter (model name only)
    search_query = request.GET.get("search", "").strip()
    if search_query:
        tokens = [t.lower() for t in search_query.split()]
        models = [
            m for m in all_models
            if all(t in m["name"].lower() for t in tokens)
        ]
    else:
        models = all_models

    # Provider filter (substring match since provider is comma-joined)
    provider_filter = request.GET.get("provider", "").strip()
    if provider_filter:
        models = [
            m for m in models
            if provider_filter.lower() in m["provider"].lower()
        ]

    # Reasoning options filter (match individual values)
    reasoning_filter = request.GET.get("reasoning", "").strip()
    if reasoning_filter:
        models = [
            m for m in models
            if reasoning_filter.lower() in [v.lower() for v in m["reasoning_values"]]
        ]

    context = {
        "models": models,
        "search_query": search_query,
        "provider_filter": provider_filter,
        "reasoning_filter": reasoning_filter,
        "providers": providers,
        "reasoning_options": reasoning_options,
        "total_count": len(models),
        "raw_json": raw_json,
    }
    return render(request, "dashboard/index.html", context)
