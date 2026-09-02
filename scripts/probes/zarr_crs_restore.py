"""Verify the two candidate restores for the CRS lost through the Zarr round trip.

Established by the previous probe: xarray writes `spatial_ref` as a plain data
variable, so on read it is no longer a coordinate and rioxarray reports no CRS.
Test both fixes on the real cache file before changing the notebooks.
"""

AOI_NAME = "central-nb-block-a"
CACHE = f"/lakehouse/default/Files/bronze/bronze/scenes/{AOI_NAME}/_session_cache.zarr"


def record(key, fn):
    try:
        findings[key] = {"ok": True, "value": str(fn())[:700]}
    except Exception as exc:
        findings[key] = {"ok": False, "value": f"{type(exc).__name__}: {exc}"[:700]}


import xarray as xr  # noqa: E402
import rioxarray  # noqa: E402, F401

cached = xr.open_zarr(CACHE)

# What survived on the demoted variable? This decides whether set_coords alone
# is enough, or whether the EPSG has to be carried separately.
record("spatial_ref_is_data_var", lambda: "spatial_ref" in cached.data_vars)
record("spatial_ref_attr_names", lambda: sorted(cached["spatial_ref"].attrs))
record(
    "spatial_ref_crs_wkt_head",
    lambda: str(cached["spatial_ref"].attrs.get("crs_wkt", "ABSENT"))[:120],
)

# Fix A: promote it back to a coordinate.
record("fixA_set_coords_crs", lambda: cached.set_coords("spatial_ref").rio.crs)

# Fix B: rewrite the CRS explicitly from a recorded EPSG code.
record("fixB_write_crs_32619", lambda: cached.rio.write_crs("EPSG:32619").rio.crs)

# Do dataset-level attrs survive a Zarr round trip? That is what makes the
# explicit EPSG fallback viable.
PROBE = "/lakehouse/default/Files/_attrs_roundtrip.zarr"


def attrs_survive():
    small = cached[["B04"]].isel(time=slice(0, 1), x=slice(0, 8), y=slice(0, 8))
    small.attrs["crs_epsg"] = 32619
    small.to_zarr(PROBE, mode="w", consolidated=True)
    return dict(xr.open_zarr(PROBE).attrs)


record("dataset_attrs_survive", attrs_survive)


# The combined restore exactly as it will be written into notebook 02.
def combined_restore():
    ds = xr.open_zarr(CACHE)
    if "spatial_ref" in ds.data_vars:
        ds = ds.set_coords("spatial_ref")
    if ds.rio.crs is None and "crs_epsg" in ds.attrs:
        ds = ds.rio.write_crs(f"EPSG:{ds.attrs['crs_epsg']}")
    return f"crs={ds.rio.crs}, coords={list(ds.coords)}"


record("combined_restore", combined_restore)
