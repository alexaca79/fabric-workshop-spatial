---
title: Sample outputs
description: Known-good samples of every table the pipeline produces, captured from a verified end-to-end run against a live Fabric capacity
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: reference
keywords:
  - sample data
  - validation
  - schema
estimated_reading_time: 4
---

## Sample outputs

`sample_outputs.json` holds the schema, the row count and the first three rows
of every table the pipeline writes. It was captured from a real end-to-end run
against a live F64 capacity on 2026-09-02, not written by hand, so the column
types and value ranges are the ones you should actually expect.

Use it to answer the question that comes up at every checkpoint: *is my output
wrong, or does it just look different from my neighbour's?*

## What is in the file

| Table | Rows | Columns | Layer |
|---|---|---|---|
| `bronze_stand_register` | 120 | 11 | bronze |
| `silver_stand_observations` | 120 | 24 | silver |
| `gold_stand_classification` | 102 | 18 | gold |
| `gold_stand_change` | 102 | 10 | gold |
| `gold_stand_narrative` | 40 | 7 | gold |
| `gold_stand_facts` | 102 | 23 | gold |
| `gold_dim_stand` | 120 | 8 | gold |
| `gold_dim_date` | 365 | 7 | gold |
| `gold_dim_forest_class` | 7 | 4 | gold |
| `gold_pipeline_run_summary` | 1 | 10 | gold |

## Reading the row counts

The counts are not all the same, and the differences are the interesting part.

**120 stands, 102 classified.** Eighteen stands had a `valid_pixel_fraction`
below 0.60, meaning more than 40 percent of the canopy was cloud, shadow or
cirrus in every scene in the window. Notebook 03 excludes them rather than
publishing a class derived from a handful of pixels. If your run classifies all
120, check that the valid-pixel gate is actually wired in, because a clean 120
usually means the threshold is being ignored rather than that your imagery was
perfect.

**40 narratives, not 102.** Notebook 04 only writes a narrative for stands that
warrant attention, which keeps the model cost proportional to the value. In the
reference run all 40 carry `validation_status = "stubbed"` because no Foundry
endpoint was configured. With a live endpoint you should see a mixture of `ok`
and at least one other status, because the numeric guard does fire in practice.

**365 dates.** The date dimension is padded to whole calendar years and must be
contiguous. Power BI rejects a date table with gaps, and the failure is a blank
result from every time intelligence measure rather than an error.

## Value ranges worth checking against

| Field | Reference range | What a value outside it means |
|---|---|---|
| `ndvi_mean` | 0.413 to 0.622 | Outside -1 to 1 is an arithmetic bug. Near zero over forest suggests a missing scale factor |
| `ndmi_mean` | 0.124 to 0.308 | Uniformly low usually means unmasked thin cirrus, not drought |
| `epsg` in the scene catalogue | 32619 | A zero means the projection metadata was not recorded |
| `lat` in `gold_dim_stand` | 46.1 to 46.4 | Anything else means a reprojection or a lat/lon swap |
| `lon` in `gold_dim_stand` | -66.9 to -66.4 | A positive value is a dropped minus sign |

## What this file is not

It is not a fixture to load instead of running the pipeline, and it is not a
test oracle. Your numbers will differ from these, because the scenes available
for your area and window differ. Shapes, types, ranges and the relationships
between the row counts are what should match.
