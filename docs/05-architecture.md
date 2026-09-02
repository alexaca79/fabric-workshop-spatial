---
title: Architecture
description: Medallion architecture, data contracts, table schemas, coordinate reference systems and orchestration design for the forest classification pipeline
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: concept
keywords:
  - medallion architecture
  - delta lake
  - onelake
  - epsg 2953
  - direct lake
estimated_reading_time: 12
---

## Architecture

The pipeline turns public satellite imagery and a forest stand register into a
stand-level classification that a Woodlands planner can filter on a map. Three
layers, one storage account, one orchestration.

## Layer contracts

Each layer signs a different contract. Confusing them is the most common way a
lakehouse becomes unmaintainable.

| Layer  | Promise                                     | Allowed to change                     | Never                                     |
|--------|---------------------------------------------|---------------------------------------|-------------------------------------------|
| Bronze | Fidelity to source                          | Add ingest metadata columns           | Reproject, mask, rename, deduplicate      |
| Silver | Comparability across scenes and dates       | Reproject, mask, derive, join, filter | Apply business rules or thresholds        |
| Gold   | Meaning for a named decision                | Classify, aggregate, label, enrich    | Invent a number without a silver source   |

The practical test: if a number in a report is questioned, you should be able to
walk it back to a bronze row without re-running anything.

## Data flow

```text
  Planetary Computer STAC                 Stand register (synthetic or JDI)
  sentinel-2-l2a                          stand_id, species_group, geometry
          |                                             |
          | pystac-client search                        | GeoPandas read
          | planetary_computer.sign                     |
          v                                             v
  ┌──────────────────────────────────────────────────────────────────────┐
  │ BRONZE                                                               │
  │   Files/bronze/scenes/<scene_id>/*.tif    raw windowed COG reads     │
  │   Tables/bronze_scene_catalog             one row per scene          │
  │   Tables/bronze_stand_register            geometry as WKB + srid     │
  └──────────────────────────────────────────────────────────────────────┘
          |
          | cloud mask from SCL, scale reflectance, reproject to EPSG:2953,
          | compute NDVI / NDMI / NBR / EVI, zonal stats per stand
          v
  ┌──────────────────────────────────────────────────────────────────────┐
  │ SILVER                                                               │
  │   Tables/silver_stand_observations        stand x scene_date grain   │
  │     ndvi_mean, ndvi_p90, ndmi_mean, nbr_mean, valid_pixel_fraction   │
  └──────────────────────────────────────────────────────────────────────┘
          |
          | rule-based or trained classifier, change detection vs baseline
          v
  ┌──────────────────────────────────────────────────────────────────────┐
  │ GOLD                                                                 │
  │   Tables/gold_stand_classification        stand x period, class      │
  │   Tables/gold_stand_change                harvest and stress events  │
  │   Tables/gold_stand_narrative             AI text + validation flag  │
  │   Tables/gold_stand_facts + gold_dim_*    star schema for Direct Lake│
  └──────────────────────────────────────────────────────────────────────┘
          |
          v
  Direct Lake semantic model  ->  Power BI map, trend, tooltip narrative
```

## Coordinate reference systems

Three CRS values appear in the pipeline, and mixing them is the single most
common source of wrong numbers.

| CRS         | Name                                        | Used for                                         |
|-------------|---------------------------------------------|--------------------------------------------------|
| EPSG:4326   | WGS84 geographic, degrees                    | STAC search geometry, Power BI map points        |
| EPSG:32619  | UTM zone 19N, metres                         | Native Sentinel-2 grid for western New Brunswick |
| EPSG:2953   | NAD83(CSRS) New Brunswick Stereographic      | Analysis, area, distance, all silver and gold    |

Rules the pipeline enforces:

- Never compute area or distance in EPSG:4326. Square degrees are not a unit
  anyone can act on, and the error varies with latitude.
- Reproject once, in silver, and store the result. Reprojecting per query is
  both slow and a source of drift between reports.
- Every table carrying geometry also carries an `srid` column. A WKB blob with
  no declared CRS is a future incident.
- Sentinel-2 scenes crossing the zone 19N and 20N boundary must be reprojected
  before mosaicking, not after.

## Table schemas

### bronze_scene_catalog

| Column             | Type      | Notes                                              |
|--------------------|-----------|-----------------------------------------------------|
| scene_id           | string    | STAC item id, primary key                          |
| collection         | string    | `sentinel-2-l2a`                                    |
| datetime_utc       | timestamp | Scene acquisition time                              |
| cloud_cover_pct    | double    | `eo:cloud_cover` from item properties               |
| epsg               | int       | Native scene CRS, typically 32619 or 32620          |
| bbox_wgs84         | string    | JSON array, the requested window not the full scene |
| assets_json        | string    | Unsigned asset hrefs, for provenance                |
| ingested_at_utc    | timestamp | Pipeline run time                                   |
| pipeline_run_id    | string    | Correlates every table written by one run           |

Unsigned hrefs are stored deliberately. A signed href is a credential with an
expiry, and persisting one creates both a security problem and a support ticket
when it stops working three days later.

