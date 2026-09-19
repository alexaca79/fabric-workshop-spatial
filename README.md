---
title: Woodlands in Microsoft Fabric
description: Complete six notebook exercises using Sentinel-2 imagery, then explore the results in a Fabric Map and Data Agent.
ms.date: 2026-09-19
---

## Start Here

Start with the [step-by-step student guide](docs/16-manual-upload-labs.md).
Upload the six student notebooks, create your own lakehouse, attach the shared
Environment, and complete the exercises before building the native Map and
Data Agent. The guide includes the required checkpoints and annotated screenshots.

Use Microsoft Fabric in your browser. You do not need local Python, Power BI
Desktop, Docker, or an AI API key. Allow a full workshop day.

## Before You Begin

* A Fabric workspace on an active capacity, with Contributor access or higher
* The published `env_forestops` Environment, prepared by your facilitator using
  [Environment setup](docs/12-spark-environment.md#manual-portal-setup)
* Your own learner or pair identifier for naming notebooks and a lakehouse
* Approved outbound access from Fabric to Planetary Computer and its imagery storage

The default route downloads imagery directly in Fabric. Only the optional manual
fallback needs about 1 GB of free space on your computer.

Screenshot workspace labels are generalized as `fabric-training-manual`.
Use the workspace your facilitator provides. Each learner or pair needs a
separate lakehouse.

## Complete The Exercises

1. Upload all six [student notebooks](notebooks/student) to your workspace folder.
2. Create your lakehouse, then attach it as the default lakehouse and select
   `env_forestops` in every notebook.
3. Complete Lab 00, then follow
  [Planetary Computer downloads in Fabric](docs/17-manual-imagery-download.md).
  Keep `INPUT_MODE = "stac"` in Lab 01. Use manual download/upload only as the fallback.
4. Work through Labs 01-05 in order. Read each section, complete its applicable
  `TODO`, select **Run cell**, and inspect the next validation output before
  continuing. Stop at any exception or `[FAIL]`; do not use **Run all** on an
  unfinished student notebook.
5. Use the student guide to create and test your native Fabric Map and Data Agent.

| Lab | Student notebook | Result |
|---|---|---|
| 00 | [Setup and stand register](notebooks/student/00_setup_lakehouse_and_config_STUDENT.ipynb) | Synthetic stand polygons and a Bronze table |
| 01 | [Import imagery](notebooks/student/01_bronze_stac_ingest_STUDENT.ipynb) | Sentinel-2 bands, source metadata and saved imagery |
| 02 | [Mask, reproject and calculate indices](notebooks/student/02_silver_reproject_and_indices_STUDENT.ipynb) | Silver observations and quality checks |
| 03 | [Classify stands and compare periods](notebooks/student/03_gold_forest_classification_STUDENT.ipynb) | Gold classifications and demonstration change flags |
| 04 | [Validate offline narratives](notebooks/student/04_gold_ai_enrichment_foundry_STUDENT.ipynb) | Checked stand summaries, explicitly labelled as stubs |
| 05 | [Publish and validate outputs](notebooks/student/05_publish_and_validate_STUDENT.ipynb) | Gold tables and a GeoJSON Map layer |

The [solution notebooks](notebooks/solutions) are answer keys. Use them to
understand a blocked exercise, then return to your student copy. Do not upload
the Python authoring sources from `notebooks/_src`.

## Workshop Files

* [Student guide](docs/16-manual-upload-labs.md): the complete walkthrough
* [Imagery guide](docs/17-manual-imagery-download.md): download directly in Fabric
  first; use the five-band browser download/upload fallback when needed
* [Workshop deck](decks/woodlands-manual-workshop.pptx): follow-along slides
* [Workshop ZIP](handouts/woodlands-fabric-first-20260919.zip): notebooks,
  solutions, handouts and deck in one download; extract it and open
  `handouts/START-HERE.md`

The ZIP does not contain imagery. Lab 01 downloads the analysis window from
Planetary Computer directly into your Fabric workflow. The repository's `scripts`,
`src` and `notebooks/_src` folders are for maintaining the exercises; learners do
not need to run them.

## Finish And Check

You are finished when all six notebooks pass their checks, your Gold tables and
GeoJSON agree with the SQL coverage query, your Map saves and reopens, and your
published Data Agent answers match the guide's SQL checks. Include a Map tooltip,
the missing-result filter, and the published agent's coverage answer in your
hand-in. Stop your Spark session; do not pause the shared capacity.

This is a teaching exercise using public Copernicus Sentinel data and synthetic
stands, not production forest inventory. Classification is heuristic, the
previous-year baseline is simulated, and narrative text is generated offline.
Report your actual coverage and missing results rather than copying example
counts.

## Verification

Rehearsed in the Fabric browser with Playwright on **2026-09-19**: all six student
copies were completed with the supplied solution code, one cell at a time.
All **83 code cells and 78 validation checks passed**. Saved code, Environment and
lakehouse bindings were checked independently. SQL, the saved/reopened native
Map, and the published Data Agent agreed on the reporting period and coverage.

The manual fallback's six browser downloads, retry flow and desktop/mobile
download page were also checked. Its full six-lab processing route was not rerun
in this rehearsal. Maintainer evidence is in
[scripts/verification/browser-20260919](scripts/verification/browser-20260919).
