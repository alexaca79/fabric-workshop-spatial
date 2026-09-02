# Create one lakehouse per medallion-layer workspace.
# Usage: pwsh -File scripts/fabric_create_lakehouses.ps1

$ErrorActionPreference = 'Stop'
$fabricResource = 'https://api.fabric.microsoft.com'

$layers = @(
    @{ Workspace = 'jdi-mock-training-bronze'; WorkspaceId = 'de310cba-1e49-4608-9c25-55f297fb6dc7'; Lakehouse = 'lh_bronze' },
    @{ Workspace = 'jdi-mock-training-silver'; WorkspaceId = '0f742d8e-000b-4280-bf8e-c9157d5235c1'; Lakehouse = 'lh_silver' },
    @{ Workspace = 'jdi-mock-training-gold'; WorkspaceId = 'da08264c-b08a-49c3-9dc1-e219913cbea7'; Lakehouse = 'lh_gold' }
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
