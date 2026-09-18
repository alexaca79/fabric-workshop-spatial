"""Keep learner-facing folders small and all exercise references usable."""

from urllib.parse import unquote, urlsplit

import nbformat

from package_manual_workshop import ROOT, addresses, bundle_entries


def test_given_docs_folder_when_listed_then_only_exercise_guides_remain():
    files = {path.name for path in (ROOT / "docs").iterdir() if path.is_file()}

    assert files == {"07-homework.md", "12-spark-environment.md", "16-manual-upload-labs.md",
                     "17-manual-imagery-download.md", "download-imagery.html"}


def test_given_decks_folder_when_listed_then_only_the_current_deck_remains():
    files = {path.relative_to(ROOT / "decks").as_posix() for path in (ROOT / "decks").rglob("*") if path.is_file()}

    assert files == {"woodlands-manual-workshop.pptx"}


def test_given_guide_images_when_scanned_then_every_retained_image_is_used():
    referenced = set()
    for guide in (ROOT / "docs").glob("*.md"):
        for address in addresses(guide.read_text(encoding="utf-8")):
            url = urlsplit(address)
            if not url.scheme and url.path.endswith(".png"):
                referenced.add((guide.parent / unquote(url.path)).resolve())
    actual = {path.resolve() for path in (ROOT / "docs/images").rglob("*") if path.is_file()}

    assert actual == referenced
    assert len(actual) == 50


def test_given_notebook_markdown_links_when_followed_then_targets_exist():
    for variant in ("student", "solutions"):
        for path in (ROOT / "notebooks" / variant).glob("*.ipynb"):
            notebook = nbformat.read(path, as_version=4)
            for cell in notebook.cells:
                if cell.cell_type != "markdown":
                    continue
                for address in addresses(cell.source):
                    url = urlsplit(address)
                    if not url.scheme and url.path:
                        assert (path.parent / unquote(url.path)).resolve().exists(), (path.name, address)


def test_given_learner_bundle_when_built_then_maintainer_receipts_are_not_included():
    entries = bundle_entries(draft=True)

    assert "handouts/homework.md" in entries
    assert not any("evidence" in name or name.endswith(".xml") or "/raw/" in name for name in entries)
    assert not any("draft" in name or "session-1" in name or "session-2" in name for name in entries)
