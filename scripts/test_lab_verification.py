"""Test the evidence helper before using it around cloud notebook cells."""

import json

import pytest

from scripts.probes.lab_verification import LabVerification


def test_given_valid_cells_when_finished_then_records_checks_and_tables(tmp_path, capsys):
    recorder = LabVerification(tmp_path / "lab.json", {"code_cells": [4, 6]}, {"application_id": "session-a"})

    with recorder.cell(4):
        print("[PASS] valid input")
    with recorder.cell(6):
        print("[PASS] table written")
    recorder.finish({"bronze_stand_register": 120})

    saved = json.loads((tmp_path / "lab.json").read_text())
    assert saved["status"] == "passed"
    assert saved["checks_passed"] == 2
    assert saved["tables"] == {"bronze_stand_register": 120}
    assert saved["runtime"]["application_id"] == "session-a"
    assert "[PASS] table written" in capsys.readouterr().out


def test_given_failed_check_when_cell_completes_then_receipt_fails_and_raises(tmp_path):
    recorder = LabVerification(tmp_path / "lab.json", {"code_cells": [4]}, {})

    with pytest.raises(AssertionError, match="reported"):
        with recorder.cell(4):
            print("[FAIL] invalid output")

    saved = json.loads((tmp_path / "lab.json").read_text())
    assert saved["status"] == "failed"
    assert saved["cells"][0]["status"] == "failed"


def test_given_cell_exception_when_recorded_then_failure_is_durable_and_url_redacted(tmp_path):
    recorder = LabVerification(tmp_path / "lab.json", {"code_cells": [4]}, {})

    with pytest.raises(ValueError, match="download"):
        with recorder.cell(4):
            raise ValueError("download https://example.test/file?sig=sensitive failed")

    saved = (tmp_path / "lab.json").read_text()
    assert "sensitive" not in saved
    assert json.loads(saved)["cells"][0]["error"]["type"] == "ValueError"


@pytest.mark.parametrize("tables", [{}, {"output": 0}])
def test_given_missing_output_when_finished_then_no_success_receipt(tmp_path, tables):
    recorder = LabVerification(tmp_path / "lab.json", {"code_cells": [4]}, {})
    with recorder.cell(4):
        pass

    with pytest.raises(AssertionError, match="durable"):
        recorder.finish(tables)

    assert json.loads((tmp_path / "lab.json").read_text())["status"] == "failed"


def test_given_unexecuted_cell_when_finished_then_rejects_incomplete_run(tmp_path):
    recorder = LabVerification(tmp_path / "lab.json", {"code_cells": [4, 6]}, {})
    with recorder.cell(4):
        pass

    with pytest.raises(AssertionError, match="Incomplete"):
        recorder.finish({"output": 1})


def test_given_wrong_cell_order_when_started_then_rejects_execution(tmp_path):
    recorder = LabVerification(tmp_path / "lab.json", {"code_cells": [4]}, {})

    with pytest.raises(ValueError, match="Unexpected"):
        with recorder.cell(6):
            pytest.fail("Out-of-order cell body executed")
