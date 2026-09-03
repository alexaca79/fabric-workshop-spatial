# Reassign the jdi-mock-training workspaces to a target Fabric capacity.
# Usage: pwsh -File scripts/fabric_assign_capacity.ps1 -CapacityId <guid>
param(
    [Parameter(Mandatory = $true)]
    [string]$CapacityId
)

$ErrorActionPreference = 'Stop'
$fabricResource = 'https://api.fabric.microsoft.com'

$layers = (Get-Content (Join-Path $PSScriptRoot 'env.json') -Raw | ConvertFrom-Json).layers

$workspaces = @(
    @{ Name = $layers.bronze.workspace; Id = $layers.bronze.workspaceId },
    @{ Name = $layers.silver.workspace; Id = $layers.silver.workspaceId },
    @{ Name = $layers.gold.workspace; Id = $layers.gold.workspaceId }
)

$body = @{ capacityId = $CapacityId } | ConvertTo-Json -Compress
$bodyFile = New-TemporaryFile
Set-Content -Path $bodyFile -Value $body -Encoding utf8 -NoNewline

foreach ($ws in $workspaces) {
    $url = "$fabricResource/v1/workspaces/$($ws.Id)/assignToCapacity"
    az rest --method post --url $url --resource $fabricResource --headers 'Content-Type=application/json' --body "@$bodyFile" | Out-Null
    Write-Output "assigned: $($ws.Name)"
}

Remove-Item $bodyFile -Force

# Verify from the service rather than trusting the POST responses.
$live = (az rest --method get --url "$fabricResource/v1/workspaces" --resource $fabricResource | ConvertFrom-Json).value
$live |
    Where-Object { $_.displayName -like 'jdi-mock-training*' } |
    Select-Object displayName, id, capacityId |
    Format-List
