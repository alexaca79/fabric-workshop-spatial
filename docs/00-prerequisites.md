---
title: Prerequisites
description: Access, licences, tooling and environment checks to complete before Session 1 of the forest classification workshop
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: how-to
keywords:
  - prerequisites
  - fabric capacity
  - access checks
estimated_reading_time: 7
---

## Prerequisites

Complete every item below before Session 1. Budget 30 minutes. Access requests
that need someone else to approve them are the main reason a workshop starts
slowly, so raise those first and do the rest while you wait.

## 1. Accounts and licences

| Item                        | What you need                                                     | How to check                                                             |
|-----------------------------|-------------------------------------------------------------------|--------------------------------------------------------------------------|
| Microsoft Entra account     | Your JDI work account                                             | Sign in at [app.fabric.microsoft.com](https://app.fabric.microsoft.com)  |
| Fabric capacity             | Membership of a workspace on an F-SKU or trial capacity           | Workspace settings shows a Licence mode other than Pro                   |
| Power BI                    | Pro or Premium Per User, or a Fabric capacity that covers viewing | You can create a report in the workshop workspace                        |
| GitHub Copilot              | An active seat                                                    | The Copilot icon in VS Code is not greyed out                            |
| Microsoft Foundry           | Access to a project with a chat model deployed                    | The project appears in [ai.azure.com](https://ai.azure.com)              |

If Foundry access is missing, you can still complete every block except the AI
enrichment exercise, and notebook 04 has an offline stub that produces the same
table shape without calling a model.

## 2. Fabric workspace

Each participant gets their own workspace so that a mistake in one workspace
cannot break anyone else's run.

1. In Fabric, select Workspaces, then New workspace.
2. Name it `ws-woodlands-<yourname>`.
3. Under Advanced, set the licence mode to the capacity the facilitator names.
4. Confirm the workspace opens and you can create items in it.

Facilitators: pre-create these workspaces where possible. Self-service creation
is often blocked by tenant settings, and discovering that at 09:05 costs the
room twenty minutes.

## 3. Lakehouse

Create one Lakehouse in your workspace named `lh_woodlands`. Leave schemas
enabled if your tenant offers the option. Notebook 00 verifies the name and
fails fast with a clear message if it differs, because every later notebook
resolves paths from it.

## 4. Spark environment

Two options, in order of preference.

Attach the shared environment. If the facilitator has published a Fabric
Environment named `env-woodlands-geo`, attach it to your notebooks. It carries
the libraries in `requirements-fabric.txt` and removes the install wait.

Install per session. If no shared environment exists, the first cell of each
notebook runs a `%pip install` block. Expect two to four minutes on the first
run of each session, and note that the install is lost when the session
recycles.

## 5. Local tooling

You only need local tooling to browse this repository and to use Copilot while
drafting code. The pipeline itself runs entirely in Fabric.

```powershell
git clone <repository-url> "JDI - Training"
cd "JDI - Training"
code .
```

Install the VS Code extensions for Python, Jupyter and GitHub Copilot. The
Fabric extension is useful but optional.

## 6. Network and data access

The notebooks reach out to `planetarycomputer.microsoft.com` for the STAC API
and to `*.blob.core.windows.net` for the signed asset reads. Confirm both
resolve from your Fabric session by running the pre-flight cell in notebook 00.
If your tenant blocks outbound access from Spark, tell the facilitator before
the session so the cached-scene fallback can be staged.

## 7. Area of interest

The default area of interest is a block of managed forest in central New
Brunswick, defined in `src/forestops/config.py` as a bounding box in WGS84 with
a target projection of EPSG:2953, the New Brunswick Stereographic Double
Projection. You can change the bounding box to your own operating area at any
point after Session 1, and the homework asks you to do exactly that.

## Pre-flight self-check

Run this in a Fabric notebook cell attached to `lh_woodlands`. It should print
a line per check with no failures.

```python
%run /repo-or-paste/preflight
```

If you cannot run it, paste the contents of
[01-preflight-check.md](01-preflight-check.md) into a cell instead. The script
is intentionally dependency-free so that it runs before any install has
happened.

## What to bring

A laptop, the workspace name you created, and one real question about your own
data. The last item matters more than it sounds: the final block of Session 2
is where people connect the exercise to their own operating area, and the
question you bring is what makes that connection stick.

## References

If any step above was unfamiliar, these are the authoritative versions:

- [Create a workspace](https://learn.microsoft.com/fabric/fundamentals/create-workspaces)
- [Roles in workspaces in Microsoft Fabric](https://learn.microsoft.com/fabric/fundamentals/roles-workspaces), for what Viewer, Contributor, Member and Admin actually allow
- [What is a lakehouse in Microsoft Fabric?](https://learn.microsoft.com/fabric/data-engineering/lakehouse-overview)
- [Create, configure, and use an environment in Fabric](https://learn.microsoft.com/fabric/data-engineering/create-and-use-environment), the shared-environment option in section 4
- [Workspace outbound access protection for data engineering workloads](https://learn.microsoft.com/fabric/security/workspace-outbound-access-protection-data-engineering), which decides whether the Planetary Computer calls in section 6 can succeed at all
- [Get started with Microsoft Fabric](https://learn.microsoft.com/training/paths/get-started-fabric/) as a pre-read if this is your first Fabric workspace

The full take-home reading plan is in
[docs/15-resources-and-learning-paths.md](15-resources-and-learning-paths.md).
