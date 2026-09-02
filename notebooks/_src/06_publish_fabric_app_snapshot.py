# Notebook 06: Publish the gold snapshot into the Chief Forester Fabric App
# Session 2, Step 4 alternative. Budget 25 minutes.

# %% [markdown]
# # 06 · Publish to the Chief Forester Fabric App
#
# **Session 2, Step 4, alternative publishing path.** Instead of a Power BI
# report, push the gold layer into a Fabric App built on the Rayfin SDK: a
# single-page dashboard for one named person.
#
# ## Why a second publishing option exists
#
# Power BI is the right answer when people want to slice, pivot and export.
# It is the wrong answer when the audience is one role, the questions are
# fixed, and what you actually want is a page that says "these seven stands,
# in this order".
#
# | | Power BI report | Fabric App |
# |---|---|---|
# | Audience | Anyone who wants to explore | One role with fixed questions |
# | Interaction | Slice, filter, drill, export | Read, then act |
# | Build cost | Low, clicks in the portal | Higher, it is a codebase |
# | Change cost | Anyone can break it | Reviewed, versioned, deployed |
# | Data access | Direct Lake over gold | Snapshot published by this notebook |
#
# Full decision guide in `docs/11-fabric-app-option.md`.
#
# ## What this notebook does
#
# ```
# gold_stand_facts + gold_dim_stand + gold_pipeline_run_summary
#         |
#         |  shape into three flat payloads
#         v
# Files/app-snapshot/<run_id>/*.json        always written
#         |
#         |  optional: POST create mutations to /api/graphql
#         v
# Fabric App: StandSnapshot, PeriodSummary, ClassBreakdown
# ```
#
# The JSON write always happens. The push happens only when the app endpoint is
# configured, so the notebook is runnable before anyone has the Fabric Apps
# workload switched on.

# %% [markdown]
# ## Step 1 · Configuration
#
# `APP_BASE_URL` is printed by `npx rayfin up` when the app deploys. Locally it
# is `http://localhost:5168`.

# %%
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import pandas as pd
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

AOI_NAME = "central-nb-block-a"

# Where the app lives. Empty string means "shape the payload but do not push".
APP_BASE_URL = os.environ.get("FABRIC_APP_URL", "").rstrip("/")
APP_TOKEN = os.environ.get("FABRIC_APP_TOKEN", "")
PUBLISHABLE_KEY = os.environ.get("FABRIC_APP_PUBLISHABLE_KEY", "pk-woodlands-chief-forester")

PUSH_ENABLED = bool(APP_BASE_URL)
BATCH_SIZE = 25

SNAPSHOT_ROOT = f"/lakehouse/default/Files/app-snapshot/{AOI_NAME}"

# --- Medallion layer --------------------------------------------------------
# Reads gold only. Attach lh_gold as the default lakehouse.
LAYER = "gold"
WORKSPACE = "jdi-mock-training-gold"
LAKEHOUSE = "lh_gold"

TABLE_FACTS = "gold_stand_facts"
TABLE_DIM_STAND = "gold_dim_stand"
TABLE_DIM_CLASS = "gold_dim_forest_class"
TABLE_RUN_SUMMARY = "gold_pipeline_run_summary"


def report(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<44} {detail}")


print(f"App endpoint configured: {PUSH_ENABLED}")
print(f"Mode: {'shape and push' if PUSH_ENABLED else 'shape only, JSON written to Files'}")

# %% [markdown]
# ## Step 2 · Read gold
#
# Nothing is computed here beyond reshaping. If a number is missing, the answer
# is to fix the notebook that should have produced it, not to derive it in the
# publishing step.

# %%
facts = spark.table(TABLE_FACTS).toPandas()
dim_stand = spark.table(TABLE_DIM_STAND).toPandas()
dim_class = spark.table(TABLE_DIM_CLASS).toPandas()

runs = spark.table(TABLE_RUN_SUMMARY).toPandas() if spark.catalog.tableExists(TABLE_RUN_SUMMARY) else pd.DataFrame()

print(f"{len(facts)} fact rows, {len(dim_stand)} stands, {len(dim_class)} classes")
report("gold facts present", len(facts) > 0)
report("stand dimension present", len(dim_stand) > 0)

PIPELINE_RUN_ID = os.environ.get("PIPELINE_RUN_ID") or f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
print(f"pipeline_run_id = {PIPELINE_RUN_ID}")

