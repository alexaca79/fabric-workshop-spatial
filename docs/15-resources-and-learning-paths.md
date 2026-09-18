---
title: Resources and learning paths
description: The take-home pack from the workshop, a sequenced 90-day plan, and a grounded reference shelf of Microsoft Learn documentation organised by what you will actually be doing
author: Workshop Delivery Team
ms.date: 2026-09-03
ms.topic: reference
keywords:
  - microsoft fabric
  - learning path
  - certification
  - reference
  - onelake
estimated_reading_time: 12
---

## Resources and learning paths

Everything below is either in this repository or on Microsoft Learn. It is
ordered by when you are likely to need it rather than by product area, because
the failure mode after a workshop is not a shortage of material. It is having
sixty tabs open and no idea which one matters on Monday.

Every external link points at official documentation. Where this repository
disagrees with Learn, Learn is right and the difference is usually a preview
feature that moved.

## What you take home

| Artifact | Where | Why it matters later |
|---|---|---|
| Six notebooks, solutions and exercises | `notebooks/` | The exercise version has numbered blanks; the solution is the answer key |
| Pinned library set | [environments/environment.yml](../environments/environment.yml) | Each pin has a comment naming the failure it prevents |
| Deployment runbook | [DEPLOY.md](../DEPLOY.md) | The two decisions and the portal or scripted path |
| Debugging method | [docs/14-debugging-notebook-failures.md](14-debugging-notebook-failures.md) | How to recover a traceback Fabric will not show you |
| Both decks with speaker notes | `decks/out/` | Every slide carries the note, so you can re-teach this |
| Sample outputs | [notebooks/sample-outputs/README.md](../notebooks/sample-outputs/README.md) | Expected shapes and value ranges to compare your run against |
| Power BI build guide | [powerbi/semantic-model-guide.md](../powerbi/semantic-model-guide.md) | Real DAX against the verified schema |

The repository is the reference implementation. It has been run end to end
against a live capacity, and the four bugs that run exposed are documented with
their fixes. That is the part you cannot get from a tutorial.

## First week: consolidate before you extend

The goal is to reproduce, not to improve. If you change the area of interest and
the library versions and the classifier in the same week, you will not know which
change broke it.

1. Re-run the pipeline unchanged against your own workspace, following
   [DEPLOY.md](../DEPLOY.md). Confirm your numbers have the same shape as
   [notebooks/sample-outputs/README.md](../notebooks/sample-outputs/README.md).
2. Change one thing: the bounding box, to your own operating area. Expect the
   scene count and cloud cover to change and the stand count to change. Nothing
   else should.
