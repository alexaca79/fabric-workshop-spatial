# Summarise the environment_verify.json findings written by
# scripts/fabric_environment.py verify <layer>.
#
# Usage: pwsh -File scripts/fabric_check_verify.ps1

$ErrorActionPreference = 'Stop'
$token = az account get-access-token --resource "https://storage.azure.com" --query accessToken -o tsv

$layers = (Get-Content (Join-Path $PSScriptRoot 'env.json') -Raw | ConvertFrom-Json).layers

$targets = @(
    @{ Name = 'bronze'; Workspace = $layers.bronze.workspaceId; Lakehouse = $layers.bronze.lakehouseId },
    @{ Name = 'silver'; Workspace = $layers.silver.workspaceId; Lakehouse = $layers.silver.lakehouseId },
    @{ Name = 'gold'; Workspace = $layers.gold.workspaceId; Lakehouse = $layers.gold.lakehouseId }
)

foreach ($target in $targets) {
    $url = "https://onelake.dfs.fabric.microsoft.com/$($target.Workspace)/$($target.Lakehouse)/Files/environment_verify.json"
    try {
        $result = Invoke-RestMethod -Uri $url -Headers @{ Authorization = "Bearer $token" }
    }
    catch {
        Write-Output "[$($target.Name)] no verify result found"
        continue
    }

    $checks = @($result.PSObject.Properties)
    $failures = @($checks | Where-Object { -not $_.Value.ok } | ForEach-Object { $_.Name })
    $verdict = if ($failures.Count -eq 0) { 'ALL PASS' } else { "FAILED: $($failures -join ', ')" }

    Write-Output "[$($target.Name)] $($checks.Count) checks - $verdict"
    Write-Output "    $($result.'guard::pandas'.value) | $($result.'guard::numpy'.value)"
    Write-Output "    planetary_computer $($result.'import::planetary_computer'.value) | geopandas $($result.'import::geopandas'.value)"
    $stac = [string]$result.stac_search.value
    Write-Output "    stac: $($stac.Substring(0, [Math]::Min(70, $stac.Length)))"
    Write-Output ""
}