# %% [markdown]
# ## Step 3 · Shape the stand snapshot
#
# One row per stand, joined to its centroid. The app needs latitude and
# longitude as plain numbers, because it draws a map link rather than holding
# geometry. Keeping WKB out of the app is deliberate: binary columns buy you
# nothing in a dashboard and cost you a schema you have to maintain.

# %%
def build_stand_snapshot(facts_df, stand_df, run_id):
    """Flatten gold facts into the app's StandSnapshot shape."""
    #@todo Merge facts with the stand dimension on stand_id to pick up lat, lon and licence_block
    #@todo Keep a left join so a fact row with a missing dimension row stays visible
    #@hint Use suffixes so licence_block from the dimension does not silently overwrite the fact column
    #@stub merged = facts_df
    #@solution
    merged = facts_df.merge(
        stand_df[["stand_id", "licence_block", "lat", "lon"]],
        on="stand_id",
        how="left",
        suffixes=("", "_dim"),
    )
    #@end

    #@todo Build the output frame with the exact field names the entity declares
    #@todo Coerce nulls: forest_class to "unclassified", change_type to "none", severity to "low"
    #@todo Round areas to 2 decimals and confidence to 3
    #@hint The entity uses camelCase. A mismatch here fails at the API, not here.
    #@stub snapshot = pd.DataFrame()
    #@solution
    snapshot = pd.DataFrame({
        "standId": merged["stand_id"].astype(str),
        "licenceBlock": merged["licence_block"].fillna("unknown").astype(str),
        "periodEnd": pd.to_datetime(merged["period_end"]),
        "forestClass": merged["forest_class"].fillna("unclassified").astype(str),
        "classConfidence": merged["class_confidence"].fillna(0.0).round(3),
        "areaHa": merged["area_ha"].fillna(0.0).round(2),
        "changeType": merged["change_type"].fillna("none").astype(str),
        "severity": merged.get("severity", pd.Series("low", index=merged.index)).fillna("low").astype(str),
        "requiresReview": merged["requires_review"].fillna(False).astype(bool),
        "isTrusted": merged["is_trusted"].fillna(False).astype(bool),
        "lat": merged["lat"].astype(float).round(6),
        "lon": merged["lon"].astype(float).round(6),
        "narrative": merged["narrative"].where(merged["narrative"].notna(), None),
        "narrativeStatus": merged["validation_status"].fillna("absent").astype(str),
        "pipelineRunId": run_id,
    })
    #@end

    return snapshot


stand_snapshot = build_stand_snapshot(facts, dim_stand, PIPELINE_RUN_ID)
print(f"{len(stand_snapshot)} stand rows shaped")
stand_snapshot.head(3)

# %% [markdown]
# ### Validation
#
# The entity declares enumerated sets. A value outside them is rejected by the
# API with a message that is much harder to read than this check.

# %%
ALLOWED_CLASSES = {
    "softwood", "hardwood", "mixedwood", "regenerating",
    "recently_harvested", "non_forest", "unclassified",
}
ALLOWED_CHANGES = {"none", "harvest", "disturbance", "moisture_stress", "regrowth"}
ALLOWED_SEVERITY = {"low", "moderate", "high"}

report("stand rows shaped", len(stand_snapshot) > 0, f"{len(stand_snapshot)} rows")
report("forestClass within the set",
       set(stand_snapshot["forestClass"]).issubset(ALLOWED_CLASSES),
       f"{sorted(set(stand_snapshot['forestClass']) - ALLOWED_CLASSES) or 'all valid'}")
report("changeType within the set",
       set(stand_snapshot["changeType"]).issubset(ALLOWED_CHANGES))
report("severity within the set",
       set(stand_snapshot["severity"]).issubset(ALLOWED_SEVERITY))
report("coordinates look like degrees",
       bool(stand_snapshot["lat"].between(-90, 90).all() and stand_snapshot["lon"].between(-180, 180).all()),
       f"lat {stand_snapshot['lat'].min():.2f} to {stand_snapshot['lat'].max():.2f}")
report("narratives suppressed where unvalidated",
       bool(stand_snapshot.loc[~stand_snapshot.narrativeStatus.isin(["ok", "stubbed"]), "narrative"].isna().all()))

