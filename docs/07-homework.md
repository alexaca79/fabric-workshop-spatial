---
title: Homework between sessions
description: Roughly 45 minutes of preparation between Session 1 and Session 2, defining your own area of interest and landing its stand register
author: Workshop Delivery Team
ms.date: 2026-09-02
ms.topic: how-to
keywords:
  - homework
  - area of interest
  - stand register
estimated_reading_time: 4
---

## Homework between sessions

Budget 45 minutes. The point is to arrive at Session 2 with your own area of
interest rather than the shared demo block, so that everything you build is
about somewhere you actually manage.

## Task 1: choose your area of interest (15 min)

Pick a block of forest you know. It can be a licence block, a management unit,
or an area you have walked.

1. Find its approximate bounding box in WGS84. The Planetary Computer Explorer
   at [planetarycomputer.microsoft.com/explore](https://planetarycomputer.microsoft.com/explore)
   is the quickest route: pan to the area, draw a box, and read the coordinates.
2. Keep it between roughly 10 km and 40 km on a side. Smaller than that and you
   get too few stands to see a pattern. Larger and Session 2 waits on downloads.
3. Record it in this format:

   ```python
   AOI_NAME = "your-block-name"
   AOI_BBOX = [-66.90, 46.10, -66.40, 46.40]  # west, south, east, north
   ```

## Task 2: check imagery availability (15 min)

Before Session 2 confirm there is usable imagery, because discovering there is
not at 0:20 on the day costs you the whole first block.

In the Planetary Computer Explorer:

1. Select the Sentinel-2 Level 2A collection.
2. Set the date range to the last full growing season, roughly June to
   September.
3. Set the cloud cover filter to 20 percent or less.
4. Confirm at least three scenes cover your box.

If you find fewer than three, widen the date range before widening the cloud
threshold. A clear scene from a slightly different week is more useful than a
cloudy scene from the right week.

Write down the scene count and the clearest date. You will use both.

## Task 3: land your stand register (15 min)

Re-run notebook 00 against your own area of interest.

1. Open `00_setup_lakehouse_and_config` in your workspace.
2. Change `AOI_NAME` and `AOI_BBOX` to your values.
3. Leave `USE_SYNTHETIC_STANDS = True` unless you have permission to load real
   inventory geometry into your workspace.
4. Run it end to end.
5. Confirm `bronze_stand_register` contains stands inside your box, and that
   `area_ha` values are plausible for stands you know.

The plausibility check is the real exercise. If your synthetic stands come out
at 4,000 hectares each, something is wrong with the projection, and finding that
now is much cheaper than finding it after you have built a classifier on top.

## Bring to Session 2

| Item                                        | Why                                                    |
|---------------------------------------------|---------------------------------------------------------|
| Your `AOI_NAME` and `AOI_BBOX`              | Every notebook in Session 2 is parameterised on them    |
| The scene count and clearest date you found | Step 1 of Session 2 starts from this                    |
| Your `bronze_stand_register` row count      | The debrief opens with three people showing theirs      |
| One question about your own data            | The last block is where this connects to your work      |

## If you get stuck

Post in the workshop Teams channel rather than arriving blocked. Most homework
problems are a bounding box in the wrong order, west and south before east and
north, and they take one message to resolve.

If you cannot complete the homework at all, come anyway. The shared area of
interest is pre-staged and you will not be behind.
