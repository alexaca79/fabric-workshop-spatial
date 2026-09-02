"""Pin down the affine/odc-geo incompatibility that breaks odc.stac.load.

odc.stac.load raised:
    TypeError: No '__dict__' attribute on 'Affine' instance to cache '_astuple'

That happens when Affine defines _astuple as a functools.cached_property while
the class carries no instance __dict__. Record the exact versions and reproduce
the failure in isolation so the fix can be verified rather than assumed.
"""

import importlib
import inspect
import traceback


def record(key, fn):
    try:
        findings[key] = {"ok": True, "value": str(fn())[:600]}
    except Exception as exc:
        findings[key] = {"ok": False, "value": f"{type(exc).__name__}: {exc}"[:600]}


for name in ("affine", "odc.geo", "odc.stac", "rasterio", "pyproj", "xarray", "rioxarray"):
    record(
        f"version::{name}",
        lambda n=name: getattr(importlib.import_module(n), "__version__", "no __version__"),
    )


def affine_shape():
    import affine

    cls = affine.Affine
    return {
        "bases": [b.__name__ for b in cls.__mro__[:4]],
        "has_slots": hasattr(cls, "__slots__"),
        "slots": getattr(cls, "__slots__", None),
        "astuple_type": type(cls.__dict__.get("_astuple")).__name__,
    }


record("affine_shape", affine_shape)


def iterate_affine():
    """This is the exact operation odc.geo performs and that blew up."""
    from affine import Affine

    a = Affine(20.0, 0.0, 400000.0, 0.0, -20.0, 5200000.0)
    return list(a)


record("iter_affine", iterate_affine)


def astuple_source():
    import affine

    return inspect.getsource(affine.Affine.__iter__)


record("affine_iter_source", astuple_source)
