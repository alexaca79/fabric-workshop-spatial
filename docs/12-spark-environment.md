---
title: Spark Environment setup
description: Publish the shared Fabric Environment before learners start the six notebook exercises.
author: Workshop Delivery Team
ms.date: 2026-09-18
ms.topic: how-to
keywords:
  - fabric environment
  - spark libraries
  - geospatial stack
  - dependency pinning
estimated_reading_time: 3
---

## Manual Portal Setup

The facilitator performs this once in the training workspace before class.
Allow about ten minutes for publication. All six notebooks use the same
published Environment; each learner uses their own default lakehouse.
Return to the [student guide](16-manual-upload-labs.md) after setup.

### Create The Environment

1. Open the Contoso workspace `fabric-training-manual`. Confirm its assigned
  `rayfintestenv` F64 capacity is active.
2. Select **New item**, search for **Environment**, and select it.
3. Enter `env_forestops`, then select **Create**.
4. In the **Home** ribbon, check **Runtime 1.3** (Spark 3.5, Python 3.11), the
  workshop's previously verified runtime. If unavailable, stop for compatibility
  validation instead of selecting a different major runtime without testing.

![Check Runtime 1.3 in the Environment Home ribbon.](images/training/manual/10-environment-runtime.png)

### Import Libraries

1. Open the navigation menu, then **Libraries** > **External repositories**.
  On a wider screen the navigation is already visible.
2. Select **More items** (`...`) > **Import YML** > **Upload to Full mode**.
  Confirm **Import**, then select
  the [Environment YAML file](../environments/environment.yml) from the bundle's
  **handouts** folder.
3. Alternatively, select **YML editor view** > **Full mode**, select all editor
  text and paste the file contents with **Ctrl+V**. Return to **List view**.
  Do not upload the file as a custom Python library or add a top-level `name`:
  the portal accepts `channels` and `dependencies`, not a Conda environment name.
4. Confirm the list contains 14 libraries and the definition retains `numpy<2`, `pandas>=2.1,<3`,
  `typing-extensions>=4.15`, `affine<3`, `zarr>=2.16` and all the other supplied
  packages. Keep the supplied version constraints unchanged.

![Use the Full mode library definition and Save before publishing.](images/training/manual/11-environment-libraries.png)

### Publish And Check

1. Select **Save** and confirm **Save changes**. In **Home**, select **Publish**,
  review **Pending changes**, select **Publish all**, then confirm **Publish**.
2. Wait for success. Saving a draft or seeing **Publishing** is not completion.
  Allow about ten minutes; actual time varies.
3. Return to the workspace and confirm `env_forestops` is available. Attach it
  to each notebook using the Home ribbon selector.
4. Start a new session and run Lab 00's Environment check. Lab 01's raster load
  remains the functional check for the full geospatial stack.

![Published Environment library rows report Success.](images/training/manual/12-environment-published.png)

Checkpoint: publication succeeded, every learner selects the Environment from
the correct workspace, and required imports pass. Do not substitute a
`%pip install` cell for a missing attachment.

If approved outbound policy blocks public packages, use the organization's
approved dependency process. Do not disable outbound protection. See
[libraries with limited network access](https://learn.microsoft.com/fabric/data-engineering/environment-manage-library-with-outbound-access-protection).
