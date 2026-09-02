---
title: Fabric App publishing option
description: When to publish the forest classification gold layer as a Fabric App on the Rayfin SDK instead of a Power BI report, with prerequisites, the snapshot pattern, and delivery notes
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: concept
keywords:
  - fabric apps
  - rayfin
  - direct lake
  - publishing
estimated_reading_time: 9
---

## Fabric App publishing option

Session 2 Step 4 publishes the gold layer as a Direct Lake semantic model and a
Power BI report. This page covers the alternative: a Fabric App, built on the
Rayfin SDK, presenting the same gold layer as a purpose-built page for one role.

The app lives in [apps/chief-forester](../apps/chief-forester/README.md) and is
fed by [notebook 06](../notebooks/solutions/06_publish_fabric_app_snapshot.ipynb).

## What Fabric Apps is

A Fabric item type, in preview, that runs a full-stack application as a managed
service inside a workspace. You define data models as TypeScript classes with
decorators, and Fabric generates the database schema, a GraphQL API, the
authentication, and static hosting for the frontend.

Three child services appear under the app in the portal: a SQL database in
Fabric holding your schema, a Fabric SSO authentication service, and static
content served from OneLake.

The CLI is called Rayfin. `npm create @microsoft/rayfin@latest` scaffolds a
project, `npx rayfin up` deploys it.

## Choosing between the three publishing paths

All three read the same gold tables. They differ in who they serve.

| | SQL analytics endpoint | Power BI report | Fabric App |
|---|---|---|---|
| Audience | Analysts writing their own queries | Anyone who wants to explore | One role with fixed questions |
| Interaction | Ad hoc T-SQL | Slice, filter, drill, export | Read the page, then act |
| Build effort | None, it already exists | An hour of clicks | It is a codebase |
| Change effort | None | Anyone with edit rights | Pull request, review, deploy |
| Data freshness | Live over Delta | Live via Direct Lake | Snapshot, published per run |
| Skills needed | T-SQL | Power BI modelling | TypeScript, React, npm |
| Preview risk | None | None | Preview, API surface can move |

The honest default is Power BI. Reach for the app only when at least two of
these are true:

- The audience is one role, and you can name the person.
- The questions are stable enough that a filter would go unused.
- The page has to say "do these things, in this order", not "here is the data".
- The output feeds an action, and you want the interface to make that action
  obvious rather than possible.

The Chief Forester dashboard qualifies on all four. A monthly review queue of
seven stands is a workflow, not an exploration.

## When not to use it

- The audience will ask for a new filter next month. That is a Power BI request.
- You need row-level security tied to an existing model. Direct Lake plus
  Power BI handles that; the app would need you to build it.
- Nobody on the team writes TypeScript. An app nobody can change is worse than
  a report anybody can.
- The workload is not enabled in your tenant and will not be soon.

## The snapshot pattern

A Fabric App has its own managed SQL database. It does not read the Lakehouse
directly, so publishing is a real step rather than a connection string.

```text
Lakehouse gold tables
        |
        |  notebook 06 reshapes into three flat payloads
        v
Files/app-snapshot/<run_id>/*.json          durable artefact, always written
        |
        |  batched GraphQL create mutations
        v
Fabric App database: StandSnapshot, PeriodSummary, ClassBreakdown
```

Three consequences worth being clear about with a customer.

Data is as fresh as the last publish, not live. For a monthly forestry cadence
that is irrelevant. For an operations console it would be disqualifying.

The app never calculates. Aggregates are computed in gold and copied in. If the
dashboard did its own arithmetic it would become a second source of truth, and
the first time it disagreed with the Power BI report nobody could say which was
right.

The snapshot is small on purpose. 120 stands and 7 class rows removes every
question about capacity, concurrency and query cost. At ten thousand stands you
would publish the review queue and the aggregates, not every stand.

## Prerequisites

| Requirement | Detail |
|---|---|
| Tenant setting | An admin enables **Fabric Apps (preview)** in the admin portal |
| Capacity | The workspace needs Fabric capacity; app services consume capacity units |
| Region | Not available in every region yet, check regional availability first |
| Workspace role | Contributor, Member or Admin to deploy |
| Local tooling | Node.js, npm, and Docker for the local development stack |

Check the region and the tenant setting before promising this in a workshop.
Both are outside the room's control and both take days to resolve.

## Deploying it

```bash
cd apps/chief-forester
npm install
cp rayfin/.env.example rayfin/.env

npx rayfin up --dry-run     # show what would change
npx rayfin up               # create or update the app and its child services
npx rayfin up status        # confirm
```

Schema changes go through `npx rayfin up db apply`. The CLI refuses destructive
operations without `--force`, and `--force` drops columns, so read the list.

Then run notebook 06 with `FABRIC_APP_URL` set to the backend URL the CLI
printed.

## Permissions

Workspace roles do not override item permissions. Give the Chief Forester
**Run and interact** on the app item. That allows opening the app and calling
its APIs, and nothing else.

Reserve **Edit** for whoever deploys. Anyone with Edit can change the schema and
the running application.

## Security notes

Static content is served from a public URL. Nothing sensitive belongs in the
frontend bundle, in `rayfin/.env`, or in a committed environment file. The
publishable key is designed to be visible; a connection string is not.

Once deployed, authentication is Fabric SSO only. Email and password exists for
local development and should stay there.

Schema lives in code. Editing the child SQL database in the portal puts the
codebase and the database out of step, and the next deploy fails.

## Delivery notes for facilitators

Treat this as an optional extension, not a required block. It adds roughly 25
minutes if the tenant is ready and consumes the whole afternoon if it is not.

Two ways to run it:

Demo only, 10 minutes. You deploy it beforehand, show the page, walk the room
through the three-way comparison table above, and move on. This is the right
call for a room of data engineers who will never write React.

Hands-on extension, 25 minutes plus. Participants run it locally with
`npx rayfin dev` and seed it from notebook 06. Only attempt this if Docker is
installed and working on every machine, which is worth verifying at pre-flight
rather than discovering at 3pm.

The teaching point survives either way, and it is not about Rayfin: publishing
is a design decision with an audience attached, and the same gold layer should
be able to serve a self-service report, an ad hoc query and a purpose-built page
without being reshaped for any of them. If your gold layer can only feed one of
the three, it is not really a gold layer.

## Preview caveat

Fabric Apps is in preview. Entity decorators, CLI commands and generated API
names can change between releases. Notebook 06 discovers the GraphQL mutation
names by introspecting the deployed app rather than hard-coding them, which is
the pattern to copy: ask the API what it offers instead of assuming.
