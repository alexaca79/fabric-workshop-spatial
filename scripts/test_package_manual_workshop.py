"""Check the focused learner archive rather than the full authoring repository."""

import hashlib
import json
from zipfile import ZipFile

import pytest

from package_manual_workshop import package, verify_links
from release_verification import EVIDENCE_FILE, MAP_CHECKS, load_release_evidence


def test_given_manual_bundle_when_packaged_then_only_four_learner_folders_exist(tmp_path):
    output = tmp_path / "manual-preview.zip"

    receipt = package(output, draft=True)

    with ZipFile(output) as archive:
        names = archive.namelist()
        assert {name.split("/")[0] for name in names} == {"student", "solutions", "handouts", "deck"}
        assert sum(name.startswith("student/") and name.endswith(".ipynb") for name in names) == 6
        assert sum(name.startswith("solutions/") and name.endswith(".ipynb") for name in names) == 6
        assert not any(name.endswith((".py", ".ps1")) or "/raw/" in name for name in names)
        assert "handouts/imagery-download.md" in names
        assert "handouts/download-imagery.html" in names
        assert "INPUT_MODE" in archive.read("handouts/imagery-download.md").decode()
        verify_links({name: archive.read(name) for name in names})
    assert receipt["integrity"] == "PASS"


def test_given_existing_archive_when_packaged_then_previous_delivery_is_preserved(tmp_path):
    output = tmp_path / "manual.zip"
    output.write_bytes(b"previous delivery")

    with pytest.raises(FileExistsError):
        package(output, draft=True)

    assert output.read_bytes() == b"previous delivery"


def test_given_missing_handout_target_when_validated_then_packaging_fails():
    with pytest.raises(ValueError, match="Broken bundle link"):
        verify_links({"handouts/start.md": b"[Missing](missing.md)"})


def test_given_changed_notebook_hash_when_final_bundle_requested_then_release_is_rejected(tmp_path):
    artifacts = ["notebooks/student/01_STUDENT.ipynb", "notebooks/solutions/01.ipynb",
                 "environments/environment.yml", "docs/download-imagery.html", "README.md",
                 "decks/woodlands-manual-workshop.pptx", "docs/07-homework.md", "docs/12-spark-environment.md",
                 "docs/16-manual-upload-labs.md", "docs/17-manual-imagery-download.md"]
    for relative in artifacts:
        artifact = tmp_path / relative
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"verified content")
    evidence = {"status": "verified", "input_mode": "stac",
                "jobs": [{"lab": f"{number:02d}", "status": "Completed", "verified": True,
                          "input_mode": "stac", "application_id": f"application-{number}"} for number in range(6)],
                "map_verification": {"status": "passed", **dict.fromkeys(MAP_CHECKS, True)},
                "artifact_sha256": {relative: hashlib.sha256(b"verified content").hexdigest() for relative in artifacts}}
    receipt = tmp_path / EVIDENCE_FILE
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps(evidence), encoding="utf-8")
    load_release_evidence(tmp_path)
    (tmp_path / artifacts[0]).write_bytes(b"unverified edit")

    with pytest.raises(ValueError, match="verification is stale"):
        load_release_evidence(tmp_path)