### bronze_stand_register

| Column        | Type   | Notes                                        |
|---------------|--------|-----------------------------------------------|
| stand_id      | string | Stable business key                           |
| licence_block | string | Management unit                               |
| species_group | string | Declared species group from inventory         |
| planted_year  | int    | Nullable for natural stands                   |
| geometry_wkb  | binary | Polygon as WKB                                |
| srid          | int    | 4326 on ingest                                |
| source        | string | `synthetic` or `jdi-inventory`                |

### silver_stand_observations

Grain: one row per `stand_id` per `scene_date`.

| Column                | Type      | Notes                                            |
|-----------------------|-----------|---------------------------------------------------|
| stand_id              | string    |                                                   |
| scene_id              | string    | Foreign key to bronze_scene_catalog               |
| scene_date            | date      |                                                   |
| ndvi_mean             | double    | Cloud-masked, scaled reflectance                  |
| ndvi_p90              | double    | Resistant to shadow in the tail                   |
| ndmi_mean             | double    | Canopy moisture                                   |
| nbr_mean              | double    | Burn and harvest sensitivity                      |
| evi_mean              | double    | Less saturating than NDVI in dense canopy         |
| valid_pixel_fraction  | double    | Quality gate. Below 0.6 the row is not trusted    |
| pixel_count           | int       |                                                   |
| area_ha               | double    | Computed in EPSG:2953                             |
| srid                  | int       | 2953                                              |

`valid_pixel_fraction` is the column that keeps the gold layer honest. A stand
that is 90 percent cloud produces a perfectly reasonable-looking NDVI mean from
the remaining ten percent of pixels, and nothing downstream would notice.

### gold_stand_classification

| Column           | Type   | Notes                                                        |
|------------------|--------|---------------------------------------------------------------|
| stand_id         | string |                                                               |
| period_start     | date   | Compositing window start                                      |
| period_end       | date   |                                                               |
| forest_class     | string | softwood, hardwood, mixedwood, regenerating, recently_harvested, non_forest |
| class_confidence | double | 0 to 1                                                        |
| class_method     | string | `rule_v1` or `rf_v1`, so a number can be traced to its logic  |
| observation_count| int    | Scenes contributing to the composite                          |

### gold_stand_change

| Column          | Type   | Notes                                            |
|-----------------|--------|---------------------------------------------------|
| stand_id        | string |                                                   |
| detected_on     | date   |                                                   |
| change_type     | string | harvest, disturbance, moisture_stress, regrowth   |
| delta_nbr       | double | Baseline minus current                            |
| severity        | string | low, moderate, high                               |
| requires_review | bool   | Drives the planner work queue                     |

### gold_stand_narrative

| Column            | Type      | Notes                                                     |
|-------------------|-----------|------------------------------------------------------------|
| stand_id          | string    |                                                            |
| period_end        | date      |                                                            |
| narrative         | string    | Two sentences, generated by Foundry, suppressed on failure |
| validation_status | string    | ok, numeric_mismatch, schema_invalid, suppressed, stubbed  |
| model_deployment  | string    | Deployment name and version at generation time             |
| generated_at_utc  | timestamp |                                                            |

Storing the deployment name matters. When a narrative reads differently next
month, the first question is whether the model changed, and without this column
that question is unanswerable.

## Orchestration

A single Fabric data pipeline runs the notebooks in order, with parameters so
that the same definition serves any area of interest.

| Parameter        | Example                                  | Purpose                                |
|------------------|------------------------------------------|-----------------------------------------|
| aoi_name         | `central-nb-block-a`                     | Names outputs and partitions            |
| aoi_bbox         | `[-66.9, 46.1, -66.4, 46.4]`             | WGS84 west, south, east, north          |
| date_start       | `2026-06-01`                             | Compositing window                      |
| date_end         | `2026-08-31`                             |                                         |
| max_cloud_cover  | `20`                                     | STAC filter                             |
| target_epsg      | `2953`                                   | Analysis projection                     |
| enable_ai        | `true`                                   | Skips notebook 04 when false            |

Between silver and gold sits one quality gate. If fewer than a configured
fraction of stands have a trusted observation, the run stops and notifies rather
than publishing a month that looks complete and is not.

## Why Direct Lake

The gold tables are already Delta in OneLake. Direct Lake reads those files
directly, so there is no import refresh to schedule, no duplicate copy of the
data, and no DirectQuery round trip per visual. The cost is discipline in the
model: a clean star schema, a real date table, and no calculated columns or
unsupported types that force a fallback to DirectQuery.

The fallback is silent by default, which is why the publish notebook includes an
explicit check.

## What this architecture does not do

- It does not replace field cruising. It narrows where a crew goes.
- It does not detect change below the resolution of a Sentinel-2 pixel, so
  selective thinning is largely invisible at 10 to 20 metres.
- It does not carry a legal or regulatory guarantee. Every gold number traces to
  a silver row and a scene, which is what makes it defensible, but the defence is
  the traceability rather than the classifier.
