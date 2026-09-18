---
title: Workshop maintenance
description: Build and validate the learner artifacts without adding maintainer files to docs or decks.
---

## Learners

Start with the [repository README](../README.md). These tools are not needed to
complete the notebook exercises.

## Current Build

Use the maintainer Python environment with the root build and Fabric requirements
installed. Run these commands from the repository root:

```powershell
python scripts/build_all.py --check
python -m pytest scripts --ignore=scripts/test_download_handout.py -q
python scripts/build_all.py
python scripts/package_manual_workshop.py handouts/woodlands-workshop.zip
```

The packager requires a new output filename and matching verified notebook
hashes. It does not replace an earlier archive or claim a new Fabric rehearsal.

## Supporting Files

* `deck/`: current deck generator and shared rendering helpers
* `verification/`: recorded runs and test reports, separate from learner guides
* `verification/screenshots/`: original captures, annotations and source hashes
* `../docs/images/`: only annotated screenshots used by the retained guides

The current notebooks use one learner lakehouse. Older `fabric_*` deployment
utilities target earlier environments and are not part of the learner workflow.
