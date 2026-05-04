param(
    [int]$StartOffset = 10,
    [int]$EndOffset = 500,
    [int]$BatchSize = 25,
    [int]$MaxWorkers = 4,
    [double]$QueryDelay = 0.2,
    [int]$DomainCap = 12,
    [string]$DatasetVersion = "dataset-v7-final",
    [string]$StatusPath = "output\d75-collection\collector.status.txt"
)

$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
New-Item -ItemType Directory -Force (Split-Path $StatusPath -Parent) | Out-Null

for ($offset = $StartOffset; $offset -lt $EndOffset; $offset += $BatchSize) {
    $remaining = $EndOffset - $offset
    $limit = [Math]::Min($BatchSize, $remaining)
    $started = "START offset=$offset limit=$limit time=$((Get-Date).ToString('o'))"
    $started | Tee-Object -FilePath $StatusPath

    & backend\.venv\Scripts\python.exe -m app.ml.dataset_builder `
        --versioned-layout `
        --dataset-version $DatasetVersion `
        --max-domain-rows-per-domain $DomainCap `
        --max-workers $MaxWorkers `
        --query-delay $QueryDelay `
        --seed-offset $offset `
        --seed-limit $limit

    if ($LASTEXITCODE -ne 0) {
        throw "dataset_builder failed at offset $offset"
    }

    $datasetPath = "backend\data\dataset_versions\$DatasetVersion\dataset.csv"
    $failuresPath = "backend\data\dataset_versions\$DatasetVersion\failures.csv"
    $rows = Import-Csv $datasetPath
    $failures = if (Test-Path $failuresPath) { Import-Csv $failuresPath } else { @() }
    $queries = @($rows | Select-Object -ExpandProperty query -Unique)
    $done = "DONE offset=$offset queries=$($queries.Count) rows=$($rows.Count) failures=$($failures.Count) time=$((Get-Date).ToString('o'))"
    $done | Tee-Object -FilePath $StatusPath
}

"FINISHED time=$((Get-Date).ToString('o'))" | Tee-Object -FilePath $StatusPath
