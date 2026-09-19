"""Capture durable cell-level evidence around unchanged workshop solution code."""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


class _OutputTee(io.TextIOBase):
    def __init__(self, target: TextIO, capture: io.StringIO) -> None:
        self.target = target
        self.capture = capture

    def write(self, text: str) -> int:
        self.target.write(text)
        return self.capture.write(text)

    def flush(self) -> None:
        self.target.flush()


class LabVerification:
    """Persist ordered solution-cell outcomes without sharing state across labs."""

    def __init__(self, output: Path, source: dict, runtime: dict) -> None:
        self.output = output
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.record = {
            "status": "running",
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "runtime": runtime,
            "cells": [],
        }
        self._save()

    def _save(self) -> None:
        self.output.write_text(json.dumps(self.record, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    @contextlib.contextmanager
    def cell(self, number: int) -> Iterator[None]:
        """Capture a cell, persist failures, and reject missing or reordered cells."""
        expected = self.record["source"]["code_cells"]
        position = len(self.record["cells"])
        if self.record["status"] != "running" or position >= len(expected) or number != expected[position]:
            raise ValueError(f"Unexpected verification cell {number}")
        captured = io.StringIO()
        outcome = {"number": number, "status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat()}
        self.record["cells"].append(outcome)
        try:
            with contextlib.redirect_stdout(_OutputTee(sys.stdout, captured)):
                yield
            if "[FAIL]" in captured.getvalue():
                raise AssertionError(f"Workshop validation reported [FAIL] in cell {number}")
        except Exception as error:
            outcome["status"] = "failed"
            outcome["error"] = {
                "type": type(error).__name__,
                "message": re.sub(r"https?://[^\s'\"<>]+", "[URL redacted]", str(error))[:2000],
            }
            self.record["status"] = "failed"
            raise
        else:
            outcome["status"] = "passed"
        finally:
            outcome["checks_passed"] = captured.getvalue().count("[PASS]")
            outcome["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            self.output.with_name(f"{self.output.stem}-cell-{number}.txt").write_text(captured.getvalue(), encoding="utf-8")
            self._save()

    def finish(self, tables: dict[str, int], *, map_export: dict | None = None) -> dict:
        """Mark success only after every expected cell and positive table count."""
        complete = [cell["number"] for cell in self.record["cells"]] == self.record["source"]["code_cells"]
        if self.record["status"] != "running" or not complete or not tables or any(count <= 0 for count in tables.values()):
            self.record["status"] = "failed"
            self._save()
            raise AssertionError("Incomplete cell sequence or missing durable table output")
        self.record.update({
            "status": "passed",
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "tables": tables,
            "checks_passed": sum(cell["checks_passed"] for cell in self.record["cells"]),
        })
        if map_export is not None:
            self.record["map_export"] = map_export
        self._save()
        return self.record
