---
title: Post-workshop assignment
description: Two-week assignment to run the forest classification pipeline against your own operating area, with acceptance criteria, extension options and a review rubric
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: how-to
keywords:
  - assignment
  - pipeline
  - acceptance criteria
estimated_reading_time: 6
---

## Post-workshop assignment

Two weeks. Roughly six hours of work. The aim is a running pipeline over your
own operating area that someone other than you could pick up.

Office hours run twice in the two-week window. Bring the thing that is not
working rather than a status update.

## The deliverable

A Fabric workspace containing:

1. A scheduled pipeline that runs the five notebooks over your area of interest.
2. Gold Delta tables populated for at least two distinct time periods.
3. A Direct Lake semantic model and a single Power BI report page.
4. A one-page write-up covering what you would change before anyone relied on it.

## Acceptance criteria

Tick every line before you submit. These are the same checks the review uses.

### Pipeline

- [ ] The pipeline runs end to end without manual intervention.
- [ ] Area of interest, date window and cloud threshold are pipeline parameters,
      not values edited inside notebooks.
- [ ] A schedule exists, and it has fired successfully at least twice.
- [ ] A failure notification is configured and you have tested it by breaking
      something on purpose.
- [ ] The quality gate between silver and gold stops the run when the trusted
      observation fraction falls below the threshold.

### Data

- [ ] `bronze_scene_catalog` has one row per scene with unsigned asset hrefs.
- [ ] Bronze is not overwritten between runs. New runs append with a new
      `pipeline_run_id`.
- [ ] `silver_stand_observations` is at the stand and scene-date grain, with no
      duplicates on that key.
- [ ] Every geometry-bearing table carries an `srid` column and it is correct.
- [ ] Areas are computed in a projected CRS, and a spot check against a known
      stand is within a few percent.
- [ ] `gold_stand_classification` carries `class_method`, so any class can be
      traced to the logic that produced it.

### AI enrichment

- [ ] Narratives are generated from pre-computed values, and the prompt does not
      ask the model to calculate anything.
- [ ] Output is schema-constrained and validated against the source row.
- [ ] `validation_status` is populated, and at least one failure mode has been
      observed and explained rather than engineered away.
- [ ] `model_deployment` records the deployment name and version.
- [ ] The pipeline still completes when AI is disabled.

### Report

- [ ] Direct Lake is confirmed in use, with no silent DirectQuery fallback.
- [ ] The map shows stands coloured by class for a selected period.
- [ ] A period selector changes the map and the trend together.
- [ ] The stand tooltip shows the narrative, and suppressed narratives display a
      clear message rather than a blank.
- [ ] A planner who has not seen the workshop can answer "which stands were
      harvested since the last period" in under a minute.

## Extension options

Pick at most one. A finished baseline beats an unfinished extension.

| Extension                  | What it adds                                                                    | Effort |
|----------------------------|----------------------------------------------------------------------------------|--------|
| Trained classifier         | Replace the rule-based classes with a random forest trained on your inventory     | High   |
| Multi-zone area of interest| Handle an area crossing UTM 19N and 20N, mosaicking after reprojection             | Medium |
| Terrain correction         | Add the Copernicus DEM, derive slope and aspect, and correct illumination          | High   |
| Harvest alerting           | Push high-severity change rows to a Teams channel through a pipeline activity      | Low    |
| Incremental processing     | Only process scenes not already in `bronze_scene_catalog`                          | Medium |
| Field note reconciliation  | Join free-text notes to stands and flag disagreements with the classification      | Medium |

## The write-up

One page. Four headings, a few sentences each.

1. What the pipeline gets right, with one number you trust and why.
2. What it gets wrong, with one number you do not trust and why.
3. What breaks first at ten times the area, and what you would change.
4. What you would need from someone else before this becomes operational.

Section two carries the most weight in review. An honest account of a limitation
is worth more than a clean run over an easy area, and a submission that claims
no limitations gets sent back.

## Review rubric

| Level        | Description                                                                                          |
|--------------|-------------------------------------------------------------------------------------------------------|
| Not yet      | Pipeline runs manually, or gold numbers cannot be traced back to a scene                              |
| Working      | All acceptance criteria met, honest write-up, report answers the problem statement                    |
| Operational  | Working, plus one extension, plus a documented failure mode with a tested recovery                    |
| Owned        | Operational, plus someone other than the author has run it and changed something without asking       |

The last level is the only one that matters in the long run. An analytics product
with exactly one person who can run it is a risk with a dashboard attached.

## Submission

Share the workspace with the facilitator group, put the write-up in the workshop
Teams channel, and note which extension you chose. Reviews return within a week
with written comments and an offer of a 30-minute call.
