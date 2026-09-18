"""Keep workspace identity checks independent of generalized display labels."""

from contextlib import nullcontext
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

import update_training_release as release


@pytest.mark.parametrize("mode", ["compare", "publish", "verify", "readback"])
@pytest.mark.parametrize("workspace_id", [release.WORKSPACE, "another-workspace", None])
def test_given_workspace_identity_when_release_runs_then_only_configured_id_is_accepted(
    monkeypatch, tmp_path, mode, workspace_id,
):
    session = SimpleNamespace(headers={})
    workspace = {"id": workspace_id, "displayName": "Existing workshop workspace"}
    calls = []

    def fake_request(actual_session, method, url):
        assert actual_session is session
        calls.append((method, url))
        return SimpleNamespace(json=lambda: workspace)

    monkeypatch.setattr(sys, "argv", ["update_training_release.py", mode])
    monkeypatch.setattr(release, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(release, "TARGETS", {})
    monkeypatch.setattr(release, "isolated_session", lambda: nullcontext(session))
    monkeypatch.setattr(release, "request", fake_request)

    if workspace_id == release.WORKSPACE:
        assert release.main() == 0
    else:
        with pytest.raises(RuntimeError, match="Workspace ID mismatch"):
            release.main()

    assert calls == [("GET", f"{release.API}/v1/workspaces/{release.WORKSPACE}")]
    assert not release.STATE_PATH.exists()


def test_given_capacity_readback_when_names_differ_then_only_configured_ids_are_selected():
    powershell = shutil.which("pwsh")
    if not powershell:
        pytest.skip("PowerShell is required for the capacity-filter regression")
    command = """
$ErrorActionPreference = 'Stop'
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $env:WORKSHOP_CAPACITY_SCRIPT, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw 'Capacity script has syntax errors' }
$predicate = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and
    $node.GetCommandName() -eq 'Where-Object'
}, $true)
$filter = $predicate.CommandElements[1].ScriptBlock.GetScriptBlock()
$workspaces = @(@{ Id = 'bronze-id' }, @{ Id = 'silver-id' }, @{ Id = 'gold-id' })
$candidates = @(
    [pscustomobject]@{ id = 'bronze-id'; displayName = 'Existing Bronze' },
    [pscustomobject]@{ id = 'silver-id'; displayName = 'Renamed Silver' },
    [pscustomobject]@{ id = 'gold-id'; displayName = 'Existing Gold' },
    [pscustomobject]@{ id = 'other-id'; displayName = 'fabric-mock-training-other' }
)
$actual = @($candidates | Where-Object -FilterScript $filter)
if (($actual.id -join ',') -ne 'bronze-id,silver-id,gold-id') {
    throw 'Capacity readback did not select exactly the configured workspace IDs'
}
"""

    subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        env={**os.environ, "WORKSHOP_CAPACITY_SCRIPT": str(
            Path(__file__).with_name("fabric_assign_capacity.ps1"),
        )},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
