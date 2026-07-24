param(
    [string]$InputHtml = "prm800k_ai_600_deepseek_v4_flash.html",
    [string]$FilterIdsPath = "prm800k_review185_ids.json",
    [string]$OutputHtml = "prm800k_ai_600_deepseek_v4_pro_reviewed.html",
    [int]$ShardCount = 4
)

$ErrorActionPreference = "Stop"
$html = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $InputHtml), [Text.Encoding]::UTF8)
$prefix = "const DATA = "
$suffix = ";`n    const samples = DATA.samples;"
$start = $html.IndexOf($prefix)
if ($start -lt 0) { throw "Embedded DATA not found" }
$start += $prefix.Length
$end = $html.IndexOf($suffix, $start)
if ($end -lt 0) { throw "Embedded DATA end not found" }
$payload = $html.Substring($start, $end - $start) | ConvertFrom-Json

$filterIds = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $FilterIdsPath), [Text.Encoding]::UTF8) | ConvertFrom-Json
$filterSet = @{}; foreach ($id in $filterIds) { $filterSet[[string]$id] = $true }
if ($filterSet.Count -ne 185) { throw "Expected 185 unique review IDs" }

$reviewed = @{}
$stats = @{ promptTokens = 0L; completionTokens = 0L; totalTokens = 0L; apiCalls = 0L }
for ($shard = 0; $shard -lt $ShardCount; $shard++) {
    $path = "prm800k_review185_pro_annotations.shard{0}.json" -f $shard
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing checkpoint: $path" }
    $doc = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $path), [Text.Encoding]::UTF8) | ConvertFrom-Json
    if ($doc.metadata.model -ne "deepseek/deepseek-v4-pro") { throw "Unexpected model in $path" }
    foreach ($property in $doc.annotations.PSObject.Properties) {
        if (-not $filterSet.ContainsKey($property.Name)) { throw "Checkpoint contains an ID outside the review set" }
        if ($reviewed.ContainsKey($property.Name)) { throw "Duplicate reviewed ID" }
        $reviewed[$property.Name] = $property.Value
    }
    foreach ($name in @("promptTokens", "completionTokens", "totalTokens", "apiCalls")) {
        if ($null -ne $doc.metadata.$name) { $stats[$name] += [long]$doc.metadata.$name }
    }
}
if ($reviewed.Count -ne 185) { throw "Expected 185 reviewed annotations, found $($reviewed.Count)" }

$replaced = 0
foreach ($sample in @($payload.samples)) {
    if (-not $filterSet.ContainsKey([string]$sample.id)) { continue }
    if (-not $reviewed.ContainsKey([string]$sample.id)) { throw "Missing reviewed annotation for $($sample.id)" }
    $annotation = $reviewed[[string]$sample.id]
    $annotation | Add-Member -Force -NotePropertyName reviewedFromModel -NotePropertyValue "deepseek/deepseek-v4-flash"
    $annotation | Add-Member -Force -NotePropertyName isProReview -NotePropertyValue $true
    $sample.aiAnnotation = $annotation
    $replaced++
}
if ($replaced -ne 185) { throw "Replaced $replaced annotations instead of 185" }

$payload.metadata.version = [string]$payload.metadata.version + "-review185-deepseek-v4-pro"
$payload.metadata | Add-Member -Force -NotePropertyName proReview -NotePropertyValue ([ordered]@{
    baseModel = "deepseek/deepseek-v4-flash"
    reviewModel = "deepseek/deepseek-v4-pro"
    reviewedCount = 185
    unchangedCount = 415
    selectionRule = "removable or step_type uncertain; confidence < 0.9; or conservative PRM/type conflict"
    promptTokens = $stats.promptTokens
    completionTokens = $stats.completionTokens
    totalTokens = $stats.totalTokens
    apiCalls = $stats.apiCalls
    mergedAt = (Get-Date).ToUniversalTime().ToString("o")
})

$json = ($payload | ConvertTo-Json -Depth 15 -Compress).Replace("</script", "<\/script")
$result = $html.Substring(0, $start) + $json + $html.Substring($end)
$outputPath = [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputHtml))
[IO.File]::WriteAllText($outputPath, $result, [Text.UTF8Encoding]::new($false))
Write-Output "created=$outputPath"
Write-Output "replaced=$replaced unchanged=415 apiCalls=$($stats.apiCalls) totalTokens=$($stats.totalTokens)"
