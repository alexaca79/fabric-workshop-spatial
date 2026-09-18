"""Check annotation bounds and preservation of the original portal capture."""

import hashlib

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from annotate_manual_screenshots import annotate


@pytest.fixture
def capture():
    return {"title": "Select the action", "focus": [
        {"box": [100, 40, 80, 30], "badge": [40, 55], "text": "Choose Create."},
    ]}


def test_given_capture_when_annotated_then_original_and_untouched_pixels_are_preserved(tmp_path, capture):
    raw, output = tmp_path / "raw.png", tmp_path / "annotated.png"
    Image.new("RGB", (300, 140), "#E3F0F5").save(raw)
    before = hashlib.sha256(raw.read_bytes()).hexdigest()

    receipt = annotate(raw, output, capture)

    assert hashlib.sha256(raw.read_bytes()).hexdigest() == before
    with Image.open(output) as image:
        assert image.width == 300 and image.height > 140
        assert image.getpixel((270, 120)) == (227, 240, 245)
        assert image.getpixel((40, 55)) != (227, 240, 245)
        assert image.info["Source SHA256"] == before
    assert receipt["callouts"] == 1


def test_given_sanitized_capture_when_annotated_then_anonymization_notice_is_preserved(tmp_path, capture):
    raw, output = tmp_path / "raw.png", tmp_path / "annotated.png"
    metadata = PngInfo()
    metadata.add_text("Anonymization", "Customer labels generalized locally.")
    Image.new("RGB", (300, 140), "#E3F0F5").save(raw, pnginfo=metadata)

    annotate(raw, output, capture)

    with Image.open(output) as image:
        assert image.info["Anonymization"] == "Customer labels generalized locally."


def test_given_same_path_when_annotated_then_source_overwrite_is_rejected(tmp_path, capture):
    raw = tmp_path / "raw.png"
    Image.new("RGB", (300, 140)).save(raw)

    with pytest.raises(ValueError, match="must not overwrite"):
        annotate(raw, raw, capture)


@pytest.mark.parametrize("box", [[-1, 1, 80, 30], [260, 1, 80, 30], [100, 130, 80, 30]])
def test_given_offscreen_target_when_annotated_then_capture_is_rejected(tmp_path, capture, box):
    raw = tmp_path / "raw.png"
    Image.new("RGB", (300, 140)).save(raw)
    capture["focus"][0]["box"] = box

    with pytest.raises(ValueError, match="outside"):
        annotate(raw, tmp_path / "output.png", capture)
