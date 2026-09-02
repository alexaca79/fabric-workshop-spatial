---
title: Chief Forester dashboard
description: Fabric App built on the Rayfin SDK that presents the gold layer of the forest classification pipeline as a single-page dashboard for a Chief Forester
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: how-to
keywords:
  - fabric apps
  - rayfin
  - dashboard
estimated_reading_time: 8
---

## Chief Forester dashboard

A Fabric App, built on the Rayfin SDK, that answers one question for one person:
what is the state of the licence area this month, and which stands need someone
to go and look at them.

This is the third publishing option in the workshop, alongside the Power BI
report and the SQL analytics endpoint. Pick it when the audience is a single
role with a fixed set of questions. See
[docs/11-fabric-app-option.md](../../docs/11-fabric-app-option.md) for the
decision.

## What the page shows

```text
┌──────────────────────────────────────────────────────────────────────┐
│  Woodlands · Chief Forester        central-nb-block-a · Jun to Aug    │
├──────────┬──────────┬──────────────┬──────────────┬──────────────────┤
│ Area     │ Usable   │ Harvested    │ Needs a look │ Last refreshed   │
│ 4,120 ha │ 86%      │ 212 ha       │ 7 stands     │ 2 days ago       │
├──────────┴──────────┴──────────────┴──────────────┼──────────────────┤
│  Area by forest class                             │  Stand detail    │
│  ████████████░░░░░░░░▒▒▒▒▒░░░                     │  CEN-00042       │
│  Softwood 2,140 ha · Hardwood 980 ha · ...        │  Two-sentence    │
│                                                   │  narrative, the  │
│  Review queue                                     │  numbers behind  │
│  CEN-00042  LB-C  Softwood  Disturbance  high     │  it, and a map   │
│  CEN-00107  LB-A  Mixedwood Moisture     moderate │  link            │
└───────────────────────────────────────────────────┴──────────────────┘
```

Five cards, one bar, one queue, one detail panel. Nothing else. A Chief
Forester who opens this on a Monday should be able to act inside a minute, and
every additional control makes that less likely.

## Design decisions worth knowing

The app never calculates anything. Every number is published by the pipeline
into the app's own database. If the dashboard computed its own class totals it
would become a second source of truth, and the first time it disagreed with the
Power BI report nobody would know which one was wrong.

Usable imagery is on the front page, not in a tooltip. A month where a third of
the stands sat under cloud is a different month, and the reader has to know
that without asking.

Suppressed narratives display a message rather than a blank. A blank reads as a
bug; an explicit message reads as a system that knows what it does not know.

The review queue is sorted by severity then area, and it is the only actionable
surface. Everything above it is context for deciding whether to trust it.

## Architecture

```text
Lakehouse (lh_woodlands)                Fabric App (Rayfin)
  gold_stand_facts        notebook 06     ┌────────────────────────┐
  gold_dim_stand      ───────────────▶    │ SQL database in Fabric │
  gold_stand_narrative   publishes a      │  StandSnapshot         │
  gold_pipeline_run_summary  snapshot     │  PeriodSummary         │
                                          │  ClassBreakdown        │
                                          ├────────────────────────┤
                                          │ GraphQL  /api/graphql  │
                                          │ Auth     /auth (SSO)   │
                                          │ Static   React + Vite  │
                                          └────────────────────────┘
```

The app has its own managed SQL database. It does not read the Lakehouse
directly, so a publish step is required. That step is notebook 06,
`06_publish_fabric_app_snapshot`, which runs at the end of the pipeline.

Snapshot rather than live view is the right trade here. The data changes
monthly, the audience is a handful of people, and a copy of 120 rows removes
every question about capacity, concurrency and query cost.

## Files

| Path | Contents |
|------|----------|
| `rayfin/rayfin.yml` | Service configuration: auth, data, static hosting |
| `rayfin/data/*.ts` | Entity definitions. These generate the database schema and the API |
| `rayfin/data/schema.ts` | Entity registry. A new entity missing from here is silently absent from the API |
| `src/App.tsx` | Page composition and the two queries that load it |
| `src/client.ts` | `RayfinClient` setup and the Fabric SSO sign-in path |
| `src/components/` | KPI row, class bar, review queue, stand detail |
| `src/styles.css` | All styling. No component library, no chart library |

## Run it locally

Docker is required: the CLI runs the backend services locally.

```bash
cd apps/chief-forester
npm install
cp rayfin/.env.example rayfin/.env

npx rayfin dev          # backend services plus the Vite dev server
```

Open `http://localhost:5173`. Local sign-in uses email and password because the
Fabric SSO path needs a deployed item. Seed the local database by running
notebook 06 with `APP_TARGET = "local"`.

## Deploy to Fabric

```bash
npx rayfin up --dry-run   # show what would change
npx rayfin up             # create or update the app and its child services
npx rayfin up status      # confirm, or add --json for a machine-readable answer
```

After a schema change in `rayfin/data/`, apply it on its own:

```bash
npx rayfin up db apply
```

The CLI refuses destructive schema operations unless you pass `--force`. Read
the listed operations before you do, because `--force` drops columns.

On success the CLI prints the hosted app URL and the Fabric portal link. Give
the Chief Forester **Run and interact** permission on the item; that is enough
to open the app and nothing more.

## Prerequisites and constraints

| Requirement | Detail |
|-------------|--------|
| Tenant setting | A Fabric admin enables **Fabric Apps (preview)** in the admin portal |
| Capacity | The workspace needs Fabric capacity. App services consume capacity units |
| Region | Fabric Apps is not available in every region yet |
| Permissions | Contributor, Member or Admin on the workspace to deploy |
| Node.js | Node and npm installed locally, plus Docker for the local stack |
| Preview | Fabric Apps is in preview. Treat the API surface as movable |

## Security notes

Static content is served from a public URL, so nothing sensitive belongs in the
frontend bundle or in `rayfin/.env`. The publishable key is designed to be
visible; a connection string is not.

Access is Fabric SSO only once deployed. Email and password exists for local
development, which is why `rayfin.yml` keeps it enabled here and why you should
turn it off for anything a real Chief Forester logs into.

Schema changes belong in `rayfin/data/`. Editing the child SQL database in the
portal puts the code and the database out of step and breaks the next deploy.
