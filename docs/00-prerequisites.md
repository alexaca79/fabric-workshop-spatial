---
title: Prerequisites
description: Access, licences, tooling and environment checks to complete before Session 1 of the forest classification workshop
author: Workshop Delivery Team
ms.date: 2026-09-17
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
| Microsoft Entra account     | Your approved Contoso workshop account                           | Sign in at [app.fabric.microsoft.com](https://app.fabric.microsoft.com)  |
| Fabric capacity             | `jdi-training-manual` on existing `rayfintestenv` F64              | Confirm the assigned capacity is Active                                  |
| Maps and Fabric Data Agent  | Permission to author items and use approved tenant features       | Both appear in New item and the agent can query the learner lakehouse    |
| Power BI                    | Optional, for the separate report extension                      | Not needed for the native Map or Data Agent lesson                       |
| GitHub Copilot              | Optional assistance with Python TODO exercises                   | Not needed to execute the browser-based lab                              |
| Microsoft Foundry           | Optional, for the live-model extension                           | Required Lab 04 uses offline stubs                                       |

All six required labs can be completed without Foundry access. Lab 04 uses an
offline stub with explicit status, not a live model response. The later native
Fabric Data Agent is a separate live service with its own tenant prerequisites.

## 2. Fabric workspace

The manual lab uses one dedicated workspace with a separate lakehouse for each
learner or pair. Coordinate Spark starts because the capacity is shared.

1. Open `jdi-training-manual`, prepared by the facilitator in Contoso.
2. Confirm Contributor or higher access for notebook imports and item creation.
3. Confirm the existing `rayfintestenv` F64 is assigned and active.
4. Follow [the manual guide](16-manual-upload-labs.md) to create your notebook
  folder. Do not recreate the workspace or use the reference `jdi-training` items.

Facilitators: pre-create these workspaces where possible. Self-service creation
is often blocked by tenant settings, and discovering that at 09:05 costs the
room twenty minutes.

## 3. Lakehouse

Upload all six student notebooks first. Then manually create
`lh_woodlands_<your-name>` with Lakehouse schemas enabled, following the manual
guide. Attach your own Lakehouse as the default for every notebook, not its
SQL endpoint or another learner's lakehouse. Keep the table names unchanged.

## 4. Spark environment

Attach the published `env_forestops` from the training workspace. It supplies
the pinned libraries from [environment.yml](../environments/environment.yml).
If missing, the facilitator follows
[manual portal setup](12-spark-environment.md#manual-portal-setup).

Do not run `%pip install` in these notebooks. Ad hoc installation can replace
Fabric runtime packages. Check the attachment and restart the session instead.

## 5. Local tooling

No local installation is required for the manual path. Extract the supplied
bundle and upload its notebooks through Fabric. The following setup is optional
for browsing the repository and using Copilot.

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

After importing the notebooks and creating your lakehouse, select the
published `env_forestops` and pin your lakehouse in Lab 00. Run its supplied
Environment check. Missing packages mean you must check the attachment and
restart the session, not paste an install command. Use the manual guide's
checkpoints to validate each subsequent lab.

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
