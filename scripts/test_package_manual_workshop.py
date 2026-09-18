"""Check the focused learner archive rather than the full authoring repository."""

from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from package_manual_workshop import bundle_entries, package, verify_links


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


def test_given_changed_notebook_hash_when_final_bundle_requested_then_release_is_rejected(monkeypatch):
    monkeypatch.setattr("package_manual_workshop.hashlib.sha256",
                        lambda content: SimpleNamespace(hexdigest=lambda: "0" * 64))

    with pytest.raises(ValueError, match="verification is stale"):
        bundle_entries(draft=False)
