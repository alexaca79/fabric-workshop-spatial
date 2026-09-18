---
title: Automating Forest Classification on Microsoft Fabric
description: One-day workshop repository for JDI Woodlands covering a bronze, silver and gold forest classification pipeline built on Microsoft Fabric, Planetary Computer, GitHub Copilot, Microsoft Foundry and Power BI
author: Workshop Delivery Team
ms.date: 2026-09-18
ms.topic: overview
keywords:
  - microsoft fabric
  - onelake
  - medallion architecture
  - planetary computer
  - forest classification
  - power bi
estimated_reading_time: 8
---

## Automating forest classification on Microsoft Fabric

A one-day, two-session workshop that takes a working team from an empty Fabric
workspace to an automated forest classification pipeline: Sentinel-2 imagery
lands in bronze, reprojection and spectral analysis happen in silver, stand-level
classification and guarded narratives land in gold. The manual student path
finishes with a native Fabric Map and Fabric Data Agent. A Direct Lake semantic
model and Power BI report are separate optional extensions.

Every exercise runs against open data, so the repository works before anyone has
been granted access to production Woodlands inventory.

## Deploying this in a JDI tenant

For the learner-led, single-workspace path, start with
[the manual upload lab guide](docs/16-manual-upload-labs.md). It uses
`jdi-training-manual` in Contoso on `rayfintestenv` F64. Upload all six student
notebooks, create your own lakehouse, complete the TODO exercises, then
manually create a native Fabric Map and Fabric Data Agent. The guide includes
45 annotated portal screenshots, with numbered circles and arrows.

Open the [extracted Start Here handout](handouts/woodlands-manual-workshop-20260918/handouts/START-HERE.md),
download the [complete workshop ZIP](handouts/woodlands-manual-workshop-20260918.zip),
or open the [47-slide manual workshop deck](decks/out/woodlands-manual-workshop.pptx).
The learner bundle has only four top-level folders: **student**, **solutions**,
**handouts**, and **deck**. Repository authoring and deployment files stay separate.

Use [DEPLOY.md](DEPLOY.md) for the production-style three-workspace topology,
outbound access protection decisions, scripted deployment and deeper verification.

## Taking it further after the workshop

[docs/15-resources-and-learning-paths.md](docs/15-resources-and-learning-paths.md)
is the take-home plan: what participants keep, a sequenced 90-day reading path
split by role, and a reference shelf of official Microsoft Learn documentation
covering every Fabric component used here.

## Status: verified end to end

The manual rehearsal completed in `jdi-training-manual` on September 18, 2026:
all six labs, independent Gold SQL checks, a saved/reopened native Map and a
published Data Agent passed. The latest period is **2026-08-31**, with
**120 registered stands, 119 retained results and one missing result (99.17%)**.
All 40 narratives are offline stubs; change flags use a simulated baseline.
The 12 downloadable notebooks validate, preserve the student TODO exercises,
and have no cloud dependency bindings. All 72 focused local tests passed.
See [manual rehearsal evidence](docs/training-manual-evidence.json).

### Earlier Reference Rehearsal

The six core labs and the Environment preflight completed in `jdi-training`
on September 17, 2026. All 83 solution code cells matched the live definitions
at that verification. A persisted cloud probe passed 23 checks and reads; a
separate current-data validation passed 22 assertions covering grain, keys,
dates, ranges and geometry. See [the live evidence](docs/training-live-evidence.json).

The later local lab check corrected a synthetic-area validation false failure
in Lab 00; three focused regression tests passed then. Processing outputs were
unchanged. The cloud equivalence receipt predates that validation correction
and the new map export; it is not evidence for the new manual rehearsal.

That run produced 102 classified facts from 120 synthetic stands. Eighteen
stands were excluded by the quality gate, so whole-register coverage was
85 percent. All 40 narratives used the offline stub. Live Foundry, a Power BI
report, Direct Lake execution and scheduling were not verified outcomes.

Running it for real found four bugs that reading the code would not have:

| Bug | Symptom | Fix |
|---|---|---|
| `affine` 3.0.1 breaks every raster load | `TypeError: No '__dict__' attribute on 'Affine' instance` | Pinned `affine<3` |
| `zarr` absent from the Environment | Notebook 01 died on its last cell, after all real work succeeded | Added `zarr>=2.16` |
| Zarr does not round-trip the CRS | Notebook 02's CRS guard fired on a reloaded cube | `set_coords("spatial_ref")` on read, plus an explicit EPSG fallback |
| STAC renamed `proj:epsg` to `proj:code` | Scene catalogue silently recorded `epsg = 0` | Read both spellings, and validate |

The last one is the instructive one: nothing failed, nothing raised, and the
provenance was simply absent. See
[docs/14-debugging-notebook-failures.md](docs/14-debugging-notebook-failures.md).

## What you build

```text
Planetary Computer (STAC)          Woodlands stand register
        |                                    |
        v                                    v
+-------------------------------------------------------+
|  BRONZE   raw scenes, raw geometry, nothing reshaped   |
|           Files/bronze/  +  bronze_scene_catalog       |
+-------------------------------------------------------+
                          |
                          v
+-------------------------------------------------------+
|  SILVER   cloud-masked, reprojected to EPSG:2953,      |
|           spectral indices, zonal stats per stand      |
|           silver_stand_observations                    |
+-------------------------------------------------------+
                          |
                          v
+-------------------------------------------------------+
|  GOLD     classified stands, harvest change detection, |
|           AI narratives, model-ready aggregates        |
|           gold_stand_classification / gold_stand_facts |
+-------------------------------------------------------+
                          |
                          v
      GeoJSON export             ->  Native Fabric Map
      Gold Delta tables          ->  Fabric Data Agent
      Optional semantic model    ->  Power BI report
```

