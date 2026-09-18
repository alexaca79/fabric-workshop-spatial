"""Submit or inspect one final Lab 00 verification run without duplicate jobs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from update_training_release import API, ROOT, WORKSPACE, isolated_session, request

ITEM_ID = "bea0df2d-1f46-43b7-842b-7bec94e71272"
RECEIPT = ROOT / "scripts/verification/training-setup-rerun.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["submit", "status"])
    mode = parser.parse_args().mode
    base = f"{API}/v1/workspaces/{WORKSPACE}/items/{ITEM_ID}/jobs/instances"
    with isolated_session() as session:
        if mode == "submit":
            if RECEIPT.exists():
                raise RuntimeError("Receipt exists; inspect status rather than resubmit")
            jobs = request(session, "GET", base).json()
            active = [job for job in jobs["value"] if job["status"] not in {
                "Completed", "Failed", "Cancelled", "Deduped",
            }]
            if active:
                raise RuntimeError("Active setup job; do not start a duplicate")
            receipt = {"workspace_id": WORKSPACE, "notebook_id": ITEM_ID,
                       "submission_started": datetime.now(timezone.utc).isoformat()}
            RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
            response = request(session, "POST", base + "?jobType=RunNotebook", {})
            receipt.update({"http_status": response.status_code, "location": response.headers["Location"]})
        else:
            receipt = json.loads(RECEIPT.read_text())
            receipt["job"] = request(session, "GET", receipt["location"]).json()
            receipt["checked_utc"] = datetime.now(timezone.utc).isoformat()
        RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"mode": mode, "status": receipt.get("job", {}).get("status", "Submitted")}))
        session.headers.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
