# Reassign the jdi-mock-training workspaces to a target Fabric capacity.
# Usage: pwsh -File scripts/fabric_assign_capacity.ps1 -CapacityId <guid>
param(
    [Parameter(Mandatory = $true)]
    [string]$CapacityId
)

$ErrorActionPreference = 'Stop'
$fabricResource = 'https://api.fabric.microsoft.com'

$workspaces = @(
    @{ Name = 'jdi-mock-training-bronze'; Id = 'de310cba-1e49-4608-9c25-55f297fb6dc7' },
    @{ Name = 'jdi-mock-training-silver'; Id = '0f742d8e-000b-4280-bf8e-c9157d5235c1' },
    @{ Name = 'jdi-mock-training-gold'; Id = 'da08264c-b08a-49c3-9dc1-e219913cbea7' }
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
