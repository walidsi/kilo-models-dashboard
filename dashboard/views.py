"""Views for the dashboard app."""

import json
import logging
import ssl
import urllib.request
import urllib.error

import certifi
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import render

logger = logging.getLogger(__name__)

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
        # On Wasmer/WASIX there is no system CA bundle, so HTTPS certificate
        # verification fails by default. Use certifi's bundled CA roots.
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        req = urllib.request.Request(api_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15, context=ssl_context) as response:
            raw_text = response.read().decode("utf-8")
        data = json.loads(raw_text)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        logger.exception("Failed to fetch models from %s", api_url)
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
    arch_input = arch.get("input_modalities") if isinstance(arch, dict) else []
    arch_output = arch.get("output_modalities") if isinstance(arch, dict) else []

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
        "context_length_display": _format_number(context_len),
        "capabilities": supported_params,
        "description": item.get("description") or "",
        "architecture": arch_modality,
        "architecture_input": arch_input if isinstance(arch_input, list) else [],
        "architecture_output": arch_output if isinstance(arch_output, list) else [],
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

    # Collect distinct input modalities (architecture values) from ALL models
    modalities = sorted({v for m in all_models for v in m["architecture_input"]})

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

    # Modality filter (match individual input modalities)
    modality_filter = request.GET.get("modality", "").strip()
    if modality_filter:
        models = [
            m for m in models
            if modality_filter.lower() in [v.lower() for v in m["architecture_input"]]
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
        "modality_filter": modality_filter,
        "reasoning_filter": reasoning_filter,
        "providers": providers,
        "modalities": modalities,
        "reasoning_options": reasoning_options,
        "total_count": len(models),
        "raw_json": raw_json,
    }
    return render(request, "dashboard/index.html", context)
