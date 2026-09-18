---
title: Woodlands in Microsoft Fabric
description: Complete six notebook exercises using Sentinel-2 imagery, then explore the results in a Fabric Map and Data Agent.
ms.date: 2026-09-18
---

## Start Here

**Follow the [step-by-step student guide](docs/16-manual-upload-labs.md).**
It covers setup, each notebook exercise, checkpoints, and the final Map and
Data Agent, with annotated screenshots.

Use Microsoft Fabric in your browser. You do not need local Python, Power BI
Desktop, Docker, or an AI API key. Allow a full workshop day.

## Before You Begin

* A Fabric workspace on an active capacity, with Contributor access or higher
* The published `env_forestops` Environment, prepared by your facilitator using
  [Environment setup](docs/12-spark-environment.md#manual-portal-setup)
* Your own learner or pair identifier for naming notebooks and a lakehouse
* About 1 GB of free local space for the manual imagery download

Screenshot workspace labels are generalized as `fabric-training-manual`.
Use the workspace your facilitator provides. Each learner or pair needs a
separate lakehouse.

## Complete The Exercises

1. Upload all six [student notebooks](notebooks/student) to your workspace folder.
2. Create your lakehouse, then attach it as the default lakehouse and select
   `env_forestops` in every notebook.
3. Complete Lab 00. Before Lab 01, follow
   [imagery download and upload](docs/17-manual-imagery-download.md).
   Manual upload is the default; automatic STAC search is also supported.
4. Work through Labs 01-05 in order. Complete the applicable `TODO` exercises,
   run cells from top to bottom, and stop at any exception or `[FAIL]`.
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
* [Imagery guide](docs/17-manual-imagery-download.md): download and upload the
  five original TIFF bands plus scene metadata, approximately 685 MB
* [Workshop deck](decks/woodlands-manual-workshop.pptx): follow-along slides
* [Workshop ZIP](handouts/woodlands-manual-download-20260918.zip): notebooks,
  solutions, handouts and deck in one download; extract it and open
  `handouts/START-HERE.md`

The imagery itself is downloaded separately. The repository's `scripts`, `src`
and `notebooks/_src` folders are for maintaining the exercises; learners do not
need to run them.

## Finish And Check

You are finished when all six notebooks pass their checks, your Gold tables and
GeoJSON exist, your Map is saved, and your Data Agent answers match the SQL
checks in the guide. Stop your Spark session when finished.

This is a teaching exercise using public Copernicus Sentinel data and synthetic
stands, not production forest inventory. Classification is heuristic, the
previous-year baseline is simulated, and narrative text is generated offline.
Report your actual coverage and missing results rather than copying example
counts.