# %% [markdown]
# ## Step 4 · Shape the class breakdown
#
# The app could total these itself from 120 rows. It does not, and that is the
# point: aggregation belongs in gold, computed once, reconcilable against the
# Power BI model. A dashboard that does its own arithmetic is a second source
# of truth waiting to disagree with the first.

# %%
def build_class_breakdown(snapshot_df, class_df, run_id):
    """Aggregate area by forest class, carrying display order and colour."""
    #@todo Group the snapshot by forestClass, summing areaHa and counting stands
    #@todo Merge in display_order and colour_hex from the class dimension
    #@todo Add areaShare as each class's fraction of total area
    #@hint Use a left join from the dimension so classes with zero area still appear
    #@stub breakdown = pd.DataFrame()
    #@solution
    grouped = snapshot_df.groupby("forestClass", as_index=False).agg(
        standCount=("standId", "nunique"),
        areaHa=("areaHa", "sum"),
    )

    breakdown = class_df.rename(columns={"forest_class": "forestClass"}).merge(
        grouped, on="forestClass", how="left"
    )
    breakdown["standCount"] = breakdown["standCount"].fillna(0).astype(int)
    breakdown["areaHa"] = breakdown["areaHa"].fillna(0.0).round(2)

    total = max(float(breakdown["areaHa"].sum()), 1.0)
    breakdown["areaShare"] = (breakdown["areaHa"] / total).round(4)
    breakdown["periodEnd"] = snapshot_df["periodEnd"].max()
    breakdown["pipelineRunId"] = run_id
    breakdown = breakdown.rename(columns={"display_order": "displayOrder", "colour_hex": "colourHex"})
    #@end

    return breakdown[[
        "periodEnd", "forestClass", "standCount", "areaHa",
        "areaShare", "displayOrder", "colourHex", "pipelineRunId",
    ]]


class_breakdown = build_class_breakdown(stand_snapshot, dim_class, PIPELINE_RUN_ID)
print(class_breakdown[["forestClass", "standCount", "areaHa", "areaShare"]].to_string(index=False))

share_total = float(class_breakdown["areaShare"].sum())
report("class rows shaped", len(class_breakdown) > 0, f"{len(class_breakdown)} classes")
report("shares sum to one", abs(share_total - 1.0) < 0.01, f"{share_total:.3f}")

# %% [markdown]
# ## Step 5 · Shape the period summary
#
# One row. It drives the header cards, and it carries the two facts a Chief
# Forester needs before trusting anything else on the page: how fresh this is,
# and how much of the area could actually be seen.

# %%
def build_period_summary(snapshot_df, facts_df, run_id):
    """One row describing the run behind everything else on the page."""
    trusted = snapshot_df[snapshot_df["isTrusted"]]

    #@todo Build a one-row DataFrame with the PeriodSummary fields
    #@todo trustedCoverage is the fraction of stands with usable imagery
    #@todo areaHarvestedHa sums areaHa where changeType is harvest
    #@todo areaStressedHa sums areaHa where changeType is moisture_stress
    #@hint Guard the division: a period with zero stands must not raise here
    #@stub summary = pd.DataFrame()
    #@solution
    stands_total = len(snapshot_df)
    summary = pd.DataFrame([{
        "aoiName": AOI_NAME,
        "periodStart": pd.to_datetime(facts_df["period_start"]).min(),
        "periodEnd": pd.to_datetime(facts_df["period_end"]).max(),
        "standsTotal": int(stands_total),
        "standsClassified": int(len(trusted)),
        "trustedCoverage": round(len(trusted) / stands_total, 4) if stands_total else 0.0,
        "areaTotalHa": round(float(snapshot_df["areaHa"].sum()), 2),
        "areaHarvestedHa": round(
            float(snapshot_df.loc[snapshot_df.changeType == "harvest", "areaHa"].sum()), 2
        ),
        "areaStressedHa": round(
            float(snapshot_df.loc[snapshot_df.changeType == "moisture_stress", "areaHa"].sum()), 2
        ),
        "standsNeedingReview": int(snapshot_df["requiresReview"].sum()),
        "narrativesGenerated": int(snapshot_df["narrative"].notna().sum()),
        "classMethod": str(facts_df["class_method"].dropna().iloc[0])
        if facts_df["class_method"].notna().any() else "unknown",
        "sceneCount": int(facts_df["observation_count"].max()) if "observation_count" in facts_df else 0,
        "publishedAt": datetime.now(timezone.utc),
        "pipelineRunId": run_id,
    }])
    #@end

    return summary


