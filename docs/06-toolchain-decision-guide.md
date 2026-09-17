---
title: Tool chain decision guide
description: Three problem patterns, the decision rule for picking a Fabric tool chain, and the exercise cards used in the Session 1 selection block
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: concept
keywords:
  - decision guide
  - dataflows
  - spark
  - foundry
estimated_reading_time: 8
---

## Tool chain decision guide

Fabric offers several ways to do most things. Picking badly does not usually
fail loudly. It produces something that works on the day and costs someone two
years of maintenance, which is a harder problem to spot and a harder one to
undo.

## The decision rule

Ask three questions in order, and stop at the first that gives a clear answer.

1. Is the data tabular with a known schema? If yes, the lowest-code option that
   handles it is usually right.
2. Does the work need per-file, per-scene or per-geometry processing? If yes,
   you need code, which means a Spark notebook.
3. Does the work require judgement over unstructured content? If yes, and only
   if yes, a language model belongs in the chain.

The order matters. Starting at question three is how organisations end up asking
a model to do arithmetic.

## Three problem patterns

### Pattern A: tabular, known schema, scheduled refresh

Examples from Woodlands: harvest volumes by block from the scaling system,
contractor hours, road maintenance records, mill delivery reconciliation.

| Option              | Use when                                                        | Cost                                                    |
|---------------------|------------------------------------------------------------------|---------------------------------------------------------|
| Dataflow Gen2       | The transformation is expressible in Power Query and stays small | Hard to unit test, and diffs are unreadable in review    |
| Warehouse and T-SQL | The team already knows SQL and the logic is set-based            | No raster, no geometry beyond basic types                |
| Spark notebook      | You need Python libraries or the volume is genuinely large        | You now own a notebook forever                           |

Default: Dataflow Gen2 for ingestion, T-SQL for transformation. Reach for Spark
only when one of the other two cannot do it, not when it would be more fun.

### Pattern B: geospatial, per-scene or per-geometry

Examples: everything in this workshop. Imagery ingestion, reprojection, masking,
index computation, zonal statistics, change detection.

There is one real option: a Spark notebook with GeoPandas, rioxarray and
rasterio. Dataflows have no raster story. T-SQL can hold geometry but cannot
open a Cloud Optimized GeoTIFF or run a windowed read against a signed href.

The decision inside the pattern is where the parallelism lives:

| Approach                                | Use when                                                 |
|-----------------------------------------|-----------------------------------------------------------|
| Single-node pandas and rioxarray        | One area of interest, a handful of scenes, under a few GB  |
| Spark parallel across scenes            | Many areas or many dates, each independently processable   |
| Spark parallel across tiles             | One very large area that does not fit a single driver      |

This workshop uses the first, with the structure needed to move to the second.
That is deliberate: most operational forestry workloads are embarrassingly
parallel across scenes, and the refactor is a `mapPartitions` rather than a
rewrite.

### Pattern C: unstructured content and judgement

Examples: field notes reconciliation, permit document extraction, incident
report triage, narrative generation for a report tooltip.

| Option                       | Use when                                                              |
|------------------------------|------------------------------------------------------------------------|
| Foundry chat model in a notebook | Low volume, batch, output feeds a table                             |
| Foundry model behind a function  | Interactive or event-driven, needs its own scaling and auth          |
| A trained classifier             | You have labels, the classes are stable, and you need auditability   |
| No AI at all                     | A threshold or a lookup gives the same answer, which is often        |

The last row is the one worth defending in a review. If a rule gets you there,
the rule is cheaper, faster, reproducible, and explainable to a regulator.

## The trap

For each pattern there is an obvious tool that is wrong often enough to matter.

| Pattern | The obvious choice                | Why it fails                                                              |
|---------|-----------------------------------|----------------------------------------------------------------------------|
| A       | A Spark notebook, because it is flexible | You have taken on code ownership for a job that a dataflow refreshes silently |
| B       | A dataflow, because ingestion feels like ingestion | It cannot open the file, and you find out after committing to a date |
| C       | A language model, because the input is text | Half of those problems are a regex and a lookup table               |

## Exercise cards

Print or paste one card per table group. Two minutes of discussion, one minute
to defend. There is a defensible answer for each, and card 3 is the trap.

### Card 1

> Woodlands receives a monthly CSV from the scaling contractor with 40,000 rows:
> block id, species, volume, date, truck id. It has the same columns every month.
> Planning needs it joined to the block register and refreshed by the third of
> each month. Which chain, and why?

Expected direction: Dataflow Gen2 to land it, T-SQL or a Warehouse view to join
and publish. No notebook. The tell is "same columns every month".

### Card 2

> Silviculture wants to know which planted stands from the last five years are
> showing lower-than-expected canopy closure, using satellite imagery, refreshed
> quarterly, across the full licence area. Which chain, and why?

Expected direction: Spark notebook, medallion layers, exactly the pattern built
in this workshop. The tell is "using satellite imagery": no other tool can open
the file.

### Card 3

> Operations has 12,000 free-text field notes from the last three seasons. Each
> one mentions a block id somewhere in the text, and they want them linked to the
> block register so a supervisor can see notes by block. Which chain, and why?

Expected direction: this is the trap. The instinct is a language model for
"free text". Block ids follow a fixed format, so a regular expression extracts
them at near-perfect accuracy, for free, deterministically, and it can be
unit tested. A model is justified only for the residue that the pattern misses,
and only if that residue matters.

### Card 4

> A planner wants a two-sentence plain-language summary of each stand's
> condition in the Power BI tooltip, drawn from the twelve numeric columns the
> pipeline already produces. Which chain, and why?

Expected direction: this is where a model earns its place. The input is
structured and already trustworthy, the output is prose, the value is in
readability rather than in calculation, and the numbers are passed in rather
than generated. Constrain the output, validate it against the source row, and
store a validation status.

## The written rule

By the end of the block, each participant writes their own version of this
sentence and keeps it:

> I reach for a notebook when the data will not open any other way or the logic
> needs a library. I reach for a model when the output is language and the
> numbers come from somewhere I trust. Otherwise I reach for the lowest-code
> option that a colleague can maintain without me.

## References

Microsoft publishes its own version of this decision, and it is worth comparing
against the sentence above:

- [Microsoft Fabric decision guide: copy activity, Copy job, dataflow, Eventstream, or Spark](https://learn.microsoft.com/fabric/fundamentals/decision-guide-pipeline-dataflow-spark)
- [What is Data Factory in Microsoft Fabric?](https://learn.microsoft.com/fabric/data-factory/data-factory-overview)
- [Pipeline overview](https://learn.microsoft.com/fabric/data-factory/pipeline-overview)
- [Differences between Azure Data Factory and Fabric Data Factory](https://learn.microsoft.com/fabric/data-factory/compare-fabric-data-factory-and-azure-data-factory), if your team already runs ADF
- [Pipelines pricing for Data Factory in Microsoft Fabric](https://learn.microsoft.com/fabric/data-factory/pricing-pipelines), because the cheapest tool to write is not always the cheapest to run hourly

More in [docs/15-resources-and-learning-paths.md](15-resources-and-learning-paths.md).
