"""Reusable building blocks for the Woodlands forest classification pipeline.

The workshop notebooks are deliberately self-contained so that every line is
visible while it is being taught. This package is the same logic after it has
been lifted out of the notebooks, which is the refactor discussed in Session 2,
Step 5. Import it from a notebook once you are past the teaching phase:

    import sys
    sys.path.append("/lakehouse/default/Files/code")
    from forestops import config, indices, classify
"""

__version__ = "1.0.0"

__all__ = [
    "config",
    "aoi",
    "stac_ingest",
    "raster",
    "indices",
    "zonal",
    "classify",
    "change",
    "narrative",
    "delta_io",
    "quality",
]
