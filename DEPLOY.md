---
title: Deployment guide for Fabric
description: How to review, deploy and verify the forest classification workshop in a Microsoft Fabric tenant, including the workspace topology and outbound access protection decisions that have to be made first
author: Workshop Delivery Team
ms.date: 2026-09-17
ms.topic: how-to
keywords:
  - deployment
  - microsoft fabric
  - outbound access protection
  - workspace topology
  - medallion
estimated_reading_time: 15
---

## Deployment guide for Fabric

This is the practical guide to standing the workshop up in a Fabric tenant. It
assumes you have a Fabric capacity and workspace admin rights, and that you want
to satisfy yourself the thing works before a room of people depends on it.

The six solution labs and Environment preflight completed on an F64 capacity.
The current manual-workspace results and their limitations are recorded in
[the lab guide](docs/16-manual-upload-labs.md). Live Foundry calls, the optional
Power BI report and scheduled pipeline are not part of that verified run.

Two decisions have to be made before anything is deployed. Both change what you
build, so they come first.

For the classroom path that uses one workspace, manual notebook uploads and
screenshot evidence, follow
[docs/16-manual-upload-labs.md](docs/16-manual-upload-labs.md). This deployment
guide remains the production-style three-workspace reference.

## What you are deploying

| Component | What it is |
|---|---|
| Spark Environment | One published Environment, `env_forestops`, carrying 16 pinned libraries |
| Lakehouses | One per medallion layer: `lh_bronze`, `lh_silver`, `lh_gold` |
| Shortcuts | OneLake shortcuts so each layer can read the one before it |
| Notebooks | Six, numbered 00 to 05, in `notebooks/solutions/` |
| Pipeline | Optional, `pipelines/forest_classification_pipeline.json` |
| Semantic model | Optional, built by hand per `powerbi/semantic-model-guide.md` |

A full run takes about 12 minutes of compute once everything is in place. The
Environment publish is the slow part at roughly 6 minutes per workspace, and it
only has to happen once.

## Decision 1: outbound access protection

This is the one that will decide whether the workshop runs as written, so settle
it before booking a room.

Notebook 01 pulls Sentinel-2 imagery live from the Microsoft Planetary Computer.
That means two outbound calls from the Spark session:

- `planetarycomputer.microsoft.com` for the STAC catalogue search
- `*.blob.core.windows.net` for the signed Cloud Optimized GeoTIFF reads

Publishing the Environment needs a third: `pypi.org`, to resolve the pinned
library set.

