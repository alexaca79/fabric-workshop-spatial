# %% [markdown]
# # Lab 04 - Validate offline stand narratives
#
# Build and validate two-sentence stand notes from the Gold measurements. This
# classroom notebook uses deterministic offline examples, not a model service.
# The native Fabric Data Agent is created separately after Lab 05.
#
# ## Where a model earns its place here
#
# - Turning structured numbers into readable prose
# - Reconciling free-text field notes against a classified result and flagging
#   disagreements for a human
# - Drafting a change narrative between two dates
#
# ## Where it does not
#
# - Deciding the class. A threshold is auditable, reproducible and free.
# - Computing anything. Ask a model for a mean and you get a plausible mean.
# - Anything a forester will be asked to defend in a regulatory conversation
#   without a traceable calculation behind it.
#
# ## The failure mode that matters
#
# Not a wrong answer. A **confident** answer that nobody checks because it reads
# well. Everything in this notebook exists to make that failure visible.

# %%
print("Offline narrative exercise: no endpoint, API key or model download is required.")

# %% [markdown]
# ## Step 1 · Configuration
#
# The output table records `stubbed` for valid offline text and suppresses invalid
# text. A stub is a classroom example, not evidence of a live model response.

# %%
import json
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

NARRATIVE_SAMPLE_SIZE = 40   # keep the workshop run short and cheap
BATCH_SIZE = 10

# --- Medallion layer --------------------------------------------------------
# Reads and writes gold only, so no cross-layer shortcuts are needed here.
LAYER = "gold"
WORKSPACE = "jdi-training"
LAKEHOUSE = "lh_woodlands"

TABLE_CLASSIFICATION = "gold_stand_classification"
TABLE_CHANGE = "gold_stand_change"
TABLE_NARRATIVE = "gold_stand_narrative"

def report(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<44} {detail}")

print("Running mode: offline stub")

# %% [markdown]
# ## Step 2 · Assemble the input rows
#
# Join classification and change so the narrative has something to say about
# what happened, not only what the stand is.

# %%
classification = spark.table(TABLE_CLASSIFICATION).toPandas()
change = spark.table(TABLE_CHANGE).toPandas()

rows = classification.merge(
    change[["stand_id", "change_type", "severity", "requires_review", "delta_nbr"]],
    on="stand_id", how="left",
)
rows["change_type"] = rows["change_type"].fillna("none")

# Prioritise the stands a planner would actually open first.
rows = rows.sort_values(["requires_review", "area_ha"], ascending=[False, False]).head(NARRATIVE_SAMPLE_SIZE)
print(f"{len(rows)} stands selected for enrichment")
rows[["stand_id", "forest_class", "change_type", "area_ha"]].head()

# %% [markdown]
# ## Step 3 · Decide what the model is allowed to see
#
# Passing the whole row is how a model ends up quoting an internal identifier
# into a planner-facing sentence. Send only what the sentence may contain.

# %%
def build_stand_payload(row):
    """Select and round the fields the model is permitted to use."""
    def clean(value, digits=2):
        if value is None or (isinstance(value, float) and value != value):
            return None
        return round(float(value), digits)

    #@todo Return a dict with stand_id, licence_block, declared_species_group,
    #@todo spectral_class, class_confidence, area_ha, ndvi_p90, ndmi_mean, nbr_mean,
    #@todo valid_pixel_fraction, change_type, observation_count and period_end
    #@todo Round numeric values with clean(), area to 1 decimal and indices to 3
    #@hint Deliberately omit anything the planner should not see in a tooltip
    #@hint Keep nulls as None rather than filling them. The model must be told the value is missing.
    #@stub return {"stand_id": row.get("stand_id")}
#@solution
    return {
        "stand_id": row.get("stand_id"),
        "licence_block": row.get("licence_block"),
        "declared_species_group": row.get("species_group"),
        "spectral_class": row.get("forest_class"),
        "class_confidence": clean(row.get("class_confidence")),
        "area_ha": clean(row.get("area_ha"), 1),
        "ndvi_p90": clean(row.get("ndvi_p90"), 3),
        "ndmi_mean": clean(row.get("ndmi_mean"), 3),
        "nbr_mean": clean(row.get("nbr_mean"), 3),
        "valid_pixel_fraction": clean(row.get("valid_pixel_fraction"), 2),
        "change_type": row.get("change_type"),
        "observation_count": row.get("observation_count"),
        "period_end": str(row.get("period_end")) if row.get("period_end") is not None else None,
    }
#@end

sample_payload = build_stand_payload(rows.iloc[0].to_dict())
print(json.dumps(sample_payload, indent=2, default=str))

# %% [markdown]
# ## Step 4 · The prompt
#
# Five rules, each one closing a specific failure observed in practice.

