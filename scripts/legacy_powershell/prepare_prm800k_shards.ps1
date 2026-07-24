param(
    [string]$InputHtml = "prm800k_ai_600_unlabeled.html",
    [string]$BaseCheckpoint = "prm800k_ai_600_annotations.checkpoint.json",
    [int]$ShardCount = 4,
    [string]$Model = "deepseek/deepseek-v4-flash"
)

$ErrorActionPreference = "Stop"

function Read-Payload([string]$Path) {
    $html = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path))
    $prefix = "const DATA = "
    $suffix = ";`n    const samples = DATA.samples;"
    $start = $html.IndexOf($prefix) + $prefix.Length
    $end = $html.IndexOf($suffix, $start)
    if ($start -lt $prefix.Length -or $end -lt 0) { throw "Embedded DATA not found" }
    return ($html.Substring($start, $end - $start) | ConvertFrom-Json)
}

$payload = Read-Payload $InputHtml
$sampleShard = @{}
foreach ($sample in @($payload.samples)) {
    $sampleShard[$sample.id] = (([int]$sample.displayOrder - 1) % $ShardCount)
}

$baseAnnotations = @{}
$baseStats = @{ promptTokens = 0L; completionTokens = 0L; totalTokens = 0L; apiCalls = 0L }
if (Test-Path -LiteralPath $BaseCheckpoint) {
    $base = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $BaseCheckpoint), [Text.Encoding]::UTF8) | ConvertFrom-Json
    foreach ($property in $base.annotations.PSObject.Properties) { $baseAnnotations[$property.Name] = $property.Value }
    foreach ($name in @("promptTokens", "completionTokens", "totalTokens", "apiCalls")) {
        if ($null -ne $base.metadata.$name) { $baseStats[$name] = [long]$base.metadata.$name }
    }
}

for ($shard = 0; $shard -lt $ShardCount; $shard++) {
    $annotations = [ordered]@{}
    foreach ($id in @($baseAnnotations.Keys | Sort-Object)) {
        if ($sampleShard.ContainsKey($id) -and $sampleShard[$id] -eq $shard) { $annotations[$id] = $baseAnnotations[$id] }
    }
    $stats = if ($shard -eq 0) { $baseStats } else { @{ promptTokens = 0L; completionTokens = 0L; totalTokens = 0L; apiCalls = 0L } }
    $doc = [ordered]@{
        metadata = [ordered]@{
            model = $Model
            seed = 820026
            updatedAt = (Get-Date).ToUniversalTime().ToString("o")
            annotationCount = $annotations.Count
            promptTokens = $stats.promptTokens
            completionTokens = $stats.completionTokens
            totalTokens = $stats.totalTokens
            apiCalls = $stats.apiCalls
            shardIndex = $shard
            shardCount = $ShardCount
        }
        annotations = $annotations
    }
    $path = Join-Path (Get-Location) ("prm800k_ai_600_annotations.shard{0}.json" -f $shard)
    [IO.File]::WriteAllText($path, ($doc | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
    Write-Output "shard=$shard inherited=$($annotations.Count) path=$path"
}

