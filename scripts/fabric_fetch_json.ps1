# Download a JSON file written by a notebook into a lakehouse Files area.
#
# Usage: pwsh -File scripts/fabric_fetch_json.ps1 <layer> <filename>

param(
    [Parameter(Mandatory = $true)][ValidateSet('bronze', 'silver', 'gold')][string]$Layer,
    [Parameter(Mandatory = $true)][string]$FileName
)

$ErrorActionPreference = 'Stop'

$layers = (Get-Content (Join-Path $PSScriptRoot 'env.json') -Raw | ConvertFrom-Json).layers
$target = @{ Workspace = $layers.$Layer.workspaceId; Lakehouse = $layers.$Layer.lakehouseId }

$token = az account get-access-token --resource "https://storage.azure.com" --query accessToken -o tsv
$url = "https://onelake.dfs.fabric.microsoft.com/$($target.Workspace)/$($target.Lakehouse)/Files/$FileName"

try {
    $result = Invoke-RestMethod -Uri $url -Headers @{ Authorization = "Bearer $token" }
}
catch {
    Write-Output "could not read $FileName from $Layer : $($_.Exception.Message)"
    exit 1
}

$result | ConvertTo-Json -Depth 6
