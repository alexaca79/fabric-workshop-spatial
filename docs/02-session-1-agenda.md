---
title: Session 1 agenda - environment and data foundations
description: Four-hour running order for Session 1 covering pre-flight checks, product ownership framing, the tool tour, tool chain selection, Fabric and OneLake, and the first hands-on Lakehouse exercise
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: reference
keywords:
  - agenda
  - session 1
  - fabric
  - onelake
estimated_reading_time: 9
---

## Session 1 agenda: environment and data foundations

Four hours. The goal by the end of the session is that every participant has a
Lakehouse containing a reprojected Woodlands dataset written as a Delta table,
and can explain why the medallion layers exist rather than reciting that they do.

| Time  | Block                                                                              | Min |
|-------|------------------------------------------------------------------------------------|-----|
| 0:00  | Pre-flight, environment and access check, with a fallback for anyone who is blocked | 20  |
| 0:20  | Owning an analytics product, what we are and are not building                        | 20  |
| 0:40  | Your environment tool by tool                                                        | 45  |
| 1:25  | Choosing a tool chain, three problem patterns and how to pick between them           | 30  |
| 1:55  | Break                                                                                | 15  |
| 2:10  | Fabric and OneLake, workspaces, Lakehouse, shortcuts, SQL analytics endpoint         | 40  |
| 2:50  | Hands-on, land a Woodlands dataset, reproject it, write a Delta table                | 50  |
| 3:40  | Wrap and homework brief                                                              | 20  |
|       | Session total                                                                        | 240 |

## 0:00 Pre-flight (20 min)

Run [01-preflight-check.md](01-preflight-check.md) as the first activity, before
any introductions. Everyone runs it at once, the facilitator walks the room, and
anyone with a `FATAL` line is moved to a fallback tier within the first ten
minutes.

Deliverable: a green pre-flight for every participant, or a named fallback.

Facilitator note: resist the urge to debug an individual laptop in front of
thirty people. Move them to the shared workspace and return to it at the break.

## 0:20 Owning an analytics product (20 min)

The framing block. What separates a pipeline someone maintains from a notebook
someone once ran.

Topics:

- Who the user is. In this workshop it is a Woodlands planner deciding where to
  send a crew next season, not a data scientist.
- What "done" means. A number on a map that a forester will act on, with a date
  attached and a known refresh cadence.
- What we are not building today: a research-grade classifier, a replacement for
  field cruising, or anything that makes a silvicultural decision on its own.
- The contract each layer signs. Bronze promises fidelity, silver promises
  comparability, gold promises meaning.

Deliverable: the room can state the user, the decision, and the refresh cadence
for the pipeline they are about to build.

## 0:40 Your environment tool by tool (45 min)

A guided tour with one live action per tool so that nobody watches a slide about
a product they have not touched.

| Tool                | Time  | Live action                                                            |
|---------------------|-------|------------------------------------------------------------------------|
| Microsoft Fabric    | 12 min| Create a workspace, create `lh_woodlands`, look at Files and Tables     |
| Power BI            | 8 min | Open the SQL analytics endpoint, run one `SELECT`, see the same data    |
| Planetary Computer  | 10 min| Search Sentinel-2 for your area in the Explorer, read one STAC item     |
| GitHub Copilot      | 10 min| Ask it for a reprojection snippet, then find the mistake in the answer  |
| Microsoft Foundry   | 5 min | Open a project, look at a deployed model, note the endpoint and version |

The Copilot segment is deliberately adversarial. Ask for "reproject a GeoDataFrame
to New Brunswick coordinates" and inspect what comes back. A confident answer
using `EPSG:4326` or an unqualified `to_crs(2953)` on data with no CRS set is the
teaching moment, and it lands harder when the room finds it rather than the slide.

## 1:25 Choosing a tool chain (30 min)

Three problem patterns, and the honest criteria for picking between them.

