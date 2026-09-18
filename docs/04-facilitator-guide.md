---
title: Facilitator guide
description: Room setup, timing discipline, fallback tiers, rehearsed failure points and delivery notes for running the two-session forest classification workshop
author: Workshop Delivery Team
ms.date: 2026-09-17
ms.topic: how-to
keywords:
  - facilitation
  - delivery
  - workshop operations
estimated_reading_time: 11
---

## Facilitator guide

Written for the person running the room. Assumes two facilitators for up to
twenty-four participants: one presenting, one floating.

For the browser-only Contoso delivery, use
[the manual walkthrough](16-manual-upload-labs.md) as the controlling checklist:
`jdi-training-manual`, existing `rayfintestenv` F64, one lakehouse per learner,
one published `env_forestops`, then native Maps and Data Agent. Its workspace
preparation and [Environment setup](12-spark-environment.md#manual-portal-setup)
replace the older topology and Foundry/report preparation below. Preserve the
reference workspace, stagger Spark starts, and do not regenerate manual-release
notebooks or weaken quality/network gates to unblock a lesson.

## Two weeks out

| Task                                                                     | Owner       |
|--------------------------------------------------------------------------|-------------|
| Confirm Fabric capacity and that it is not shared with a production load  | Facilitator |
| Pre-create `ws-woodlands-<name>` workspaces if self-service is blocked    | Facilitator |
| Publish the `env-woodlands-geo` Fabric Environment                        | Facilitator |
| Confirm Foundry project access and note the endpoint and deployment name  | Facilitator |
| Send [00-prerequisites.md](00-prerequisites.md) to participants           | Facilitator |
| Confirm outbound access to Planetary Computer from a Spark session        | Facilitator |

The outbound access check is the one people skip and the one that ruins a
session. Run the pre-flight script yourself from a Fabric notebook on the target
capacity, not from your laptop.

## Two days out

- Run every solution notebook end to end on the target capacity. Record the
  wall clock time of each. If notebook 01 takes eleven minutes, the room needs
  to know that before they sit through it.
- Stage `ws-woodlands-shared` with all solution notebooks already executed and
  the gold tables populated. This is the fallback everyone drops into.
- Cache one clear-sky scene window to `Files/bronze/scenes/` in the shared
  workspace, so that a cloudy live search does not stall the session.
- Rebuild the decks: `python scripts/build_all.py`.

## Room setup

- Two screens if available. Slides on one, live notebook on the other. Never
  alt-tab between them; the room loses the thread every time.
- Editor font at a size you can read from the back row. 16pt minimum.
- A visible timer. The agenda is tight and the hands-on blocks absorb overrun
  from every block before them.
- The floating facilitator carries the fallback checklist and does not present.

## Timing discipline

The two blocks that reliably overrun:

| Block                              | Why it overruns                                       | Recovery                                                                      |
|------------------------------------|-------------------------------------------------------|-------------------------------------------------------------------------------|
| Session 1, 0:40 tool tour           | People want to explore each product                    | Set a hard timer per tool. Park exploration for the break.                      |
| Session 2, 1:00 Copilot analysis    | Copilot answers vary, and debate is genuinely useful   | Cap the discussion at three assumptions, then move to the solution notebook.    |

The checkpoint mechanic is what protects the schedule. At each checkpoint,
anyone who is not green opens the solution notebook, runs it, and continues.
State this out loud at the start of each session so that using the solution
feels like the designed path rather than giving up.

## Fallback tiers

Apply in order. Move people fast; do not debug in front of the room.

1. Shared workspace `ws-woodlands-shared`, write access, solutions pre-run.
2. Pair programming, two people and one keyboard, blocked person drives.
3. Read-only, working against `notebooks/sample-outputs/` locally, rejoining at
   the next break.

Track who is on which tier. A participant parked on tier three at 0:20 of
Session 1 who is still there at 3:40 has had a bad day, and that is recoverable
only if you noticed.

## Rehearsed failure points

Things that will go wrong. Rehearse the recovery so the room sees competence
rather than panic.

| Failure                                                   | Live recovery                                                                                       |
|-----------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| STAC search returns zero items                             | Widen the date window and raise the cloud threshold on screen, and narrate why                       |
| A signed asset href returns 403 mid-demo                   | Re-sign and re-run. Explain token expiry as a design constraint, not an outage                       |
| Spark session takes six minutes to start                   | Switch to the pre-warmed session you started before the block. Always start one                       |
| Foundry deployment throttles                               | Switch notebook 04 to `USE_OFFLINE_STUB = True` and continue                                          |
| Direct Lake silently falls back to DirectQuery             | This is a teaching moment, not a failure. Show the fallback reason and fix the model                  |
| A participant's reprojection produces zero-area polygons   | Their geometry was in metres already and got double-projected. Show `gdf.crs` before and after         |

## Delivery notes per block

### Session 1, owning an analytics product

Keep this concrete. The abstraction only lands if it is attached to a named
person making a named decision. Use a real planner if one is in the room.

### Session 1, the Copilot segment

The point is not that Copilot is unreliable. The point is that it optimises for
a plausible answer to the question you asked, and geospatial code is full of
questions people ask imprecisely. Run the same prompt twice and show that the
answers differ. Then show the same prompt with the CRS and the scale factor
stated, and show that it now gets it right. The lesson is about the prompt, not
the tool.

### Session 1, Fabric and OneLake

The shortcut demo is the highest-value five minutes in Session 1. Do it live,
slowly, and query through the SQL analytics endpoint afterwards so the room sees
the same bytes through two engines.

### Session 2, where AI is quietly wrong

Do the three demonstrations in the order written. The third one, where the model
invents an opinion about missing data, is the one people remember, because it
looks exactly like a correct answer.

Say the uncomfortable part out loud: the failure mode is not a wrong answer, it
is a confident answer that nobody checks because it reads well. That is why the
notebook writes a `validation_status` column rather than trusting the response.

### Session 2, publishing

Budget more time than feels necessary for the semantic model. First-time Direct
Lake model creation involves several clicks in places people have not looked
before, and a room of twenty-four moves at the speed of the slowest three.

## Post-session

- Export the workspace list and confirm nothing is left on a shared capacity
  that will be charged after the event.
- Send the assignment brief and the office hours calendar invite the same day.
- Collect the one thing each participant would change. Fold it into the next
  delivery rather than into a document nobody reads.

## What good looks like at the end

Every participant can point at a Power BI map of their own operating area,
explain which layer each number came from, name one thing the AI enrichment does
well and one thing it must not be trusted with, and describe what they would
change to run it on the real stand register.
