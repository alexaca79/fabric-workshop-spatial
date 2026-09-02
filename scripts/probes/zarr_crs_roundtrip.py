"""Work out why the CRS does not survive the Zarr session cache round trip.

Notebook 02 reloads the cube written by notebook 01 and its CRS guard fires:
`raster has no CRS`. Establish what is actually in the file, and test the
candidate fix (rio.write_crs before to_zarr) rather than assuming it works.
"""

AOI_NAME = "central-nb-block-a"
CACHE = f"/lakehouse/default/Files/bronze/bronze/scenes/{AOI_NAME}/_session_cache.zarr"


def record(key, fn):
    try:
        findings[key] = {"ok": True, "value": str(fn())[:700]}
    except Exception as exc:
        findings[key] = {"ok": False, "value": f"{type(exc).__name__}: {exc}"[:700]}


import xarray as xr  # noqa: E402
import rioxarray  # noqa: E402, F401  (registers the .rio accessor)

record("cache_path_used", lambda: CACHE)

cached = None


def open_cache():
    global cached
    cached = xr.open_zarr(CACHE)
    return f"opened, dims={dict(cached.sizes)}"


record("open_cache", open_cache)
record("cache_coords", lambda: list(cached.coords))
record("cache_data_vars", lambda: list(cached.data_vars))
record("cache_rio_crs", lambda: cached.rio.crs)
record("cache_spatial_ref_attrs", lambda: dict(cached["spatial_ref"].attrs) if "spatial_ref" in cached.coords else "no spatial_ref coord")
record("cache_b04_attrs", lambda: dict(cached["B04"].attrs) if "B04" in cached.data_vars else "no B04")
record("cache_ds_attrs", lambda: dict(cached.attrs))

# Now the round trip test: does write_crs before to_zarr preserve it?
import odc.stac  # noqa: E402
import planetary_computer as pc  # noqa: E402
import pystac_client  # noqa: E402

AOI_BBOX = (-66.90, 46.10, -66.40, 46.40)
fresh = None


def load_fresh():
    global fresh
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace
    )
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=list(AOI_BBOX),
        datetime="2026-06-01/2026-08-31",
        query={"eo:cloud_cover": {"lt": 20}},
    )
    items = sorted(search.items(), key=lambda i: i.properties.get("eo:cloud_cover", 100))[:1]
    fresh = odc.stac.load(items, bands=["B04", "B08"], bbox=list(AOI_BBOX),
                          resolution=20, chunks={}, groupby="solar_day")
    return f"loaded {dict(fresh.sizes)}"


record("load_fresh", load_fresh)
record("fresh_rio_crs", lambda: fresh.rio.crs)
record("fresh_coords", lambda: list(fresh.coords))

PROBE_OUT = "/lakehouse/default/Files/_crs_roundtrip_test.zarr"


def roundtrip_plain():
    fresh.to_zarr(PROBE_OUT, mode="w", consolidated=True)
    return str(xr.open_zarr(PROBE_OUT).rio.crs)


record("roundtrip_plain_crs", roundtrip_plain)


def roundtrip_with_write_crs():
    tagged = fresh.rio.write_crs(fresh.rio.crs)
    tagged.to_zarr(PROBE_OUT + "2", mode="w", consolidated=True)
    back = xr.open_zarr(PROBE_OUT + "2")
    return str(back.rio.crs)


record("roundtrip_write_crs_crs", roundtrip_with_write_crs)


def roundtrip_write_crs_coords():
    back = xr.open_zarr(PROBE_OUT + "2")
    return {
        "coords": list(back.coords),
        "spatial_ref_attrs": sorted(back["spatial_ref"].attrs)[:8] if "spatial_ref" in back.coords else None,
    }


record("roundtrip_write_crs_shape", roundtrip_write_crs_coords)
