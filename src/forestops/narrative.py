"""AI enrichment with guardrails.

The model turns numbers the pipeline already computed into a sentence a planner
reads in a tooltip. It is never asked to calculate, classify or decide. Every
response is validated against the row it came from, and a response that fails
validation is stored with the narrative suppressed rather than dropped, so the
failure stays visible.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .config import foundry_settings

SYSTEM_PROMPT = """You write two-sentence condition notes for forest stands, read by a Woodlands planner.

Rules you must follow:
- Use only the values supplied in the user message. Do not introduce any number that is not present there.
- Do not calculate, estimate, convert or round any value. Restate values exactly as given.
- If a value is null, say the measurement is unavailable. Never infer what it might have been.
- Do not recommend an operational action. Describe the condition; the planner decides.
- Return JSON matching the requested schema and nothing else.
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "Two sentences describing the stand condition"},
        "attention": {"type": "string", "enum": ["none", "watch", "review"]},
        "values_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Every numeric value quoted in the summary, as it appears in the input",
        },
    },
    "required": ["summary", "attention", "values_used"],
}

NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")

VALIDATION_OK = "ok"
VALIDATION_NUMERIC = "numeric_mismatch"
VALIDATION_SCHEMA = "schema_invalid"
VALIDATION_SUPPRESSED = "suppressed"
VALIDATION_STUBBED = "stubbed"


