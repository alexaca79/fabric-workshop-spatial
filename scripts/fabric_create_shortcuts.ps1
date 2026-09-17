# Create the OneLake shortcuts that let each medallion layer read its upstream.
#
# Two kinds, and the ordering matters:
#
#   Files  - created once, up front. The Files folder always exists, so these
#            can be made against empty lakehouses.
#   Tables - a table shortcut needs a real target table, so these can only be
#            created AFTER the upstream notebook has written it. Re-run with
#            -Tables once the upstream layer has produced data.
#
# Usage:
#   pwsh -File scripts/fabric_create_shortcuts.ps1            # Files only
#   pwsh -File scripts/fabric_create_shortcuts.ps1 -Tables    # Files + Tables

param(
    [switch]$Tables
)

$ErrorActionPreference = 'Continue'
$fabricResource = 'https://api.fabric.microsoft.com'

$layers = (Get-Content (Join-Path $PSScriptRoot 'env.json') -Raw | ConvertFrom-Json).layers

$bronze = @{ Name = 'bronze'; WorkspaceId = $layers.bronze.workspaceId; LakehouseId = $layers.bronze.lakehouseId }
$silver = @{ Name = 'silver'; WorkspaceId = $layers.silver.workspaceId; LakehouseId = $layers.silver.lakehouseId }
$gold = @{ Name = 'gold'; WorkspaceId = $layers.gold.workspaceId; LakehouseId = $layers.gold.lakehouseId }

function New-OneLakeShortcut {
    param(
        [hashtable]$Owner,
        [hashtable]$Target,
        [string]$Path,
        [string]$Name,
        [string]$TargetPath
    )

    $payload = @{
        path   = $Path
        name   = $Name
        target = @{
            oneLake = @{
                workspaceId = $Target.WorkspaceId
                itemId      = $Target.LakehouseId
                path        = $TargetPath
            }
        }
    } | ConvertTo-Json -Depth 6 -Compress

    $bodyFile = New-TemporaryFile
    Set-Content -Path $bodyFile -Value $payload -Encoding utf8 -NoNewline

    $url = "$fabricResource/v1/workspaces/$($Owner.WorkspaceId)/items/$($Owner.LakehouseId)/shortcuts"
    $raw = az rest --method post --url $url --resource $fabricResource --headers 'Content-Type=application/json' --body "@$bodyFile" 2>&1
    Remove-Item $bodyFile -Force

    $label = "$($Owner.Name)/$Path/$Name -> $($Target.Name)"
    if ($LASTEXITCODE -eq 0) {
        Write-Output "  OK      $label"
        return
    }

    $message = ($raw -join ' ')
    if ($message -match 'ShorcutsOperationNotAllowed|already exists|EntityConflict') {
        Write-Output "  EXISTS  $label"
    }
    elseif ($message -match 'RequestBodyValidationFailed|NotFound|does not exist|InvalidPath') {
        # Fabric reports a missing target table as RequestBodyValidationFailed
        # rather than NotFound, which reads like a malformed payload. It is not.
        Write-Output "  PENDING $label  (upstream table not written yet)"
    }
    else {
        if ($message.Length -gt 160) { $message = $message.Substring(0, 160) }
        Write-Output "  FAILED  $label  :: $message"
    }
}

Write-Output 'Files-level shortcuts (raster and snapshot files)'
New-OneLakeShortcut -Owner $silver -Target $bronze -Path 'Files' -Name 'bronze' -TargetPath 'Files'
New-OneLakeShortcut -Owner $gold -Target $silver -Path 'Files' -Name 'silver' -TargetPath 'Files'

if ($Tables) {
    Write-Output ''
    Write-Output 'Table-level shortcuts (upstream layers must already be populated)'

    # Silver reads the bronze stand register and scene catalogue.
    foreach ($table in @('bronze_stand_register', 'bronze_scene_catalog')) {
        New-OneLakeShortcut -Owner $silver -Target $bronze -Path 'Tables' -Name $table -TargetPath "Tables/$table"
    }

    # Gold reads silver observations, and notebook 05 also reaches back to bronze.
    New-OneLakeShortcut -Owner $gold -Target $silver -Path 'Tables' -Name 'silver_stand_observations' -TargetPath 'Tables/silver_stand_observations'
    New-OneLakeShortcut -Owner $gold -Target $bronze -Path 'Tables' -Name 'bronze_stand_register' -TargetPath 'Tables/bronze_stand_register'
}

Write-Output ''
Write-Output 'Current shortcuts'
foreach ($layer in @($silver, $gold)) {
    $url = "$fabricResource/v1/workspaces/$($layer.WorkspaceId)/items/$($layer.LakehouseId)/shortcuts"
    $list = (az rest --method get --url $url --resource $fabricResource | ConvertFrom-Json).value
    if (-not $list) {
        Write-Output "  $($layer.Name): none"
        continue
    }
    foreach ($shortcut in $list) {
        Write-Output "  $($layer.Name): $($shortcut.path)/$($shortcut.name)  ->  $($shortcut.target.oneLake.path)"
    }
}
