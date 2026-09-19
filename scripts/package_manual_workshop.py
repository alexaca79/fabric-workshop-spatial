"""Package only student notebooks, solutions, handouts and the manual deck.

Usage:
    python scripts/package_manual_workshop.py handouts/woodlands-manual.zip
    python scripts/package_manual_workshop.py handouts/manual-preview.zip --draft
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZIP_DEFLATED, ZipFile

import nbformat
from markdown_it import MarkdownIt
from pptx import Presentation

from release_verification import load_release_evidence

ROOT = Path(__file__).resolve().parents[1]


def addresses(text: str) -> list[str]:
    """Read actual Markdown link and image destinations through the parser."""
    result = []
    for token in MarkdownIt().parse(text):
        for child in token.children or []:
            address = child.attrGet("href") or child.attrGet("src")
            if address:
                result.append(address)
    return result


def rewrite_links(text: str, source: Path, destination: str, mapping: dict[Path, str]) -> str:
    """Relocate only parsed local links to their declared bundle destinations."""
    for address in dict.fromkeys(addresses(text)):
        target = urlsplit(address)
        if target.scheme or target.netloc or not target.path:
            continue
        original = (source.parent / unquote(target.path)).resolve()
        if original not in mapping:
            raise ValueError(f"No manual bundle destination for {source.name}: {address}")
        target_name = mapping[original]
        destination_parent = Path(destination).parent
        target_parts = Path(target_name).parts
        parent_parts = destination_parent.parts
        shared = 0
        while shared < min(len(target_parts), len(parent_parts)) and target_parts[shared] == parent_parts[shared]:
            shared += 1
        relative = "/".join([".."] * (len(parent_parts) - shared) + list(target_parts[shared:]))
        if target.fragment:
            relative += f"#{target.fragment}"
        if f"]({address})" not in text:
            raise ValueError(f"Unsupported Markdown link form: {address}")
        text = text.replace(f"]({address})", f"]({relative})")
    return text


def verify_links(entries: dict[str, bytes]) -> None:
    """Check bundled Markdown targets and local section anchors, including folders."""
    virtual_root = (ROOT / "_manual_bundle_validation").resolve()
    for name, content in entries.items():
        if not name.endswith(".md"):
            continue
        for address in addresses(content.decode("utf-8")):
            target = urlsplit(address)
            if target.scheme or target.netloc:
                continue
            path = ((virtual_root / name).parent / unquote(target.path)).resolve() if target.path else virtual_root / name
            relative = path.relative_to(virtual_root).as_posix()
            if relative not in entries and not any(entry.startswith(relative + "/") for entry in entries):
                raise ValueError(f"Broken bundle link in {name}: {address}")
            if target.fragment and relative.endswith(".md"):
                headings = re.findall(r"^#{1,6}\s+(.+)$", entries[relative].decode("utf-8"), re.MULTILINE)
                anchors = {re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-") for heading in headings}
                if unquote(target.fragment) not in anchors:
                    raise ValueError(f"Broken bundle anchor in {name}: {address}")


def bundle_entries(*, draft: bool = False) -> dict[str, bytes]:
    """Assemble the focused distribution without modifying any source artifact."""
    evidence_path = ROOT / "scripts/verification/training-manual-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if not draft and evidence["status"] != "ready_for_classroom":
        raise ValueError("Final bundle requires ready_for_classroom evidence; use --draft during rehearsal")
    entries: dict[str, bytes] = {}
    mapping = {
        (ROOT / "notebooks/student").resolve(): "student",
        (ROOT / "notebooks/solutions").resolve(): "solutions",
        (ROOT / "docs/07-homework.md").resolve(): "handouts/homework.md",
        (ROOT / "docs/16-manual-upload-labs.md").resolve(): "handouts/student-guide.md",
        (ROOT / "docs/12-spark-environment.md").resolve(): "handouts/environment-setup.md",
        (ROOT / "docs/17-manual-imagery-download.md").resolve(): "handouts/imagery-download.md",
        (ROOT / "docs/download-imagery.html").resolve(): "handouts/download-imagery.html",
        (ROOT / "environments/environment.yml").resolve(): "handouts/environment.yml",
    }
    for variant in ("student", "solutions"):
        notebooks = sorted((ROOT / "notebooks" / variant).glob("*.ipynb"))
        if len(notebooks) != 6:
            raise ValueError(f"Expected six {variant} notebooks")
        for notebook_path in notebooks:
            notebook = nbformat.read(notebook_path, as_version=4)
            nbformat.validate(notebook)
            if "dependencies" in notebook.metadata:
                raise ValueError(f"Cloud binding in learner artifact: {notebook_path.name}")
            name = f"{variant}/{notebook_path.name}"
            entries[name] = notebook_path.read_bytes()
            mapping[notebook_path.resolve()] = name
    for capture in evidence["screenshots"]:
        if capture["status"] != "captured":
            if not draft:
                raise ValueError(f"Missing required screenshot: {capture['file']}")
            continue
        source = ROOT / "docs" / evidence["screenshot_directory"] / capture["file"]
        name = f"handouts/images/training/manual/{capture['file']}"
        entries[name] = source.read_bytes()
        mapping[source.resolve()] = name
    download_images = ROOT / "docs/images/training/manual-download"
    download_captures = json.loads((ROOT / "scripts/verification/screenshots/manual-download/annotations.json").read_text(encoding="utf-8"))["captures"]
    for capture in download_captures:
        source = download_images / capture["file"]
        name = f"handouts/images/training/manual-download/{capture['file']}"
        entries[name] = source.read_bytes()
        mapping[source.resolve()] = name
    if not draft:
        load_release_evidence(ROOT)
    guide_path = ROOT / "docs/16-manual-upload-labs.md"
    guide = guide_path.read_text(encoding="utf-8")
    environment_path = ROOT / "docs/12-spark-environment.md"
    environment = environment_path.read_text(encoding="utf-8")
    homework_path = ROOT / "docs/07-homework.md"
    download_guide = ROOT / "docs/17-manual-imagery-download.md"
    for source, target, text in ((guide_path, "handouts/student-guide.md", guide),
                                 (environment_path, "handouts/environment-setup.md", environment),
                                 (homework_path, "handouts/homework.md", homework_path.read_text(encoding="utf-8")),
                                 (download_guide, "handouts/imagery-download.md", download_guide.read_text(encoding="utf-8"))):
        entries[target] = rewrite_links(text, source, target, mapping).encode("utf-8")
    entries["handouts/download-imagery.html"] = (ROOT / "docs/download-imagery.html").read_bytes()
    entries["handouts/environment.yml"] = (ROOT / "environments/environment.yml").read_bytes()
    deck_name = "woodlands-manual-workshop.pptx"
    deck = (ROOT / "decks" / deck_name).read_bytes()
    if not draft:
        presentation = Presentation(io.BytesIO(deck))
        if len(presentation.slides) != len(evidence["screenshots"]) + len(download_captures) + 2:
            raise ValueError("Final deck is stale or incomplete")
    entries[f"deck/{deck_name}"] = deck
    status = "DRAFT: live rehearsal is incomplete. Do not use for classroom delivery." if draft else "Verified classroom bundle."
    entries["handouts/START-HERE.md"] = (
        "---\ntitle: Woodlands in Fabric\ndescription: Start the six Fabric notebook exercises.\n---\n\n"
        "## Start Here\n\n" + status + "\n\n"
        "1. Open the [student guide](student-guide.md). Follow the steps in order.\n"
        "2. Upload the six [student notebooks](../student), then create your own lakehouse.\n"
        "3. Attach your default lakehouse and the published `env_forestops` Environment in every notebook.\n"
        "4. Follow [Planetary Computer downloads in Fabric](imagery-download.md) for Lab 01. STAC is the default; manual download/upload is the fallback.\n"
        "5. Complete each TODO, select **Run cell**, and inspect its validation. Stop at any exception or `[FAIL]`. Use the [solutions](../solutions) as answer keys.\n"
        "6. Verify Gold SQL, save and reopen your native Map, then test and publish your Data Agent.\n"
        f"7. Follow the [workshop deck](../deck/{deck_name}) alongside the guide.\n\n"
        "The facilitator completes [Environment setup](environment-setup.md) once.\n"
        "The bundle contains no deployment scripts, credentials or pre-attached notebook bindings.\n"
    ).encode("utf-8")
    verify_links(entries)
    return entries


def package(output: Path, *, draft: bool = False) -> dict:
    """Write a new archive and verify notebook counts, layout and ZIP integrity."""
    if output.exists():
        raise FileExistsError(f"Archive already exists: {output}")
    entries = bundle_entries(draft=draft)
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in sorted(entries.items()):
            archive.writestr(name, content)
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("Manual archive integrity check failed")
    return {"archive": str(output), "files": len(entries), "student_notebooks": 6,
            "solution_notebooks": 6, "folders": ["student", "solutions", "handouts", "deck"],
            "draft": draft, "links": "PASS", "integrity": "PASS"}


def create_parser() -> argparse.ArgumentParser:
    """Create the focused manual package command parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--draft", action="store_true")
    return parser


def main() -> int:
    """Build the requested new archive without overwriting earlier deliveries."""
    arguments = create_parser().parse_args()
    try:
        print(json.dumps(package(arguments.output, draft=arguments.draft), indent=2))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"Manual packaging failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