period_summary = build_period_summary(stand_snapshot, facts, PIPELINE_RUN_ID)
print(period_summary.T.to_string(header=False))

coverage = float(period_summary["trustedCoverage"].iloc[0])
report("summary shaped", len(period_summary) == 1)
report("coverage is a fraction", 0.0 <= coverage <= 1.0, f"{coverage:.0%}")
if coverage < 0.7:
    print("      Coverage below 70 percent. The app shows this in amber on the front")
    print("      page rather than hiding it, which is the correct behaviour.")

# %% [markdown]
# ## Step 6 · Write the snapshot to Files
#
# This always happens, whether or not the app exists. It gives you a durable,
# inspectable artefact, and it means the push step can be re-run without
# re-reading gold.

# %%
import os as _os

snapshot_dir = f"{SNAPSHOT_ROOT}/{PIPELINE_RUN_ID}"
_os.makedirs(snapshot_dir, exist_ok=True)

payloads = {
    "PeriodSummary": period_summary,
    "ClassBreakdown": class_breakdown,
    "StandSnapshot": stand_snapshot,
}

written = {}
for entity, frame in payloads.items():
    path = f"{snapshot_dir}/{entity}.json"
    frame.to_json(path, orient="records", date_format="iso", indent=2)
    written[entity] = path
    print(f"  {entity:<16} {len(frame):>5} rows  ->  {_os.path.basename(path)}")

report("snapshot files written", all(_os.path.getsize(p) > 0 for p in written.values()))

# %% [markdown]
# ## Step 7 · Discover the mutation names
#
# Rayfin generates the GraphQL schema from the entity decorators, so the exact
# mutation names come from the deployed app rather than from an assumption in
# this notebook. Introspection asks the app what it actually offers.
#
# This is worth doing rather than hard-coding. A generated API that changes
# between preview releases will break a guess and survive a query.

# %%
def graphql(query, variables=None):
    """POST a GraphQL document to the app and return the data block."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-publishable-key": PUBLISHABLE_KEY,
    }
    if APP_TOKEN:
        headers["Authorization"] = f"Bearer {APP_TOKEN}"

    request = urllib.request.Request(f"{APP_BASE_URL}/api/graphql", data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.load(response)

    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "GraphQL error"))
    return payload.get("data", {})


INTROSPECT = """
query {
  __schema {
    mutationType {
      fields { name args { name type { kind name ofType { kind name } } } }
    }
  }
}
"""


def discover_create_mutations(entities):
    """Map each entity to the generated create mutation, by asking the app."""
    fields = graphql(INTROSPECT)["__schema"]["mutationType"]["fields"]
    names = [f["name"] for f in fields]
    mapping = {}
    for entity in entities:
        target = f"create{entity}".lower()
        match = next((n for n in names if n.lower() == target), None)
        if match is None:
            match = next((n for n in names if entity.lower() in n.lower() and "create" in n.lower()), None)
        mapping[entity] = match
    return mapping, names


mutations = {}
if PUSH_ENABLED:
    try:
        mutations, all_names = discover_create_mutations(payloads)
        for entity, name in mutations.items():
            print(f"  {entity:<16} -> {name or 'NOT FOUND'}")
        report("create mutations discovered", all(mutations.values()),
               f"{len(all_names)} mutations exposed by the app")
    except Exception as exc:
        print(f"  Introspection failed: {type(exc).__name__}: {exc}")
        print("  The snapshot files are already written. Fix the endpoint and re-run from here.")
        PUSH_ENABLED = False
else:
    print("  Skipped. Set FABRIC_APP_URL to enable the push.")

# %% [markdown]
# ## Step 8 · Push the snapshot
#
# Written in batches, with the result printed per batch. A 400-row load that
# fails on row 380 having written nothing is an afternoon nobody gets back.

# %%
def _serialise(value):
    """JSON-safe conversion. Timestamps become ISO strings, NaN becomes null."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def push_entity(entity, frame, mutation_name):
    """Create every row of one entity, in batches."""
    records = [{k: _serialise(v) for k, v in row.items()} for row in frame.to_dict("records")]
    created = 0

    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start : start + BATCH_SIZE]

        #@todo Build one GraphQL document per batch using aliased mutations
        #@todo Alias each row as m0, m1, ... so a batch is a single request
        #@todo Pass the rows as variables rather than inlining them into the query string
        #@hint One request per row hits the rate limiter and then hangs on backoff.
        #@hint Batched aliases keep it to one HTTP call per batch.
        #@stub raise NotImplementedError("build the batched mutation")
        #@solution
        aliases = []
        variables = {}
        var_defs = []
        for index, record in enumerate(batch):
            aliases.append(f'm{index}: {mutation_name}(input: $i{index}) {{ id }}')
            variables[f"i{index}"] = record
            var_defs.append(f"$i{index}: {entity}CreateInput!")

        document = f"mutation Push({', '.join(var_defs)}) {{ {' '.join(aliases)} }}"
        graphql(document, variables)
        #@end

        created += len(batch)
        print(f"    {entity}: {created}/{len(records)}")

    return created


