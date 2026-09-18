---
title: Pre-flight check
description: Dependency-free environment and access verification script to run at the start of Session 1, with a triage table for every failure mode
author: Workshop Delivery Team
ms.date: 2026-09-17
ms.topic: troubleshooting
keywords:
  - preflight
  - environment check
  - triage
estimated_reading_time: 5
---

## Pre-flight check

The first twenty minutes of Session 1 exist to find broken environments while
there is still time to fix them. Run the script below in a Fabric notebook
attached to `lh_woodlands`. It uses only the standard library plus PySpark, so
it works before any `%pip install` has run.

## The script

```python
# Woodlands workshop pre-flight. Paste into a Fabric notebook cell and run.
import importlib
import json
import socket
import sys
import urllib.request

RESULTS = []


def check(name, fn, fatal=False):
    try:
        detail = fn()
        RESULTS.append(("PASS", name, detail or ""))
    except Exception as exc:  # noqa: BLE001 - we want every failure reported
        RESULTS.append(("FATAL" if fatal else "WARN", name, f"{type(exc).__name__}: {exc}"))


def _python():
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _spark():
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    return f"Spark {spark.version}"


def _lakehouse():
    import notebookutils

    mounts = notebookutils.fs.mounts()
    default = [m for m in mounts if m.get("mountPoint") == "/default"]
    if not default:
        raise RuntimeError("No default lakehouse attached. Use the Explorer pane to attach lh_woodlands.")
    return default[0].get("source", "attached")


def _write_read():
    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    df = spark.createDataFrame([(1, "preflight")], ["id", "label"])
    df.write.mode("overwrite").format("delta").saveAsTable("preflight_probe")
    n = spark.table("preflight_probe").count()
    spark.sql("DROP TABLE IF EXISTS preflight_probe")
    return f"wrote and read {n} row"


def _dns():
    ip = socket.gethostbyname("planetarycomputer.microsoft.com")
    return f"planetarycomputer.microsoft.com -> {ip}"


def _stac():
    url = "https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a"
    with urllib.request.urlopen(url, timeout=25) as resp:
        payload = json.load(resp)
    return f"collection '{payload['id']}' reachable"


def _geo_libs():
    present, missing = [], []
    for mod in ("geopandas", "rasterio", "rioxarray", "pystac_client", "planetary_computer", "odc.stac"):
        try:
            importlib.import_module(mod)
            present.append(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        raise ImportError(f"missing {missing}; attach env_forestops and restart the session")
    return f"{len(present)} geospatial libraries present"


def _foundry():
    import os

    endpoint = os.environ.get("FOUNDRY_ENDPOINT")
    if not endpoint:
        raise RuntimeError("FOUNDRY_ENDPOINT not set; notebook 04 will use the offline stub")
    return endpoint


check("Python runtime", _python, fatal=True)
check("Spark session", _spark, fatal=True)
check("Lakehouse attached", _lakehouse, fatal=True)
check("Delta write and read", _write_read, fatal=True)
check("Outbound DNS", _dns, fatal=True)
check("Planetary Computer STAC API", _stac, fatal=True)
check("Geospatial libraries", _geo_libs)
check("Foundry endpoint", _foundry)

width = max(len(name) for _, name, _ in RESULTS)
for status, name, detail in RESULTS:
    print(f"[{status:<5}] {name.ljust(width)}  {detail}")

fatal = [r for r in RESULTS if r[0] == "FATAL"]
print()
print(f"{len(RESULTS) - len(fatal)} of {len(RESULTS)} checks usable, {len(fatal)} blocking")
if fatal:
    print("Blocking failures. Show this output to a facilitator before continuing.")
```

## Reading the output

A `WARN` is survivable. A `FATAL` means you cannot proceed unaided, and the
facilitator moves you onto the fallback path immediately rather than debugging
in front of the room.

## Triage table

| Symptom                                              | Cause                                             | Fix                                                                                |
|------------------------------------------------------|---------------------------------------------------|------------------------------------------------------------------------------------|
| `No default lakehouse attached`                       | Notebook opened outside the Lakehouse context     | Explorer pane, Lakehouses, Add, pick `lh_woodlands`, set as default                 |
| Delta write fails with a permission error             | Workspace on a Pro licence, or Viewer role        | Facilitator moves you to the shared capacity workspace                             |
| DNS resolution fails                                  | Tenant blocks outbound traffic from Spark         | Switch to the cached-scene fallback in `docs/09-troubleshooting.md`                 |
| STAC reachable but asset reads return 403             | Signing step skipped                              | Every asset href must pass through `planetary_computer.sign`                        |
| `missing ['odc.stac', ...]`                           | Environment not attached                          | Attach `env_forestops`, then restart the notebook session                           |
| Spark session takes longer than five minutes to start | Capacity throttled or cold                        | Facilitator checks capacity metrics; use a neighbour's screen in the meantime       |
| `FOUNDRY_ENDPOINT not set`                            | Expected before Session 2                         | Ignore for Session 1; notebook 04 falls back to an offline stub                     |

## Fallback for anyone still blocked

Three tiers, applied in order.

1. Shared workspace. The facilitator keeps `ws-woodlands-shared` open with the
   solution notebooks already run. You get write access and work there.
2. Pair up. Two people, one keyboard. The person who is blocked drives.
3. Read-only path. Work the notebooks locally against the sample outputs
   committed under `notebooks/sample-outputs/`, and rejoin at the next break.

None of these is a failure state. The point of the day is the pattern, not the
plumbing, and the plumbing is the part most likely to be different at your
site anyway.
