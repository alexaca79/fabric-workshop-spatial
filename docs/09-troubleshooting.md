---
title: Troubleshooting
description: Symptoms, causes and fixes for the errors participants hit most often across Fabric, STAC ingestion, geospatial processing, Foundry and Direct Lake
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: troubleshooting
keywords:
  - troubleshooting
  - errors
  - fabric
  - stac
  - direct lake
estimated_reading_time: 10
---

## Troubleshooting

Organised by where you are when it breaks. Search this page before asking, then
ask quickly rather than grinding.

## Fabric and Lakehouse

### The notebook cannot find the Lakehouse

```text
Py4JJavaError: Path does not exist: abfss://.../Tables/bronze_stand_register
```

The notebook has no default Lakehouse attached, or it is attached to a different
one. In the Explorer pane on the left, add `lh_woodlands` and set it as default.
Restart the session afterwards; attaching does not retro-fit an already running
session.

### Writing a GeoDataFrame to Delta fails

```text
AnalysisException: Cannot resolve column 'geometry' due to data type mismatch
```

Spark has no geometry type. Serialise to WKB first and carry the CRS in its own
column:

```python
sdf = spark.createDataFrame(
    gdf.assign(geometry_wkb=gdf.geometry.apply(lambda g: g.wkb), srid=gdf.crs.to_epsg())
       .drop(columns="geometry")
)
```

### Table exists but the SQL analytics endpoint does not see it

The endpoint metadata syncs asynchronously and lags by up to a couple of minutes.
Refresh the endpoint from the Lakehouse view. If it still does not appear after
five minutes, the write probably went to `Files/` rather than `Tables/`.

### Session takes minutes to start, or dies mid-run

Capacity is throttled or the session was idle-recycled. Check the Fabric capacity
metrics app. During the workshop, tell a facilitator rather than retrying; a
throttled capacity does not improve by being asked again.

### `%pip install` succeeded earlier and now the import fails

The session recycled and installs do not persist. Re-run the install cell, or
attach the `env-woodlands-geo` environment so the libraries are baked into the
session start.

## Planetary Computer and STAC

### The search returns zero items

Work through these in order:

1. Bounding box order. It is west, south, east, north. Reversing the pairs
   silently returns nothing.
2. Longitude sign. New Brunswick is around -66, not 66.
3. Date range. Widen it before touching the cloud filter.
4. Cloud filter. `eo:cloud_cover` is scene-wide, so a mostly clear scene can be
   excluded because of cloud far from your area.

```python
search = catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=AOI_BBOX,                       # [west, south, east, north]
    datetime=f"{DATE_START}/{DATE_END}",
    query={"eo:cloud_cover": {"lt": MAX_CLOUD}},
)
print(f"{len(list(search.items()))} items")
```

### Asset reads return HTTP 403

The href was not signed, or the signature expired. Sign at the point of use:

```python
import planetary_computer as pc
signed = pc.sign(item)
```

Never store a signed href in a table. It is a credential with an expiry, and it
will fail later in a way that looks like an outage.

### Reads are extremely slow

You are probably reading whole scenes rather than windows. Pass the bounding box
into the loader so only the relevant blocks of the Cloud Optimized GeoTIFF are
fetched:

```python
ds = odc.stac.load(items, bands=BANDS, bbox=AOI_BBOX, resolution=20, chunks={})
```

Also check resolution. Loading at 10 m when 20 m answers the question costs four
times the bytes for no additional insight at stand scale.

## Geospatial processing

### `to_crs` raises about a missing CRS

```text
ValueError: Cannot transform naive geometries. Please set a CRS on the object first.
```

The frame has no declared CRS. Set it, do not guess silently:

```python
gdf = gdf.set_crs(4326)   # declare what it already is
gdf = gdf.to_crs(2953)    # then transform
```

Calling `set_crs` on data that is already projected relabels it without moving
anything, which produces geometries in the wrong place and no error at all.

### Areas are tiny numbers like 0.0004

Area was computed in degrees. Reproject to EPSG:2953 first, then compute:

```python
gdf_m = gdf.to_crs(2953)
gdf_m["area_ha"] = gdf_m.geometry.area / 10_000
```

### Areas are enormous, or geometries land in the ocean

Double projection. The data was already in metres and got transformed again.
Print `gdf.crs` and `gdf.total_bounds` before and after every transform while
debugging. Coordinates in the millions with a CRS of 4326 is the signature.

### Zonal statistics return all NaN

Three usual causes:

1. The stands and the raster are in different CRS values. Align them first.
2. The stands fall outside the raster window. Compare `total_bounds` for both.
3. Everything was masked out as cloud. Check `valid_pixel_fraction` before
   concluding the maths is wrong.

### NDVI looks right but NDMI values are implausible

The reflectance scale factor was not applied. Sentinel-2 L2A stores surface
reflectance as integers, so divide by 10000. NDVI hides the error because the
scale cancels in a normalised ratio of two same-scaled bands, while any threshold
you set on an absolute value moves.

```python
ref = ds[BANDS].astype("float32") / 10_000.0
```

## Microsoft Foundry

### Authentication fails from the Spark session

Managed identity is not always available in a notebook session. Use a key from a
Key Vault-backed configuration, or set `USE_OFFLINE_STUB = True` and continue.
Notebook 04 produces the same table shape either way, so nothing downstream
breaks.

### The model returns prose when a JSON object was requested

Ask for structured output explicitly rather than in the prompt text, and validate
before writing:

```python
response = client.chat.completions.create(
    model=DEPLOYMENT,
    messages=messages,
    response_format={"type": "json_object"},
    temperature=0,
)
```

If a response still fails to parse, write the row with
`validation_status = "schema_invalid"` and an empty narrative. Never retry
silently in a loop; you will discover the cost at the end of the month.

### Rate limited part way through a batch

Add a small delay between calls and process in batches, and make the batch
resumable by writing after each batch rather than at the end. A 500-stand run
that fails at stand 480 and has written nothing is a bad afternoon.

## Power BI and Direct Lake

### The semantic model falls back to DirectQuery

Common causes, in order of frequency: a calculated column on a large table, an
unsupported data type such as binary in the model, a view rather than a table, or
a table above the row limit for the capacity SKU.

Fix by keeping WKB out of the semantic model. Publish latitude and longitude
centroids as doubles for mapping, and leave the geometry in the Lakehouse for
notebooks that need it.

### The map shows nothing

Latitude and longitude are reversed, or they are still in projected metres.
Power BI map visuals want WGS84 degrees. Produce centroids explicitly:

```python
cent = gdf.to_crs(2953).geometry.centroid.to_crs(4326)
gdf["lon"] = cent.x
gdf["lat"] = cent.y
```

Note the order: compute the centroid in the projected CRS so it is geometrically
correct, then convert the point to degrees for display.

### New rows do not appear in the report

Direct Lake picks up changes, but the semantic model may need a framing refresh
after a schema change. A schema change is not the same as a data change; adding
a column requires the model to be refreshed before the column exists to Power BI.

## Still stuck

Post in the workshop Teams channel with three things: what you ran, the full
error text, and what you expected. That is usually enough for someone to answer
in one message. Screenshots of a truncated error cost a round trip.
