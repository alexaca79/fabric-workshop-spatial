# Create one lakehouse per medallion-layer workspace.
# Usage: pwsh -File scripts/fabric_create_lakehouses.ps1

$ErrorActionPreference = 'Stop'
$fabricResource = 'https://api.fabric.microsoft.com'

$config = (Get-Content (Join-Path $PSScriptRoot 'env.json') -Raw | ConvertFrom-Json).layers

$layers = @(
    @{ Workspace = $config.bronze.workspace; WorkspaceId = $config.bronze.workspaceId; Lakehouse = $config.bronze.lakehouse },
    @{ Workspace = $config.silver.workspace; WorkspaceId = $config.silver.workspaceId; Lakehouse = $config.silver.lakehouse },
    @{ Workspace = $config.gold.workspace; WorkspaceId = $config.gold.workspaceId; Lakehouse = $config.gold.lakehouse }
)

$created = @()

foreach ($layer in $layers) {
    $body = @{ displayName = $layer.Lakehouse } | ConvertTo-Json -Compress
    $bodyFile = New-TemporaryFile
    Set-Content -Path $bodyFile -Value $body -Encoding utf8 -NoNewline

    $url = "$fabricResource/v1/workspaces/$($layer.WorkspaceId)/lakehouses"
    $raw = az rest --method post --url $url --resource $fabricResource --headers 'Content-Type=application/json' --body "@$bodyFile" 2>&1
    Remove-Item $bodyFile -Force

    try {
        $lh = $raw | ConvertFrom-Json
        $created += [pscustomobject]@{
            Workspace   = $layer.Workspace
            WorkspaceId = $layer.WorkspaceId
            Lakehouse   = $lh.displayName
            LakehouseId = $lh.id
        }
        Write-Output "created: $($layer.Workspace) / $($lh.displayName)"
    }
    catch {
        Write-Output "FAILED : $($layer.Workspace) / $($layer.Lakehouse) :: $($raw -join ' ')"
    }
}

$created | ConvertTo-Json -Depth 4 | Set-Content -Path 'scripts/.fabric-mock-env.json' -Encoding utf8
Write-Output ''
$created | Format-List