if PUSH_ENABLED and all(mutations.values()):
    totals = {}
    # Summary and breakdown first: the app reads the newest PeriodSummary and
    # then filters everything else by its run id, so writing stands first would
    # leave a window where the page renders empty.
    for entity in ("PeriodSummary", "ClassBreakdown", "StandSnapshot"):
        totals[entity] = push_entity(entity, payloads[entity], mutations[entity])

    print()
    for entity, count in totals.items():
        report(f"{entity} published", count == len(payloads[entity]), f"{count} rows")
else:
    print("Push skipped. The snapshot files under Files/app-snapshot are the artefact.")

# %% [markdown]
# ## Step 9 · Confirm what the app will show
#
# Read it back through the same API the dashboard uses. A publish that cannot
# be read back by the consumer is not a publish.

# %%
VERIFY = """
query {
  periodSummaries: PeriodSummary(orderBy: { periodEnd: DESC }, first: 1) {
    aoiName periodEnd standsTotal trustedCoverage areaTotalHa standsNeedingReview pipelineRunId
  }
}
"""

if PUSH_ENABLED:
    try:
        data = graphql(VERIFY)
        latest = (data.get("periodSummaries") or [None])[0]
        if latest:
            print(json.dumps(latest, indent=2))
            report("app returns the new period", latest.get("pipelineRunId") == PIPELINE_RUN_ID)
        else:
            report("app returns the new period", False, "no summary rows returned")
    except Exception as exc:
        # Query field names are generated, so a mismatch here is a naming
        # difference rather than a failed publish. Check the app's GraphQL
        # schema in the portal and adjust the document above.
        print(f"  Verification query failed: {type(exc).__name__}: {exc}")
        print("  Open the app's /api/graphql schema and confirm the query field names.")
else:
    print("Nothing to verify. Push was not enabled.")

# %% [markdown]
# ## Step 10 · Wire it into the pipeline
#
# Add this notebook as the last activity, after `05_publish_and_validate`, and
# make it conditional so a run without the app still succeeds.
#
# ```
# [ 05 publish ] ──▶ < publish_target contains "app" > ──▶ [ 06 publish to app ]
#         │                        │
#         │                       false
#         └──────────────────────▶ [ Refresh semantic model ]
# ```
#
# | Parameter | Example | Purpose |
# |---|---|---|
# | `publish_target` | `powerbi,app` | Which publishing paths run |
# | `FABRIC_APP_URL` | `https://woodlands-chief-forester-app.rayfin.windows.net` | App backend |
# | `PIPELINE_RUN_ID` | passed from the pipeline | Correlates every table in one run |
#
# Pass `PIPELINE_RUN_ID` in from the pipeline rather than generating it here.
# The app filters on it, so a run id that disagrees with the rest of the run
# produces a dashboard showing a period that no other table knows about.

# %% [markdown]
# ## Checkpoint
#
# You are done when:
#
# - `Files/app-snapshot/<run_id>/` holds three JSON files
# - Every validation above prints `PASS`
# - If the app is deployed, the verification query returns your run id
#
# ## What this notebook deliberately does not do
#
# It does not compute anything the pipeline has not already computed. Every
# figure is a reshape of a gold column. If a number is wrong on the dashboard,
# it is wrong in gold, and this notebook is not where you fix it.
#
# **Next:** open the app, or go back to `05_publish_and_validate` for the
# Power BI path. Most teams end up running both.