## Repository layout

| Path          | Contents                                                                      |
|---------------|-------------------------------------------------------------------------------|
| `docs/`       | Prerequisites, session agendas, facilitator guide, architecture, homework      |
| `decks/`      | Slide generators, icon renderer, shared theme, and the built `.pptx` files     |
| `notebooks/`  | `solutions/` fully worked notebooks, `student/` skeletons, and `sample-outputs/` |
| `src/`        | `forestops` helper package imported by the notebooks                           |
| `environments/` | The pinned library set published as a Fabric Environment                     |
| `pipelines/`  | Fabric data pipeline definition that orchestrates the notebooks end to end     |
| `powerbi/`    | Direct Lake semantic model and report build guide                              |
| `scripts/`    | Build and validation utilities, plus the live-capacity deploy and debug tools  |

## Quick start for participants

1. Complete [docs/00-prerequisites.md](docs/00-prerequisites.md), then follow
   [docs/16-manual-upload-labs.md](docs/16-manual-upload-labs.md) in order.
2. Upload all six student notebooks before manually creating your lakehouse.
3. Attach `env_forestops` and your own default lakehouse to every notebook.
4. Complete TODOs and run Labs 00-05 cell by cell. Use the separate solution
   keys to understand a blocked exercise, not as your submitted work.
5. Create the native Fabric Map from Lab 05's GeoJSON, then create and test
   the Fabric Data Agent against the four Gold tables.

## Quick start for facilitators

For the browser-only delivery, use the workspace preparation in
[docs/16-manual-upload-labs.md](docs/16-manual-upload-labs.md) and
[manual Environment setup](docs/12-spark-environment.md#manual-portal-setup).
Do not globally regenerate the manual-release notebooks: that would replace
release-specific corrections. The commands below belong to the separate
authoring and three-workspace deployment workflow.

```powershell
# From the repository root
python -m pip install -r requirements-build.txt

# Regenerate icon assets, doc images, both decks, and all notebooks
python scripts/build_all.py
```

Outputs land in `decks/out/`, `docs/images/` and
`notebooks/{solutions,student}/`.

Before delivery you also need the three workspaces, the lakehouses, the
shortcuts and the published Environment. Those are scripted:

```powershell
pwsh -File scripts/fabric_create_lakehouses.ps1
python scripts/fabric_environment.py build bronze   # repeat for silver and gold
pwsh -File scripts/fabric_create_shortcuts.ps1 -Tables
python scripts/fabric_run_pipeline.py all           # optional: prove it end to end
```

Read [docs/13-three-workspace-layout.md](docs/13-three-workspace-layout.md) for
the layout and [docs/12-spark-environment.md](docs/12-spark-environment.md) for
why the library set is pinned rather than installed with `%pip`.

See [docs/04-facilitator-guide.md](docs/04-facilitator-guide.md) for room setup,
timing, the fallback plan for blocked participants, and the demo failure points
worth rehearsing.

## Session map

| Session | Focus                            | Duration | Agenda                                            |
|---------|----------------------------------|----------|---------------------------------------------------|
| 1       | Environment and data foundations | 4 hours  | [docs/02-session-1-agenda.md](docs/02-session-1-agenda.md) |
| 2       | Build it end to end              | 4 hours  | [docs/03-session-2-agenda.md](docs/03-session-2-agenda.md) |

## Notebooks

| Order | Notebook                              | Session block                          |
|-------|---------------------------------------|----------------------------------------|
| 00    | `00_setup_lakehouse_and_config`       | Session 1, hands-on (2:50)             |
| 01    | `01_bronze_stac_ingest`               | Session 2, Step 1 (0:15)               |
| 02    | `02_silver_reproject_and_indices`     | Session 2, Step 2 (1:00)               |
| 03    | `03_gold_forest_classification`       | Session 2, Step 2 continued            |
| 04    | `04_gold_ai_enrichment_foundry`       | Session 2, Step 3 (2:05)               |
| 05    | `05_publish_and_validate`             | Session 2, Step 4 and Step 5 (2:50)    |

Each notebook exists twice. The `student/` copy has the scaffolding, the
markdown, the imports and the assertions, with the interesting lines replaced by
numbered TODO instructions. The `solutions/` copy is complete and runnable.

`notebooks/sample-outputs/` holds the schema, row count and first rows of every
table from the verified run, so a participant can tell the difference between an
output that is wrong and one that merely differs from their neighbour's.

## Consume the Gold layer

| Path | Serves | Where |
|------|--------|-------|
| SQL analytics endpoint | Analysts writing their own T-SQL | Built in, no work required |
| Native Fabric Map | Spatial exploration of stand polygons | Lab 05 GeoJSON and the manual guide |
| Fabric Data Agent | Natural-language questions over Gold data | Four Gold tables and the manual guide |
| Direct Lake semantic model and Power BI report | Anyone who wants to explore | Notebook 05 and `powerbi/` |

After the six notebooks, the manual workflow requires a native Map and a
tested, published Data Agent. Use
[the semantic model guide](powerbi/semantic-model-guide.md) for the optional
Power BI extension. No custom application, Node.js or Docker setup is required.

## Data and licensing

All imagery comes from the Microsoft Planetary Computer under the terms of the
source collections. Sentinel-2 L2A is free and open under the Copernicus data
licence. No JDI inventory data is stored in this repository. The stand register
used in the exercises is generated synthetically by notebook 00 and is designed
to be swapped for the real register by changing one configuration flag.

## Support during the workshop

Post blockers in the workshop Teams channel rather than working around them
silently. A blocked participant with a working solution notebook is still
learning; a blocked participant in silence is not.