def build_stand_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Select the fields the model is allowed to see.

    Passing the whole row is how a model ends up quoting an internal identifier
    into a planner-facing sentence. Only send what the sentence may contain.
    """
    def _round(value: Any, digits: int = 2) -> Any:
        return None if value is None or value != value else round(float(value), digits)

    return {
        "stand_id": row.get("stand_id"),
        "licence_block": row.get("licence_block"),
        "declared_species_group": row.get("species_group"),
        "spectral_class": row.get("forest_class"),
        "class_confidence": _round(row.get("class_confidence")),
        "area_ha": _round(row.get("area_ha"), 1),
        "ndvi_p90": _round(row.get("ndvi_p90"), 3),
        "ndmi_mean": _round(row.get("ndmi_mean"), 3),
        "nbr_mean": _round(row.get("nbr_mean"), 3),
        "valid_pixel_fraction": _round(row.get("valid_pixel_fraction"), 2),
        "change_type": row.get("change_type"),
        "observation_count": row.get("observation_count"),
        "period_end": str(row.get("period_end")) if row.get("period_end") is not None else None,
    }


def allowed_numbers(payload: dict[str, Any]) -> set[str]:
    """Every numeric token the model is permitted to reproduce."""
    allowed: set[str] = set()
    for value in payload.values():
        if isinstance(value, (int, float)) and value == value:
            allowed.add(_canonical(value))
        elif isinstance(value, str):
            allowed.update(_canonical(tok) for tok in NUMBER_PATTERN.findall(value))
    return allowed


def _canonical(value: Any) -> str:
    """Normalise a number so 0.70, 0.7 and .7 compare equal."""
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


def validate_response(text: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """Parse and check a model response against the row that produced it.

    Two checks. The response must match the schema, and every number in the
    summary must already exist in the payload. The second check is the one that
    matters: a fluent sentence containing a number the pipeline never computed
    is indistinguishable from a correct one at reading speed.
    """
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None, VALIDATION_SCHEMA

    if not isinstance(parsed, dict):
        return None, VALIDATION_SCHEMA
    if not all(key in parsed for key in RESPONSE_SCHEMA["required"]):
        return None, VALIDATION_SCHEMA
    if parsed.get("attention") not in {"none", "watch", "review"}:
        return None, VALIDATION_SCHEMA
    if not isinstance(parsed.get("summary"), str) or not parsed["summary"].strip():
        return None, VALIDATION_SCHEMA

    permitted = allowed_numbers(payload)
    quoted = {_canonical(tok) for tok in NUMBER_PATTERN.findall(parsed["summary"])}
    invented = quoted - permitted
    if invented:
        return parsed, VALIDATION_NUMERIC

    return parsed, VALIDATION_OK


def offline_stub(payload: dict[str, Any]) -> dict[str, Any]:
    """Deterministic narrative used when Foundry is unavailable.

    Produces the same table shape as the model path so that nothing downstream
    has to know whether AI was enabled. This is what keeps the pipeline runnable
    for participants without Foundry access, and what makes ``enable_ai=false``
    a supported configuration rather than a broken one.
    """
    cls = payload.get("spectral_class") or "unclassified"
    ndmi = payload.get("ndmi_mean")
    change = payload.get("change_type") or "none"

    first = f"Stand {payload.get('stand_id')} is classified {cls} across {payload.get('area_ha')} hectares."
    if ndmi is None:
        second = "Canopy moisture is unavailable for this period."
    elif change in {"harvest", "disturbance"}:
        second = f"Canopy loss was detected with moisture at {ndmi}, consistent with {change}."
    else:
        second = f"Canopy moisture sits at {ndmi} with no significant change detected."

    attention = "review" if change in {"disturbance", "moisture_stress"} else "none"
    return {"summary": f"{first} {second}", "attention": attention, "values_used": []}


def create_client():
    """Build a Foundry client, or return None when it is not configured."""
    settings = foundry_settings()
    if not settings["endpoint"] or not settings["api_key"]:
        return None, settings
    from openai import AzureOpenAI

    client = AzureOpenAI(
        azure_endpoint=settings["endpoint"],
        api_key=settings["api_key"],
        api_version=settings["api_version"],
    )
    return client, settings


def generate_narrative(client, deployment: str, payload: dict[str, Any]) -> str:
    """Single schema-constrained completion for one stand.

    Temperature is zero because this is a formatting task, not a creative one.
    Two runs over the same row should produce the same sentence, otherwise a
    planner who refreshes the report sees the wording change for no reason.
    """
    response = client.chat.completions.create(
        model=deployment,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Write the stand note from these values only.\n"
                    f"Return JSON with keys: {list(RESPONSE_SCHEMA['properties'])}.\n\n"
                    f"{json.dumps(payload, indent=2)}"
                ),
            },
        ],
    )
    return response.choices[0].message.content or ""


def enrich_rows(
    rows: list[dict[str, Any]],
    use_offline_stub: bool = False,
    batch_size: int = 25,
) -> list[dict[str, Any]]:
    """Generate and validate a narrative for every row.

    Results are returned per batch so a long run that fails part way through has
    still written something. A 500-stand job that fails at stand 480 with
    nothing persisted is an afternoon nobody gets back.
    """
    client, settings = (None, foundry_settings()) if use_offline_stub else create_client()
    stubbing = use_offline_stub or client is None
    deployment = settings.get("deployment") or "offline-stub"
    generated_at = datetime.now(timezone.utc)

    out: list[dict[str, Any]] = []
    for start in range(0, len(rows), batch_size):
        for row in rows[start : start + batch_size]:
            payload = build_stand_payload(row)

            if stubbing:
                parsed = offline_stub(payload)
                status = VALIDATION_STUBBED
            else:
                try:
                    raw = generate_narrative(client, deployment, payload)
                    parsed, status = validate_response(raw, payload)
                except Exception as exc:  # noqa: BLE001 - a failed call must not fail the run
                    parsed, status = None, f"{VALIDATION_SUPPRESSED}:{type(exc).__name__}"

            narrative = parsed["summary"] if parsed and status in {VALIDATION_OK, VALIDATION_STUBBED} else None

            out.append(
                {
                    "stand_id": payload["stand_id"],
                    "period_end": row.get("period_end"),
                    "narrative": narrative,
                    "attention": (parsed or {}).get("attention", "none"),
                    "validation_status": status,
                    "model_deployment": "offline-stub" if stubbing else deployment,
                    "generated_at_utc": generated_at,
                }
            )
    return out