| Pattern                                            | Reach for                                  | Do not reach for                                     |
|----------------------------------------------------|--------------------------------------------|------------------------------------------------------|
| Tabular data, known schema, scheduled refresh       | Dataflows Gen2 or a Warehouse plus T-SQL   | A Spark notebook, because you will maintain it forever |
| Raster or vector geospatial, per-scene processing   | Spark notebook plus GeoPandas and rioxarray| Dataflows, which have no raster story                 |
| Unstructured text, images, judgement calls          | Foundry model behind a notebook or function| A classifier you have to label data for this quarter  |

The exercise: three one-paragraph problem statements from Woodlands operations,
handed out on cards. Table groups pick a chain and defend it in two minutes.
There is a defensible answer for each, and at least one card is deliberately a
trap where the obvious tool is the wrong one.

Deliverable: a written decision rule each participant can apply to their next
request without asking anyone.

## 1:55 Break (15 min)

Facilitators use this window to unblock the pre-flight failures parked at 0:00.

## 2:10 Fabric and OneLake (40 min)

The conceptual core of the day.

- Workspace as the unit of access, capacity and lifecycle.
- OneLake as one storage account for the tenant, and why that removes most of the
  copying you do today.
- Lakehouse: `Files/` for anything, `Tables/` for Delta, and the fact that a
  table is a folder with a transaction log.
- Shortcuts: reference data in place, across workspaces and clouds, with no copy
  and no second refresh schedule to maintain.
- SQL analytics endpoint: the same Delta files, read through T-SQL, with no
  extra storage and no separate load.
- Where the medallion layers live and why bronze is never overwritten.

Live demo: create a shortcut from `lh_woodlands` to a shared reference Lakehouse
holding the stand register, then query it through the SQL endpoint without
copying a byte. This is the moment the OneLake idea usually lands.

## 2:50 Hands-on: land, reproject, write (50 min)

Notebook: `notebooks/student/00_setup_lakehouse_and_config_STUDENT.ipynb`

Steps:

1. Resolve the Lakehouse paths and print the resolved configuration.
2. Load or generate the Woodlands stand register as a GeoDataFrame.
3. Inspect the CRS, and discover that it is not what you assumed.
4. Reproject to EPSG:2953 and recompute area in hectares.
5. Write bronze geometry as WKB into a Delta table.
6. Read it back through Spark and validate the row count and the CRS metadata.

Checkpoint at 3:25: everyone runs the validation cell. It prints a single
`PASS` or `FAIL` per assertion. Anyone with a `FAIL` gets the solution notebook
and moves on rather than falling behind.

Common trip hazards, in the order they usually appear:

- Writing a `geometry` column straight to Delta, which fails because Spark has
  no geometry type. Serialise to WKB and keep the EPSG code in a column.
- Calling `.to_crs()` on a frame whose CRS is `None`, which raises rather than
  guessing. Set it explicitly with `.set_crs()` first.
- Computing area before reprojecting, which gives square degrees and a number
  that looks plausible until someone checks it against a cruise sheet.

## 3:40 Wrap and homework brief (20 min)

- Recap: the three layers, the one storage account, and the decision rule.
- Preview Session 2 as five steps: get it, analyse it, add AI where it earns its
  place, publish it, make it repeatable.
- Homework brief: [07-homework.md](07-homework.md), roughly 45 minutes.
- Collect one question per person for the Session 2 opener.

## Materials checklist

| Item                                   | Where                                              |
|----------------------------------------|-----------------------------------------------------|
| Slide deck                             | `decks/out/session-1-environment-and-foundations.pptx` |
| Pre-flight script                      | `docs/01-preflight-check.md`                        |
| Student notebook 00                    | `notebooks/student/`                                |
| Solution notebook 00                   | `notebooks/solutions/`                              |
| Tool chain exercise cards              | `docs/06-toolchain-decision-guide.md`               |
| Shared fallback workspace, pre-run     | `ws-woodlands-shared`                               |
