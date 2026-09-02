---
title: Automating Forest Classification on Microsoft Fabric
description: One-day workshop repository for JDI Woodlands covering a bronze, silver and gold forest classification pipeline built on Microsoft Fabric, Planetary Computer, GitHub Copilot, Microsoft Foundry and Power BI
author: Workshop Delivery Team
ms.date: 2026-09-02
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
classification and AI enrichment land in gold, and a Direct Lake semantic model
drives a Power BI map.

Every exercise runs against open data, so the repository works before anyone has
been granted access to production Woodlands inventory.

## Status: verified end to end

The whole pipeline has been executed against a live Fabric F64 capacity, not
just authored. All six notebooks run to completion across three workspaces, the
OneLake shortcuts resolve, and the output data passes 27 correctness checks
covering grain, index ranges, referential integrity and map geometry.

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
        Direct Lake semantic model  ->  Power BI map
        Fabric App (Rayfin SDK)     ->  Chief Forester dashboard
```

## Repository layout

| Path          | Contents                                                                      |
|---------------|-------------------------------------------------------------------------------|
| `docs/`       | Prerequisites, session agendas, facilitator guide, architecture, homework      |
| `decks/`      | Slide generators, icon renderer, shared theme, and the built `.pptx` files     |
| `notebooks/`  | `solutions/` fully worked notebooks, `student/` skeletons, and `sample-outputs/` |
| `src/`        | `forestops` helper package imported by the notebooks                           |
| `apps/`       | `chief-forester` Fabric App on the Rayfin SDK, the alternative publishing path |
| `environments/` | The pinned library set published as a Fabric Environment                     |
| `pipelines/`  | Fabric data pipeline definition that orchestrates the notebooks end to end     |
| `powerbi/`    | Direct Lake semantic model and report build guide                              |
| `scripts/`    | Build and validation utilities, plus the live-capacity deploy and debug tools  |

## Quick start for participants

1. Read [docs/00-prerequisites.md](docs/00-prerequisites.md) and complete the
   access checks before Session 1. This takes about 30 minutes and is the single
   biggest cause of a slow start.
2. Run the pre-flight notebook cell in
   [notebooks/student/00_setup_lakehouse_and_config_STUDENT.ipynb](notebooks/student/00_setup_lakehouse_and_config_STUDENT.ipynb).
   It prints a pass or fail line for every dependency.
3. Work the `student/` notebooks during the sessions. The matching
   `solutions/` notebook is the answer key, not the starting point.
4. If you fall behind, open the solution for the block you missed, run it, and
   rejoin. Nobody should be stuck waiting on a previous step.

## Quick start for facilitators

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
| 06    | `06_publish_fabric_app_snapshot`      | Session 2, Step 4 alternative, optional |

Each notebook exists twice. The `student/` copy has the scaffolding, the
markdown, the imports and the assertions, with the interesting lines replaced by
numbered TODO instructions. The `solutions/` copy is complete and runnable.

`notebooks/sample-outputs/` holds the schema, row count and first rows of every
table from the verified run, so a participant can tell the difference between an
output that is wrong and one that merely differs from their neighbour's.

## Three ways to publish the same gold layer

| Path | Serves | Where |
|------|--------|-------|
| SQL analytics endpoint | Analysts writing their own T-SQL | Built in, no work required |
| Direct Lake semantic model and Power BI report | Anyone who wants to explore | Notebook 05 and `powerbi/` |
| Fabric App on the Rayfin SDK | One role with fixed questions | Notebook 06 and `apps/chief-forester/` |

The Fabric App is the Chief Forester dashboard: five cards, a class breakdown,
a review queue and a stand detail panel. Choose between the three using
[docs/11-fabric-app-option.md](docs/11-fabric-app-option.md). A gold layer that
can only feed one of the three is not really a gold layer.

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