# %%
SYSTEM_PROMPT = """You write two-sentence condition notes for forest stands, read by a Woodlands planner.

Rules you must follow:
- Use only the values supplied in the user message. Do not introduce any number that is not present there.
- Do not calculate, estimate, convert or round any value. Restate values exactly as given.
- If a value is null, say the measurement is unavailable. Never infer what it might have been.
- Do not recommend an operational action. Describe the condition; the planner decides.
- Return JSON matching the requested schema and nothing else.
"""

RESPONSE_KEYS = ("summary", "attention", "values_used")

print(SYSTEM_PROMPT)

# %% [markdown]
# ## Step 5 · Where AI is quietly wrong
#
# Three demonstrations. Read the output of each before moving on. They are the
# reason the rest of this notebook is built the way it is.

# %% [markdown]
# ### Demonstration 1 · It restates numbers you never gave it
#
# Ask for a summary including area, without supplying the area. A helpful model
# produces a helpful number.

# %%
demo_payload = {k: v for k, v in sample_payload.items() if k != "area_ha"}
print("Payload sent (note: no area_ha):")
print(json.dumps({k: v for k, v in list(demo_payload.items())[:5]}, indent=2))
print("\nPrompt: 'Summarise this stand and state its area in hectares.'")
print("\nWhat you get back is a sentence containing a hectare figure.")
print("It is fluent, it is specific, and it came from nowhere.")
print("Nothing in the response marks it as invented.")

# %% [markdown]
# ### Demonstration 2 · The same question, two different answers
#
# Ask it to classify a stand from index values with no threshold definition. Run
# it twice. The answers differ, and neither is wrong in a way you can point at.
#
# This is why classification lives in notebook 03 as a threshold dictionary a
# forester can argue with.

# %%
print("Prompt: 'Given NDVI 0.62 and NDMI 0.14, classify this stand.'\n")
print("  Run 1: 'mixedwood, given the moderate moisture signature'")
print("  Run 2: 'likely softwood-dominated mixedwood'")
print("  Run 3: 'mixedwood with hardwood component'\n")
print("Three answers, no thresholds, nothing to audit, and no way to explain to a")
print("regulator why a stand moved class between two runs of the same pipeline.")

# %% [markdown]
# ### Demonstration 3 · It has an opinion about missing data
#
# This is the one people remember, because the output looks exactly like a
# correct answer.

# %%
missing_payload = {**sample_payload, "ndmi_mean": None}
print("Payload sent, with ndmi_mean explicitly null:")
print(json.dumps({k: missing_payload[k] for k in ("stand_id", "spectral_class", "ndmi_mean", "ndvi_p90")}, indent=2))
print()
print("Without the null-handling rule in the system prompt, a typical response is:")
print('  "Canopy moisture is moderate for a stand of this type."')
print()
print("That sentence is not a hallucinated number, so a numeric guard does not")
print("catch it. It is a hallucinated *judgement* about data that does not exist.")
print("The only defence is the instruction, and the only proof it worked is")
print("reading the output. Both belong in your test set.")

# %% [markdown]
# ## Step 6 · The numeric guard
#
# Every number in the generated summary must already exist in the payload. This
# catches demonstration 1 mechanically.
#
# It does **not** catch demonstration 3. Say that out loud when someone claims
# validation has solved the problem.

# %%
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")

def canonical(value):
    """Normalise a number so 0.70, 0.7 and .7 compare equal."""
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)

def allowed_numbers(payload):
    """Every numeric token the model is permitted to reproduce."""
    #@todo Walk the payload values
    #@todo Add every int or float, canonicalised
    #@todo Add every number found inside a string value, canonicalised
    #@todo Return the set
    #@hint period_end is a string like "2026-08-31" and contains three legitimate numbers
    #@stub return set()
#@solution
    allowed = set()
    for value in payload.values():
        if isinstance(value, (int, float)) and value == value:
            allowed.add(canonical(value))
        elif isinstance(value, str):
            allowed.update(canonical(tok) for tok in NUMBER_PATTERN.findall(value))
    return allowed
#@end

def validate_response(text, payload):
    """Parse and check a model response against the row that produced it."""
    #@todo Parse the response as JSON, returning (None, "schema_invalid") on failure
    #@todo Check it is a dict containing every key in RESPONSE_KEYS
    #@todo Check attention is one of none, watch or review
    #@todo Check summary is a non-empty string
    #@todo Extract every number in the summary and compare against allowed_numbers
    #@todo Return (parsed, "numeric_mismatch") if any number was invented
    #@todo Otherwise return (parsed, "ok")
    #@hint Return the parsed object even on numeric_mismatch, so the failure can be inspected
    #@stub return None, "schema_invalid"
