param(
    [string]$InputHtml = "prm800k_ai_600_unlabeled.html",
    [string]$OutputHtml = "prm800k_ai_600_deepseek_v4_flash.html",
    [int]$ShardCount = 4
)

$ErrorActionPreference = "Stop"
$html = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $InputHtml))
$prefix = "const DATA = "
$suffix = ";`n    const samples = DATA.samples;"
$start = $html.IndexOf($prefix)
if ($start -lt 0) { throw "Embedded DATA not found" }
$start += $prefix.Length
$end = $html.IndexOf($suffix, $start)
if ($end -lt 0) { throw "Embedded DATA end not found" }
$payload = $html.Substring($start, $end - $start) | ConvertFrom-Json

$annotations = @{}
$stats = @{ promptTokens = 0L; completionTokens = 0L; totalTokens = 0L; apiCalls = 0L }
for ($shard = 0; $shard -lt $ShardCount; $shard++) {
    $path = "prm800k_ai_600_annotations.shard{0}.json" -f $shard
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing shard checkpoint: $path" }
    $doc = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $path), [Text.Encoding]::UTF8) | ConvertFrom-Json
    foreach ($property in $doc.annotations.PSObject.Properties) {
        if ($annotations.ContainsKey($property.Name)) { throw "Duplicate annotation across shards: $($property.Name)" }
        $annotations[$property.Name] = $property.Value
    }
    foreach ($name in @("promptTokens", "completionTokens", "totalTokens", "apiCalls")) {
        if ($null -ne $doc.metadata.$name) { $stats[$name] += [long]$doc.metadata.$name }
    }
}

$missing = [System.Collections.Generic.List[string]]::new()
foreach ($sample in @($payload.samples)) {
    if (-not $annotations.ContainsKey($sample.id)) {
        $missing.Add([string]$sample.id)
        continue
    }
    $sample | Add-Member -Force -NotePropertyName aiAnnotation -NotePropertyValue $annotations[$sample.id]
}
if ($missing.Count -gt 0) { throw "Missing $($missing.Count) annotations; first missing id: $($missing[0])" }
if ($annotations.Count -ne $payload.samples.Count) { throw "Annotation count does not match sample count" }

$payload.metadata | Add-Member -Force -NotePropertyName aiAnnotation -NotePropertyValue ([ordered]@{
    requestedModel = "deepseek/deepseek-v4-flash"
    annotationCount = $annotations.Count
    completed = $true
    promptTokens = $stats.promptTokens
    completionTokens = $stats.completionTokens
    totalTokens = $stats.totalTokens
    apiCalls = $stats.apiCalls
    shardCount = $ShardCount
    generatedAt = (Get-Date).ToUniversalTime().ToString("o")
})
$payload.metadata.version = [string]$payload.metadata.version + "-ai-deepseek-v4-flash"

$json = ($payload | ConvertTo-Json -Depth 15 -Compress).Replace("</script", "<\/script")
$result = $html.Substring(0, $start) + $json + $html.Substring($end)
$outputPath = [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputHtml))
[IO.File]::WriteAllText($outputPath, $result, [Text.UTF8Encoding]::new($false))
Write-Output "created=$outputPath"
Write-Output "annotations=$($annotations.Count) apiCalls=$($stats.apiCalls) totalTokens=$($stats.totalTokens)"