[Workspace outbound access protection](https://learn.microsoft.com/fabric/security/workspace-outbound-access-protection-data-engineering)
blocks all three. When it is on, notebooks, Spark job definitions and lakehouses
in that workspace cannot reach public endpoints at all unless you have approved
a managed private endpoint for the destination.

### If outbound access protection is off

Nothing to do. This is the path the workshop is written for, and the path the
verification run used. Confirm it is actually off rather than assuming, because
the setting is per workspace and a workspace created from a locked-down template
may inherit it.

Check in the portal under **Workspace settings**, **Network Security**,
**Outbound access protection**. Note that toggling it takes up to 15 minutes to
take effect, so change it well before you need it.

### If outbound access protection must stay on

Two things break, and only one of them has a clean workaround.

The Environment publish breaks because Spark cannot install from PyPI. The
supported fix is to
[upload wheel files](https://learn.microsoft.com/fabric/security/workspace-outbound-access-protection-data-engineering#installing-libraries-securely-in-outbound-access-protected-workspaces)
to the Environment instead, or to host an internal PyPI mirror. Download the 16
packages in [environments/environment.yml](environments/environment.yml) plus
their transitive dependencies on a trusted machine, then upload the wheels. This
is tedious but it works, and it only has to be done once.

Notebook 01 does not have a clean workaround. Managed private endpoints target
Azure resources in your own subscription that support Private Link. The
Planetary Computer is a Microsoft-operated public service, so there is no
private endpoint to approve. Under outbound access protection, the live STAC
call cannot succeed.

The practical answer is to pre-stage the imagery: run notebook 01 once from
somewhere with internet access, land the scene catalogue and the raster window
into a lakehouse, and have the workshop start from that. Notebook 02 already
falls back to a re-load if its session cache is missing, so the seam is not
large. Budget half a day to prepare it and confirm the pre-staged scenes cover
the area of interest you intend to teach.

If your position is that production forest classification will never call a
public catalogue, say so early. It changes what Session 2 should teach, and the
honest version of that lesson is worth more than a demo that only works in a
sandbox.

## Decision 2: one workspace or three

The reference deployment separates medallion layers into their own workspaces, and
this repository is built that way, so the default should suit you. The reasons
are worth stating because they are the argument you will need if anyone pushes
back on the extra setup.

| | Three workspaces | One workspace |
|---|---|---|
| Permissions | Grant silver access without granting bronze | All or nothing |
| Blast radius | A mistake in silver cannot overwrite bronze | Anything can overwrite anything |
| Dependency direction | Visible in the shortcut graph | Lives in someone's head |
| Setup cost | Environment published three times, shortcuts wired | Publish once, no shortcuts |
| Capacity | All three can sit on one capacity | One |

The three-workspace layout is documented in
[docs/13-three-workspace-layout.md](docs/13-three-workspace-layout.md), with a
diagram, the shortcut table and the setup order.

Two things about it are easy to get wrong.

Notebook 05 reads `bronze_stand_register` directly from the gold workspace, to
build its stand dimension. The obvious wiring of silver-reads-bronze and
gold-reads-silver leaves that broken, and the failure surfaces two layers away
from its cause. Gold needs shortcuts to both upstream layers.

Every notebook uses unqualified `spark.table(...)` calls, which resolve against
whichever lakehouse is attached as the default. That is what makes the split
work, and it is also what breaks if a notebook is opened with the wrong default
lakehouse attached. The symptom is `TABLE_OR_VIEW_NOT_FOUND`, or worse, silently
reading the wrong layer.

### If you would rather use one workspace for the pilot

Reasonable for a first run, and it removes the shortcut step entirely. Create one
workspace, one lakehouse, and attach it to all six notebooks. The notebooks
need no code changes because nothing is qualified by workspace. You lose the
permissions boundary and the visible dependency graph, so if the pilot goes
anywhere, plan to split it before it carries real inventory.

Note that under outbound access protection, cross-workspace access has an extra
constraint: Spark must use fully qualified
`abfss://<workspace_id>@onelake.dfs.fabric.microsoft.com/<lakehouse_id>/...`
paths rather than display names. If you are running both the three-workspace
layout and outbound access protection, test the cross-layer reads early rather
than assuming shortcuts resolve.

## Before you start

| Requirement | Detail |
|---|---|
| Capacity | Any F SKU. The verification run used F64. F2 will work but the Environment publish is slower |
| Role | Workspace Admin, to create items and change network settings |
| Tenant setting | Users can create Fabric items. Often disabled by default |
| Region | Any. No region-specific dependencies |
| Local tooling | Only if you use the scripted path. Python 3.11 and the Azure CLI |

## Deployment path A: the portal

Recommended for the first run. Nothing to install, nothing to edit, and you see
each object as it is created.

1. Create three workspaces, one per layer, on the capacity you intend to use.
   Use your organization's naming convention; nothing in the notebooks depends on
   workspace names.
2. Create one lakehouse per workspace, named `lh_bronze`, `lh_silver` and
   `lh_gold`. These names do matter to the shortcut instructions below, though
   not to the notebook code.
3. In the bronze workspace, create an Environment named `env_forestops`. Under
   Public libraries, add the packages from
   [environments/environment.yml](environments/environment.yml). Publish and
   wait, roughly 6 minutes. Repeat in silver and gold. Environments are
   workspace-scoped, so all three need their own copy.
4. Upload the six notebooks from `notebooks/solutions/` into the workspace for
   their layer: 00 and 01 to bronze, 02 to silver, 03 through 05 to gold. Each
   notebook declares its layer near the top so you can check.
5. Bind each notebook by attaching `env_forestops` as the Environment and the
   layer's lakehouse as the default lakehouse. Both are in the notebook ribbon.
   See the diagram in
   [docs/12-spark-environment.md](docs/12-spark-environment.md).
6. Run notebooks 00 and 01 in bronze, in that order.
7. Create the shortcuts now that the bronze tables exist. Portal steps are in
   [docs/13-three-workspace-layout.md](docs/13-three-workspace-layout.md).
8. Run notebook 02 in silver, then create the remaining gold shortcuts.
9. Run notebooks 03, 04 and 05 in gold, in order.

The order matters in one specific way: a shortcut to a table that does not exist
yet is rejected, and Fabric reports it as `RequestBodyValidationFailed`, which
reads like a malformed request rather than a missing target. If you see that,
the upstream notebook has not run yet.

## Deployment path B: the scripts

Faster for repeat deployments, and how the verification run was done. It needs
the Azure CLI signed in to the target tenant.

All the workspace and lakehouse ids live in one file,
[scripts/env.json](scripts/env.json). That is the only file you edit:

```json
{
  "environmentName": "env_forestops",
  "layers": {
    "bronze": {
      "workspace": "your-bronze-workspace",
      "workspaceId": "<guid from the workspace URL>",
      "lakehouse": "lh_bronze",
      "lakehouseId": "<guid, known after the lakehouse exists>"
    }
  }
}
```

Workspace ids come from the workspace URL in the Fabric portal. Lakehouse ids do
not exist until the lakehouses do, so on a fresh tenant fill in the workspace
ids first, run the lakehouse step, then paste the lakehouse ids it prints back
into the same file.

```powershell
az login

# 1. fill in the three workspaceId values in scripts/env.json, then:
pwsh -File scripts/fabric_create_lakehouses.ps1

# 2. paste the printed lakehouse ids into scripts/env.json, then check it:
python scripts/check_env_config.py

python scripts/fabric_environment.py build bronze
python scripts/fabric_environment.py wait  bronze
# repeat for silver and gold

python scripts/fabric_run_pipeline.py all
```

`check_env_config.py` validates the shape before anything touches Fabric. A
malformed id otherwise surfaces later as a generic 400 or an empty listing,
which reads like a permissions problem rather than a typo.

`fabric_run_pipeline.py all` deploys each notebook to its layer, binds it to the
Environment and default lakehouse, runs it, and creates the table shortcuts
between layers at the right moments. It stops on the first failure and writes a
log to `scripts/.run-logs/`.

## Verify it actually worked

A notebook job reporting `Completed` only means nothing raised. Check the data.

```powershell
python scripts/fabric_probe.py gold scripts/probes/pipeline_data_verify.py verify.json
pwsh -File scripts/fabric_fetch_json.ps1 gold verify.json
```

That runs 23 checks: grain uniqueness, spectral indices inside their physical
range, referential integrity across the star schema, map centroids landing in
New Brunswick, and whether stands missing from the classification are explained
by the valid-pixel gate rather than lost silently.

Reference numbers from the verified run, for comparison:

| Check | Value |
|---|---|
| Stands in the register | 120 |
| Stands classified | 102 |
| Stands excluded for cloud | 18 |
| NDVI range | 0.413 to 0.622 |
| NDMI range | 0.124 to 0.308 |
| Fact rows | 102 |

Your numbers will differ, because the scenes available for your area and window
differ. The shapes and the relationships between the counts should match. More
detail in [notebooks/sample-outputs/README.md](notebooks/sample-outputs/README.md).

Eighteen unclassified stands is correct behaviour, not a bug. Those stands had
more than 40 percent of their canopy obscured in every available scene, and
notebook 03 excludes them rather than publishing a class derived from a handful
of pixels. If your run classifies all 120, check the valid-pixel gate is wired
in rather than celebrating.

## When something fails

Fabric reports every uncaught notebook exception as
`System_Cancelled_Session_Statements_Failed`, which names no cell, no line and
no exception type. Do not try to reason from it.

```powershell
python scripts/fabric_trace_notebook.py 01_bronze_stac_ingest bronze
pwsh -File scripts/fabric_fetch_json.ps1 bronze trace_01_bronze_stac_ingest.json
```

That runs the real notebook cell by cell inside a catching harness and returns
the first failing cell with its full traceback. Full method in
[docs/14-debugging-notebook-failures.md](docs/14-debugging-notebook-failures.md).

Common failures, in the order you are likely to meet them:

| Symptom | Cause |
|---|---|
| Environment publish fails | Outbound access protection is blocking PyPI. See Decision 1 |
| `ModuleNotFoundError` on the first import | Environment not attached, or session started before it was |
| `No '__dict__' attribute on 'Affine' instance` | `affine<3` pin missing from the Environment |
| Empty STAC result | Bounding box order, or a dropped minus sign on the longitude. New Brunswick is near -66 |
| `RequestBodyValidationFailed` on a shortcut | Target table does not exist yet. Run the upstream notebook |
| `TABLE_OR_VIEW_NOT_FOUND` | Wrong default lakehouse attached, or a missing cross-layer shortcut |
| Report is slow, no errors | Direct Lake silently fell back to DirectQuery. See the Power BI guide |

`python scripts/build_all.py --check` verifies both generated notebook content
and notebook structure. Cell IDs are deterministic, so a stale result means the
committed notebook bundle needs to be regenerated.

## One-workspace and three-workspace names

The participant guide intentionally uses `fabric-training`, `lh_woodlands` and
`env_forestops`. This guide uses `lh_bronze`, `lh_silver` and `lh_gold` across
three workspaces. The notebook bundle defaults to the participant topology;
facilitators using three workspaces should deploy through the supplied scripts,
which apply the target bindings for each layer.

## What to look at if you are reviewing rather than deploying

If the question is whether the content is right rather than whether it runs, the
decks are the fastest read. Both are committed, so no build is needed:

- `decks/out/session-1-environment-and-foundations.pptx`
- `decks/out/session-2-build-it-end-to-end.pptx`

Every slide carries speaker notes. Session 2 is the one with the technical
content and the AI conversation.

For the shape of the day, [docs/02-session-1-agenda.md](docs/02-session-1-agenda.md)
and [docs/03-session-2-agenda.md](docs/03-session-2-agenda.md). For the
assignment participants take away,
[docs/08-assignment.md](docs/08-assignment.md).

The exercise notebooks in `notebooks/student/` are the ones participants get,
with the interesting lines replaced by numbered instructions. The matching file
in `notebooks/solutions/` is the complete answer.