#@solution
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None, "schema_invalid"

    if not isinstance(parsed, dict) or not all(k in parsed for k in RESPONSE_KEYS):
        return None, "schema_invalid"
    if parsed.get("attention") not in {"none", "watch", "review"}:
        return None, "schema_invalid"
    if not isinstance(parsed.get("summary"), str) or not parsed["summary"].strip():
        return None, "schema_invalid"

    permitted = allowed_numbers(payload)
    quoted = {canonical(tok) for tok in NUMBER_PATTERN.findall(parsed["summary"])}
    if quoted - permitted:
        return parsed, "numeric_mismatch"

    return parsed, "ok"
#@end

# %% [markdown]
# ### Prove the guard works
#
# Two fabricated responses, one clean and one containing an invented number.

# %%
clean_response = json.dumps({
    "summary": f"Stand {sample_payload['stand_id']} is classified {sample_payload['spectral_class']} "
               f"across {sample_payload['area_ha']} hectares. Canopy moisture sits at {sample_payload['ndmi_mean']}.",
    "attention": "none",
    "values_used": [str(sample_payload["area_ha"]), str(sample_payload["ndmi_mean"])],
})

invented_response = json.dumps({
    "summary": f"Stand {sample_payload['stand_id']} covers 847.3 hectares and shows strong canopy vigour.",
    "attention": "none",
    "values_used": ["847.3"],
})

malformed_response = "Here is the summary you asked for: the stand looks healthy."

for label, text in [("clean", clean_response), ("invented number", invented_response), ("malformed", malformed_response)]:
    _, status = validate_response(text, sample_payload)
    print(f"  {label:<18} -> {status}")

report("clean response passes", validate_response(clean_response, sample_payload)[1] == "ok")
report("invented number is caught", validate_response(invented_response, sample_payload)[1] == "numeric_mismatch")
report("malformed response is caught", validate_response(malformed_response, sample_payload)[1] == "schema_invalid")

# %% [markdown]
# ## Step 7 · The offline stub
#
# Deterministic text keeps this exercise reproducible for either imagery route.
# Validate it against the same structured payload before writing the Gold table.

# %%
def offline_stub(payload):
    """Return a deterministic classroom narrative from measured inputs."""
    cls = payload.get("spectral_class") or "unclassified"
    ndmi = payload.get("ndmi_mean")
    change_type = payload.get("change_type") or "none"

    first = f"Stand {payload.get('stand_id')} is classified {cls} across {payload.get('area_ha')} hectares."
    if ndmi is None:
        second = "Canopy moisture is unavailable for this period."
    elif change_type in {"harvest", "disturbance"}:
        second = f"Canopy loss was detected with moisture at {ndmi}, consistent with {change_type}."
    else:
        second = f"Canopy moisture sits at {ndmi} with no significant change detected."

    attention = "review" if change_type in {"disturbance", "moisture_stress"} else "none"
    return {"summary": f"{first} {second}", "attention": attention, "values_used": []}

print(offline_stub(sample_payload)["summary"])
print()
print(offline_stub({**sample_payload, "ndmi_mean": None})["summary"])
print()
print("Note the second one. The stub says the measurement is unavailable rather")
print("than describing moisture it does not have. That is the bar the model has")
print("to clear, and it is a low bar that models miss regularly.")

# %% [markdown]
# ## Step 8 · Generate
#
# Serialize the offline response and run the schema/numeric checks from Step 5.
# Only validated text is retained. No external service is contacted.

# %%
def generate_narrative(payload):
    """Validate one offline response before labelling it as a stub."""
    #@todo Serialize offline_stub(payload) with json.dumps and validate_response
    #@todo Return the parsed response and "stubbed" only if validation returned "ok"
    #@hint Preserve the original validation status when the response is invalid.
    #@stub return None, "not_completed"
#@solution
    parsed, status = validate_response(json.dumps(offline_stub(payload)), payload)
    return parsed, "stubbed" if status == "ok" else status
#@end

# %%
generated_at = datetime.now(timezone.utc)
records = []

for start in range(0, len(rows), BATCH_SIZE):
    batch = rows.iloc[start : start + BATCH_SIZE]
    for _, row in batch.iterrows():
        payload = build_stand_payload(row.to_dict())

        #@todo Call generate_narrative(payload), retaining its parsed response and status
        #@todo Keep the summary only for a validated "stubbed" response, otherwise use None
        #@hint A rejected narrative remains visible through validation_status.
        #@stub parsed, status, narrative = None, "not_completed", None
#@solution
        parsed, status = generate_narrative(payload)
        narrative = parsed["summary"] if parsed and status == "stubbed" else None
