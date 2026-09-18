"""Check the focused learner archive rather than the full authoring repository."""

from zipfile import ZipFile

import pytest

from package_manual_workshop import package, verify_links


def test_given_manual_bundle_when_packaged_then_only_four_learner_folders_exist(tmp_path):
    output = tmp_path / "manual-preview.zip"

    receipt = package(output, draft=True)

    with ZipFile(output) as archive:
        names = archive.namelist()
        assert {name.split("/")[0] for name in names} == {"student", "solutions", "handouts", "deck"}
        assert sum(name.startswith("student/") and name.endswith(".ipynb") for name in names) == 6
        assert sum(name.startswith("solutions/") and name.endswith(".ipynb") for name in names) == 6
        assert not any(name.endswith((".py", ".ps1")) or "/raw/" in name for name in names)
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
