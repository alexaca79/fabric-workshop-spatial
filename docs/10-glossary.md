---
title: Glossary
description: Fabric, geospatial, remote sensing and AI terms used across the workshop, defined for a mixed audience of foresters and data practitioners
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: reference
keywords:
  - glossary
  - terminology
estimated_reading_time: 7
---

## Glossary

Written for a room that mixes forestry and data backgrounds. Nobody should have
to pretend they know what a COG is.

## Fabric and OneLake

Capacity
: The compute you are billed for, sized as an F SKU. A workspace runs on exactly
one capacity, and throttling is a capacity-level event rather than a
workspace-level one.

Delta table
: A folder of Parquet files plus a transaction log. The log is what gives you
time travel, atomic writes and schema enforcement. When someone says "the table
is a folder", this is what they mean.

Direct Lake
: A Power BI storage mode that reads Delta files in OneLake directly, with no
import copy and no DirectQuery round trip. Falls back to DirectQuery silently
when the model uses something it cannot support.

Lakehouse
: A Fabric item with two halves. `Files/` holds anything, `Tables/` holds Delta
tables. The same storage is readable through Spark, through the SQL analytics
endpoint, and through Power BI.

OneLake
: One storage account for the whole tenant. Every workspace has a folder in it.
The practical consequence is that a shortcut can reference data anywhere without
copying it.

Shortcut
: A reference to data that lives somewhere else, presented as if it were local.
No copy, no second refresh schedule, and permissions follow the source.

SQL analytics endpoint
: A read-only T-SQL surface over the Delta tables in a Lakehouse. Same files, a
different engine, no additional storage.

Workspace
: The unit of access control, capacity assignment and lifecycle. If you are
arguing about who can see what, you are arguing about workspaces.

## Geospatial

CRS, coordinate reference system
: The rules that turn coordinates into positions on the earth. Two datasets with
different CRS values cannot be compared until one is transformed.

EPSG code
: A numeric identifier for a CRS. EPSG:4326 is WGS84 in degrees, EPSG:2953 is
the New Brunswick Stereographic Double Projection in metres.

Geodetic versus projected
: Geodetic coordinates are angles on a sphere and are measured in degrees.
Projected coordinates are flattened onto a plane and are measured in metres.
Area and distance are only meaningful in a projected CRS.

Reprojection
: Transforming coordinates from one CRS to another. Doing it twice by accident
is the most common geospatial bug in existence.

SRID
: Spatial reference identifier, in practice the same number as the EPSG code.
Stored alongside geometry so that a consumer knows what the numbers mean.

UTM zone
: A projected CRS covering a six-degree strip of longitude. New Brunswick spans
zones 19N and 20N, which is why an area of interest crossing the boundary needs
handling.

WKB, well-known binary
: A compact binary encoding of a geometry. Used here because Spark has no native
geometry type, so geometry travels as bytes with the SRID in a separate column.

Zonal statistics
: Summarising raster pixel values within polygon boundaries. This is the step
that turns imagery into one row per forest stand.

## Remote sensing

Band
: One wavelength range recorded by the sensor. Sentinel-2 records thirteen. This
workshop uses red, near infrared and two shortwave infrared bands, plus the
scene classification layer.

COG, cloud optimized GeoTIFF
: A GeoTIFF organised so that a client can fetch just the part it needs over
HTTP range requests. This is why you can analyse a scene without downloading it.

EVI, enhanced vegetation index
: A greenness index that saturates less than NDVI in dense canopy, which matters
in mature forest where NDVI flattens out.

NBR, normalised burn ratio
: Uses near infrared against shortwave infrared. Sensitive to fire and to
harvest, because both remove canopy and expose bare ground.

NDMI, normalised difference moisture index
: Canopy moisture. Drops under drought stress and after canopy removal. Sensitive
to the reflectance scale factor, which is why the scaling step matters.

NDVI, normalised difference vegetation index
: The standard greenness index. Robust and well understood, and it saturates in
closed canopy, which limits how much it can tell you about mature stands.

Scale factor
: Sentinel-2 Level 2A stores surface reflectance as integers, so values divide by
10000 to become reflectance between 0 and 1. Skipping this cancels out in
normalised ratios and quietly breaks absolute thresholds.

SCL, scene classification layer
: A per-pixel class raster shipped with Sentinel-2 L2A, used to mask cloud,
cloud shadow, snow and saturated pixels.

Sentinel-2 Level 2A
: Surface reflectance imagery, atmospherically corrected, at 10 to 20 metre
resolution, revisited every five days. Free and open under the Copernicus
licence.

STAC, SpatioTemporal Asset Catalog
: A standard for describing geospatial assets so they can be searched by
geometry, date and property. A Catalog holds Collections, a Collection holds
Items, and an Item points at Assets.

Signing
: Appending a short-lived token to a Planetary Computer asset URL so it can be
read. Tokens expire, so sign at the point of use and never persist the result.

## Forestry

Licence block
: A management unit within a forest licence. Used here as the grouping level
above the stand.

Mixedwood
: A stand where neither softwood nor hardwood dominates. It is the class most
often confused by spectral classification, because the mixture is exactly what
the index values average out.

Softwood and hardwood
: Conifer and deciduous respectively. They separate reasonably well in near
infrared and shortwave infrared, particularly outside the peak growing season.

Stand
: A contiguous area of forest managed as a unit, uniform enough in species,
age and condition to be treated as one thing. The grain of everything in this
pipeline.

Stand register
: The inventory table listing stands with their attributes and boundaries. In
this workshop it is generated synthetically so the exercises run without access
to production inventory.

## AI

Deployment
: A named, versioned instance of a model in Foundry. Recorded alongside every
generated narrative, because "the wording changed" is otherwise unanswerable.

Grounding
: Passing the facts into the prompt rather than relying on what the model
already knows. Every number in a narrative here is grounded in a silver row.

Hallucination
: A confident, fluent, wrong output. The failure mode that matters in this
pipeline is not an obviously wrong answer, it is a plausible one that nobody
checks.

Schema-constrained output
: Requiring the model to return a specific JSON shape, so the response can be
parsed and validated rather than interpreted.

Validation status
: The column recording whether a generated narrative passed its numeric and
schema checks. A narrative that fails is suppressed and flagged rather than
dropped, so the failure stays visible.
