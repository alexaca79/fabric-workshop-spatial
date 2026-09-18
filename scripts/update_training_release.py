"""Apply the reviewed training-cell changes with restartable Fabric receipts.

Usage: python scripts/update_training_release.py compare|publish|verify|readback
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import nbformat
import requests

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = "60a018e6-4688-4a64-84af-0574e0bc8d3a"
TENANT = "711a9076-1115-4c36-b7b4-82b4f3a05f6f"
API = "https://api.fabric.microsoft.com"
RECOVERY = Path.home() / "JDI-training-retired-app-20260917-125920/notebook-before-validation-fix"
STATE_PATH = ROOT / "scripts/verification/training-release-state.json"
TARGETS = {
    "00_setup_lakehouse_and_config": "bea0df2d-1f46-43b7-842b-7bec94e71272",
    "00_setup_lakehouse_and_config_STUDENT": "e44cad16-4a4b-4ba3-96e3-9be3ccf8000d",
    "05_publish_and_validate": "f478c3cb-4924-4736-9366-4264cd9b1a96",
    "05_publish_and_validate_STUDENT": "f7a9e08d-a8eb-4b01-bef9-2980aa5e3a26",
}


def cli_json(arguments: list[str]) -> dict:
    """Use the isolated CLI without exposing its token output."""
    executable = shutil.which("az")
    if not executable:
        raise RuntimeError("Azure CLI is unavailable")
    command = [executable, *arguments, "--output", "json"]
    shim = Path(executable).suffix.lower() in {".cmd", ".bat"}
    result = subprocess.run(
        subprocess.list2cmdline(command) if shim else command,
        shell=shim,
        capture_output=True,
        text=True,
        timeout=45,
        check=True,
    )
    return json.loads(result.stdout)


def isolated_session() -> requests.Session:
    """Restore only the previously approved contoso context and assert it."""
    profile = json.loads((Path.home() / ".azure-tenants/index.json").read_text())["tenants"]["contoso"]
    if profile["tenant_id"] != TENANT:
        raise RuntimeError("Tenant index changed")
    os.environ["AZURE_CONFIG_DIR"] = profile["config_dir"]
    os.environ["AZD_CONFIG_DIR"] = profile["azd_config_dir"]
    account = cli_json(["account", "show"])
    if account["tenantId"] != TENANT or not (
        account["id"] in profile["allowed_subscriptions"]
        or account["name"] in profile["allowed_subscriptions"]
    ):
        raise RuntimeError("Tenant or subscription mismatch")
    session = requests.Session()
    token = cli_json(["account", "get-access-token", "--resource", API])["accessToken"]
    session.headers.update({"Authorization": f"Bearer {token}", "x-ms-fabric-skill": "spark-cli"})
    return session


def request(session: requests.Session, method: str, url: str, body=None):
    endpoint = urlsplit(url)
    if endpoint.scheme != "https" or endpoint.hostname not in {
        "api.fabric.microsoft.com",
        "wabi-west-us3-a-primary-redirect.analysis.windows.net",
    }:
        raise RuntimeError("Unexpected Fabric endpoint")
    response = session.request(method, url, json=body, timeout=40)
    if response.status_code not in {200, 201, 202}:
        raise RuntimeError(f"Fabric {method} returned HTTP {response.status_code}")
    return response


def submit(session: requests.Session, url: str, body: dict) -> dict:
    response = request(session, "POST", url, body)
    if response.status_code == 202:
        return {"http_status": 202, "operation": response.headers["Location"]}
    return {"http_status": response.status_code, "result": response.json() if response.content else {}}


def resolve(session: requests.Session, receipt: dict, *, definition=False) -> dict:
    if "result" in receipt:
        return receipt["result"]
    status = request(session, "GET", receipt["operation"]).json()
    if status["status"] != "Succeeded":
        raise RuntimeError(f"Operation is {status['status']}; receipt retained, no resubmission")
    if definition:
        return request(session, "GET", receipt["operation"].rstrip("/") + "/result").json()
    return status


def decode(envelope: dict) -> dict:
    parts = [part for part in envelope["definition"]["parts"] if part["path"].endswith(".ipynb")]
    if len(parts) != 1:
        raise RuntimeError("Expected one notebook part")
    return json.loads(base64.b64decode(parts[0]["payload"]))


def source(cell: dict) -> str:
    return "".join(cell["source"]).replace("\r\n", "\n").rstrip()


def cell_for(book: dict, marker: str) -> tuple[int, dict]:
    matches = [(index, cell) for index, cell in enumerate(book["cells"]) if marker in source(cell)]
    if len(matches) != 1:
        raise RuntimeError(f"Ambiguous cell marker: {marker}")
    return matches[0]


def merge(name: str, current: dict) -> tuple[dict, list[dict]]:
    """Replace only reviewed cells, rejecting changes since the saved baseline."""
    variant = "student" if name.endswith("_STUDENT") else "solutions"
    local = json.loads((ROOT / "notebooks" / variant / f"{name}.ipynb").read_text(encoding="utf-8"))
    baseline = decode(json.loads((RECOVERY / f"{name}.before.definition.json").read_text(encoding="utf-8-sig")))
    if name.startswith("00"):
        markers = [
            ('report("areas are plausible"', 'report("areas match expected scale"'),
            ("The area check is the one that matters", "The synthetic polygons are sampling cells"),
        ]
    else:
        markers = [(marker, marker) for marker in (
            "# Lab 05 -", "## Step 9 ", "## Step 10 ", "## Step 11 ",
            "## Step 12 ", "## Final checkpoint",
        )]
    merged = copy.deepcopy(current)
    changes = []
    for old_marker, new_marker in markers:
        index, actual = cell_for(current, old_marker)
        _, old = cell_for(baseline, old_marker)
        _, new = cell_for(local, new_marker)
        if source(actual) != source(old):
            raise RuntimeError(f"Concurrent source edit: {name}, cell {index + 1}")
        merged["cells"][index]["source"] = copy.deepcopy(new["source"])
        changes.append({"cell_number": index + 1, "cell_type": actual["cell_type"]})
    restored = copy.deepcopy(merged)
    for change in changes:
        index = change["cell_number"] - 1
        restored["cells"][index]["source"] = current["cells"][index]["source"]
    if restored != current:
        raise RuntimeError("Non-target content changed")
    schema_book = copy.deepcopy(merged)
    schema_book.pop("notebookName", None)
    nbformat.validate(nbformat.from_dict(schema_book))
    return merged, changes


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["compare", "publish", "verify", "readback"])
    mode = parser.parse_args().mode
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {
        "workspace_id": WORKSPACE, "notebooks": {}, "data_writes": 0,
    }
    with isolated_session() as session:
        workspace = request(session, "GET", f"{API}/v1/workspaces/{WORKSPACE}").json()
        if workspace["displayName"] != "jdi-training":
            raise RuntimeError("Workspace name mismatch")
        for name, item_id in TARGETS.items():
            base = f"{API}/v1/workspaces/{WORKSPACE}/notebooks/{item_id}"
            record = state["notebooks"].setdefault(name, {"id": item_id})
            if mode == "compare" and "comparison" not in record:
                record["comparison"] = submit(session, base + "/getDefinition?format=ipynb", {})
            elif mode == "publish" and "publish" not in record:
                if record.get("submission_started"):
                    raise RuntimeError("Prior submission uncertain; inspect cloud history before retry")
                envelope = resolve(session, record["comparison"], definition=True)
                current = decode(envelope)
                merged, changes = merge(name, current)
                jobs_url = f"{API}/v1/workspaces/{WORKSPACE}/items/{item_id}/jobs/instances"
                while jobs_url:
                    jobs = request(session, "GET", jobs_url).json()
                    if any(job["status"] not in {"Completed", "Failed", "Cancelled", "Deduped"} for job in jobs["value"]):
                        raise RuntimeError("Active notebook job blocks publication")
                    jobs_url = jobs.get("continuationUri")
                item = request(session, "GET", f"{API}/v1/workspaces/{WORKSPACE}/items/{item_id}").json()
                if item["displayName"] != name or item["type"] != "Notebook":
                    raise RuntimeError("Notebook identity changed")
                account = cli_json(["account", "show"])
                if account["tenantId"] != TENANT or account["id"] != "a0c62bdd-d642-4fdb-b372-ae041cf83ce3":
                    raise RuntimeError("Authentication context changed")
                definition = copy.deepcopy(envelope["definition"])
                definition["format"] = "ipynb"
                next(part for part in definition["parts"] if part["path"].endswith(".ipynb"))["payload"] = base64.b64encode(json.dumps(merged).encode()).decode()
                record.update({"changes": changes, "before_sha256": fingerprint(current),
                               "expected_sha256": fingerprint(merged), "bindings": current["metadata"].get("dependencies", {}),
                               "submission_started": datetime.now(timezone.utc).isoformat()})
                save(state)
                record["publish"] = submit(session, base + "/updateDefinition", {"definition": definition})
            elif mode == "verify":
                resolve(session, record["publish"])
                record["publish_status"] = "Succeeded"
                if "readback" not in record:
                    record["readback"] = submit(session, base + "/getDefinition?format=ipynb", {})
            elif mode == "readback":
                actual = decode(resolve(session, record["readback"], definition=True))
                if fingerprint(actual) != record["expected_sha256"]:
                    raise RuntimeError(f"Readback differs for {name}")
                record["readback_status"] = "PASS"
                record["verified_utc"] = datetime.now(timezone.utc).isoformat()
            save(state)
            print(f"{mode}: {name}: receipt saved", flush=True)
        session.headers.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