#@end

        records.append({
            "stand_id": payload["stand_id"],
            "period_end": row.get("period_end"),
            "narrative": narrative,
            "attention": (parsed or {}).get("attention", "none"),
            "validation_status": status,
            "model_deployment": "offline-stub",
            "generated_at_utc": generated_at,
        })

    print(f"  batch {start // BATCH_SIZE + 1}: {len(records)} rows generated")

narratives = pd.DataFrame(records)
print(f"\n{len(narratives)} narratives")
print(narratives["validation_status"].value_counts())

# %% [markdown]
# ### Why batch and print
#
# Progress is printed per batch. The next step writes the complete result table;
# a printed batch count alone does not prove that anything was saved.

# %% [markdown]
# ## Step 9 · Read some
#
# Read five narratives properly. Not skim: read them against the row they came
# from. This is the only test that catches demonstration 3.

# %%
for _, record in narratives.head(5).iterrows():
    source = rows[rows.stand_id == record.stand_id].iloc[0]
    print(f"{record.stand_id}   class={source.forest_class}   ndmi={source.ndmi_mean:.3f}"
          f"   area={source.area_ha:.1f} ha   status={record.validation_status}")
    print(f"   {record.narrative}")
    print()

# %% [markdown]
# ## Step 10 · Write, with failures visible
#
# Rows that failed validation are written with the narrative suppressed rather
# than dropped. A missing row looks like a stand that was never processed. A row
# with a null narrative and a status of `numeric_mismatch` tells you exactly what
# happened.

# %%
#@todo Assert that every row whose validation_status is not ok or stubbed has a null narrative
#@hint This is the assertion that stops an unvalidated sentence reaching a planner
#@stub pass
#@solution
unvalidated = narratives[~narratives["validation_status"].isin(["ok", "stubbed"])]
assert unvalidated["narrative"].isna().all(), (
    "an unvalidated narrative would be published; suppress it before writing"
)
#@end

(
    spark.createDataFrame(narratives).write
    .format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(TABLE_NARRATIVE)
)
print(f"{TABLE_NARRATIVE}: {spark.table(TABLE_NARRATIVE).count()} rows")

# %% [markdown]
# ### Validation

# %%
stored = spark.table(TABLE_NARRATIVE).toPandas()
failed = int((~stored["validation_status"].isin(["ok", "stubbed"])).sum())

report("narratives written", len(stored) > 0, f"{len(stored)} rows")
report("validation status on every row", stored["validation_status"].notna().all())
report("model deployment recorded", stored["model_deployment"].notna().all(),
       stored["model_deployment"].iloc[0])
report("unvalidated narratives suppressed",
       bool(stored.loc[~stored.validation_status.isin(["ok", "stubbed"]), "narrative"].isna().all()))
report("failure rate within tolerance", failed / len(stored) <= 0.20,
       f"{failed}/{len(stored)} failed ({failed / len(stored):.0%})")

# %% [markdown]
# ## Step 11 · Break the guard on purpose
#
# Remove the numeric check and see what reaches the table. Then put it back.
#
# The point of this exercise is not to prove the guard works. It is to see how
# convincing the output is without it.

# %%
def validate_without_guard(text, payload):
    """The same validator with the numeric check removed. Do not ship this."""
    parsed = None
    try:
        candidate = json.loads(text)
        parsed = candidate if isinstance(candidate, dict) and "summary" in candidate else None
    except json.JSONDecodeError:
        parsed = None
    return (parsed, "ok") if parsed else (None, "schema_invalid")

_, guarded = validate_response(invented_response, sample_payload)
_, unguarded = validate_without_guard(invented_response, sample_payload)

print(f"Response: {json.loads(invented_response)['summary']}\n")
print(f"  with the numeric guard:    {guarded}")
print(f"  without the numeric guard: {unguarded}")
print()
print("Without the guard, an invented hectare figure is published to a planner")
print("as a validated fact. Nothing about the sentence signals a problem.")

# %% [markdown]
# ## Checkpoint
#
# You are done when `gold_stand_narrative` exists, every row carries a
# `validation_status`, and the result matches the selected mode. In offline mode,
# every row should be `stubbed`. In live mode, review every non-`ok` status to
# confirm the numeric guard is doing its job.
#
# ## What to take away
#
# | Question | Answer |
# |---|---|
# | Did AI decide any class? | No. Notebook 03 did, with thresholds. |
# | Did AI compute any number? | No. Every number was passed in and checked on the way out. |
# | What happens if Foundry is down? | The stub runs, the table shape is identical, the report still refreshes. |
# | What happens if the model changes? | `model_deployment` records which one wrote each sentence. |
# | What is still not caught? | Hallucinated judgements about missing data. Only reading the output catches those. |
#
# **Next:** `05_publish_and_validate` builds the star schema and the Direct Lake
# model.
