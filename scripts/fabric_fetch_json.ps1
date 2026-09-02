# Download a JSON file written by a notebook into a lakehouse Files area.
#
# Usage: pwsh -File scripts/fabric_fetch_json.ps1 <layer> <filename>

param(
    [Parameter(Mandatory = $true)][ValidateSet('bronze', 'silver', 'gold')][string]$Layer,
    [Parameter(Mandatory = $true)][string]$FileName
)

$ErrorActionPreference = 'Stop'

$targets = @{
    bronze = @{ Workspace = 'de310cba-1e49-4608-9c25-55f297fb6dc7'; Lakehouse = '207c2a7d-52eb-4c1b-badc-162c21a5292d' }
    silver = @{ Workspace = '0f742d8e-000b-4280-bf8e-c9157d5235c1'; Lakehouse = 'a5e9f744-5d18-4552-990f-a04a121a6466' }
    gold   = @{ Workspace = 'da08264c-b08a-49c3-9dc1-e219913cbea7'; Lakehouse = 'e42f056d-3e4b-42bf-9ed7-6e7effdc78ab' }
}

$target = $targets[$Layer]
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
