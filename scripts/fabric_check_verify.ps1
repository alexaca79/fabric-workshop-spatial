# Summarise the environment_verify.json findings written by
# scripts/fabric_environment.py verify <layer>.
#
# Usage: pwsh -File scripts/fabric_check_verify.ps1

$ErrorActionPreference = 'Stop'
$token = az account get-access-token --resource "https://storage.azure.com" --query accessToken -o tsv

$targets = @(
    @{ Name = 'bronze'; Workspace = 'de310cba-1e49-4608-9c25-55f297fb6dc7'; Lakehouse = '207c2a7d-52eb-4c1b-badc-162c21a5292d' },
    @{ Name = 'silver'; Workspace = '0f742d8e-000b-4280-bf8e-c9157d5235c1'; Lakehouse = 'a5e9f744-5d18-4552-990f-a04a121a6466' },
    @{ Name = 'gold'; Workspace = 'da08264c-b08a-49c3-9dc1-e219913cbea7'; Lakehouse = 'e42f056d-3e4b-42bf-9ed7-6e7effdc78ab' }
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