3. Read [Understand medallion architecture for Fabric with OneLake](https://learn.microsoft.com/fabric/onelake/onelake-medallion-lakehouse-architecture)
   and compare its deployment models against what you built.

Background reading for the week, in order:

- [What is a lakehouse in Microsoft Fabric?](https://learn.microsoft.com/fabric/data-engineering/lakehouse-overview) for the item model
- [Lakehouse and Delta Lake tables](https://learn.microsoft.com/fabric/data-engineering/lakehouse-and-delta-tables) for why the Tables area behaves the way it does
- [OneLake shortcuts](https://learn.microsoft.com/fabric/onelake/onelake-shortcuts) for the mechanism behind the three-workspace layout
- [Get started with Microsoft Fabric](https://learn.microsoft.com/training/paths/get-started-fabric/) if any of the above felt like new vocabulary

## Days 8 to 30: make it yours

This is where the assignment in [docs/08-assignment.md](08-assignment.md) lives.
Pick the track that matches your job.

### If you are building the pipeline

- [Implement a Lakehouse with Microsoft Fabric](https://learn.microsoft.com/training/paths/implement-lakehouse-microsoft-fabric/), the closest training path to what you just did
- [Lakehouse end-to-end scenario](https://learn.microsoft.com/fabric/data-engineering/tutorial-lakehouse-introduction), a second worked example with different data
- [Create, configure, and use an environment in Fabric](https://learn.microsoft.com/fabric/data-engineering/create-and-use-environment) before you add a single library
- [Manage Apache Spark libraries in Microsoft Fabric](https://learn.microsoft.com/fabric/data-engineering/library-management) for why inline `%pip install` is a trap in a shared workspace
- [Apache Spark runtimes in Fabric](https://learn.microsoft.com/fabric/data-engineering/runtime) so you know what the base image already gives you

### If you are building the report

- [Direct Lake in Power BI Desktop](https://learn.microsoft.com/fabric/fundamentals/direct-lake-power-bi-desktop), and note the fallback conditions
- [Dimensional modeling in Fabric Data Warehouse](https://learn.microsoft.com/fabric/data-warehouse/dimensional-modeling-overview) for the star schema this repo already produces
- [Power BI semantic models in Microsoft Fabric](https://learn.microsoft.com/fabric/data-warehouse/semantic-models)
- [Tutorial: Build Power BI reports in Microsoft Fabric](https://learn.microsoft.com/power-bi/fundamentals/fabric-get-started)

The single most useful thing to learn here is how to tell that Direct Lake has
silently fallen back to DirectQuery. The report still works. It just gets slow,
and nothing tells you why.

### If you are scheduling and operating it

- [Pipeline overview](https://learn.microsoft.com/fabric/data-factory/pipeline-overview) and [What is Data Factory in Microsoft Fabric?](https://learn.microsoft.com/fabric/data-factory/data-factory-overview)
- [Transform data by running a notebook](https://learn.microsoft.com/fabric/data-factory/notebook-activity), which is the activity type in [pipelines/forest_classification_pipeline.json](../pipelines/forest_classification_pipeline.json)
- [Microsoft Fabric decision guide: copy activity, Copy job, dataflow, Eventstream, or Spark](https://learn.microsoft.com/fabric/fundamentals/decision-guide-pipeline-dataflow-spark), the official version of the argument in [docs/06-toolchain-decision-guide.md](06-toolchain-decision-guide.md)
- [Pipelines pricing for Data Factory in Microsoft Fabric](https://learn.microsoft.com/fabric/data-factory/pricing-pipelines) before you schedule anything hourly

### If you are the one who gets paged

- [Apache Spark monitoring overview](https://learn.microsoft.com/fabric/data-engineering/spark-monitoring-overview)
- [Apache Spark application detail monitoring](https://learn.microsoft.com/fabric/data-engineering/spark-detail-monitoring)
- [Spark errors overview in Microsoft Fabric](https://learn.microsoft.com/fabric/data-engineering/troubleshoot-spark)
- [Use the monitoring hub to track Fabric activity](https://learn.microsoft.com/fabric/admin/monitoring-hub)
- [Spark monitoring and performance optimization best practices](https://learn.microsoft.com/fabric/data-engineering/spark-monitoring-best-practices)

Pair these with [docs/14-debugging-notebook-failures.md](14-debugging-notebook-failures.md).
The Learn pages cover what the platform shows you. That doc covers what to do
when the platform shows you nothing useful, which was the case for every one of
the four real bugs found in this pipeline.

## Days 31 to 90: govern it, then certify

By this point the question stops being "does it run" and becomes "who is allowed
to change it, and what happens when it breaks at 2am".

- [Roles in workspaces in Microsoft Fabric](https://learn.microsoft.com/fabric/fundamentals/roles-workspaces) and the [permission model](https://learn.microsoft.com/fabric/security/permission-model), which is the machinery behind the three-workspace argument
- [What is Microsoft Fabric administration?](https://learn.microsoft.com/fabric/admin/admin-overview) and [Understand Microsoft Fabric admin roles](https://learn.microsoft.com/fabric/admin/roles)
- [Manage your Fabric capacity](https://learn.microsoft.com/fabric/admin/capacity-settings), because a paused capacity and a broken pipeline look identical from the report
- [Administer and govern Microsoft Fabric](https://learn.microsoft.com/training/paths/microsoft-fabric-admin-governance/)
- [Manage a Microsoft Fabric environment](https://learn.microsoft.com/training/paths/manage-microsoft-fabric-environment/)

If the tenant runs with outbound access protection, read
[Workspace outbound access protection for data engineering workloads](https://learn.microsoft.com/fabric/security/workspace-outbound-access-protection-data-engineering)
and the section on
[managing libraries with limited network access](https://learn.microsoft.com/fabric/data-engineering/environment-manage-library-with-outbound-access-protection).
That combination decides whether the workshop pipeline runs as written. It is
covered as Decision 1 in [DEPLOY.md](../DEPLOY.md).

### Certification

The relevant credential for the work in this repository is the Fabric Data
Engineer track.

- [Study Guide for Exam DP-700](https://learn.microsoft.com/credentials/certifications/resources/study-guides/dp-700), which is the honest scope statement
- [Course DP-700T00-A: Microsoft Fabric Data Engineer](https://learn.microsoft.com/training/courses/dp-700t00) for the instructor-led version

If the analytics and machine learning side is closer to your role,
[Implement a data science and machine learning solution for AI in Microsoft Fabric](https://learn.microsoft.com/training/paths/implement-data-science-machine-learning-fabric/)
is the adjacent path.

Certification is not the point, and a certificate will not tell you that
`affine` 3.0.1 breaks every raster load. It is useful as a reading list with a
deadline attached.

## Reference shelf

Kept short on purpose. These are the pages worth bookmarking rather than reading
once.

| Topic | Page |
|---|---|
| Lakehouse concepts | [What is a lakehouse](https://learn.microsoft.com/fabric/data-engineering/lakehouse-overview) |
| Delta behaviour | [Lakehouse and Delta Lake tables](https://learn.microsoft.com/fabric/data-engineering/lakehouse-and-delta-tables) |
| Medallion | [Medallion architecture with OneLake](https://learn.microsoft.com/fabric/onelake/onelake-medallion-lakehouse-architecture) |
| OneLake patterns | [Architecture patterns](https://learn.microsoft.com/fabric/onelake/architecture-patterns) |
| Shortcuts | [OneLake shortcuts](https://learn.microsoft.com/fabric/onelake/onelake-shortcuts), [shortcuts in a lakehouse](https://learn.microsoft.com/fabric/data-engineering/lakehouse-shortcuts) |
| Environments | [Create and use an environment](https://learn.microsoft.com/fabric/data-engineering/create-and-use-environment) |
| Libraries | [Library management](https://learn.microsoft.com/fabric/data-engineering/library-management), [manage libraries in environments](https://learn.microsoft.com/fabric/data-engineering/environment-manage-library) |
| Runtimes | [Apache Spark runtimes](https://learn.microsoft.com/fabric/data-engineering/runtime) |
| Spark monitoring | [Monitoring overview](https://learn.microsoft.com/fabric/data-engineering/spark-monitoring-overview), [run series](https://learn.microsoft.com/fabric/data-engineering/apache-spark-monitor-run-series) |
| Spark errors | [Troubleshoot Spark](https://learn.microsoft.com/fabric/data-engineering/troubleshoot-spark) |
| Pipelines | [Pipeline overview](https://learn.microsoft.com/fabric/data-factory/pipeline-overview), [notebook activity](https://learn.microsoft.com/fabric/data-factory/notebook-activity) |
| Tool choice | [Decision guide](https://learn.microsoft.com/fabric/fundamentals/decision-guide-pipeline-dataflow-spark) |
| Direct Lake | [Direct Lake in Power BI Desktop](https://learn.microsoft.com/fabric/fundamentals/direct-lake-power-bi-desktop) |
| Star schema | [Dimensional modeling](https://learn.microsoft.com/fabric/data-warehouse/dimensional-modeling-overview) |
| Workspaces | [Create a workspace](https://learn.microsoft.com/fabric/fundamentals/create-workspaces), [workspace roles](https://learn.microsoft.com/fabric/fundamentals/roles-workspaces) |
| Permissions | [Permission model](https://learn.microsoft.com/fabric/security/permission-model) |
| Capacity | [Capacity settings](https://learn.microsoft.com/fabric/admin/capacity-settings) |
| Outbound access | [Workspace outbound access protection](https://learn.microsoft.com/fabric/security/workspace-outbound-access-protection-data-engineering) |
| Reference architecture | [Enterprise BI with Microsoft Fabric](https://learn.microsoft.com/azure/architecture/example-scenario/analytics/enterprise-bi-microsoft-fabric) |

## Imagery and geospatial sources

These are outside Microsoft Learn because the data is.

- [Planetary Computer Explorer](https://planetarycomputer.microsoft.com/explore) for browsing scenes before you write code against them
- The STAC API at `https://planetarycomputer.microsoft.com/api/stac/v1`, which is what notebook 01 queries
- The Sentinel-2 L2A collection endpoint, `https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a`, for the band list and asset keys

One practical note from the verified run: the STAC projection extension renamed
`proj:epsg` to `proj:code`. Reading only the old spelling silently records a
missing CRS rather than failing. If you extend the ingest notebook, check the
item properties against the live API rather than against a blog post.

## A note on what to trust

This repository was verified against a live F64 capacity on 2026-09-02, and the
notes in it reflect the platform on that date. Fabric moves quickly. When
something here contradicts Learn, assume Learn is current and this is a
snapshot, then check whether the difference is a preview feature that reached
general availability.

The parts least likely to go stale are the ones about method rather than
product: how to isolate a failing cell, why a version pin needs a comment naming
the failure it prevents, and why a job that reports success is not the same as a
pipeline that produced correct data.
