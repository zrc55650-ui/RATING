param(
    [string]$InputPattern = "qwen_deletion_fast_worker??.jsonl",
    [string]$OutputJsonl = "qwen_deletion_generations.jsonl"
)
$ErrorActionPreference = "Stop"
$files = @(Get-ChildItem -File $InputPattern | Sort-Object Name)
if ($files.Count -lt 1) { throw "No generation shards match $InputPattern" }
$rows = [System.Collections.Generic.List[object]]::new()
foreach ($file in $files) {
    foreach ($line in [IO.File]::ReadAllLines($file.FullName, [Text.Encoding]::UTF8)) {
        if ($line.Trim()) { $rows.Add(($line | ConvertFrom-Json)) }
    }
}
if ($rows.Count -ne 4800) { throw "Expected 4800 rows, found $($rows.Count)" }
$unique = @($rows.taskId | Sort-Object -Unique)
if ($unique.Count -ne 4800) { throw "Expected 4800 unique task IDs, found $($unique.Count)" }
foreach ($run in 1..4) {
    foreach ($condition in @("control", "deleted")) {
        $count = @($rows | Where-Object { $_.run -eq $run -and $_.condition -eq $condition }).Count
        if ($count -ne 600) { throw "Run $run / $condition has $count rows instead of 600" }
    }
}
$writer = [IO.StreamWriter]::new($OutputJsonl, $false, [Text.UTF8Encoding]::new($false))
try {
    foreach ($row in ($rows | Sort-Object run,displayOrder,condition)) { $writer.WriteLine(($row | ConvertTo-Json -Depth 10 -Compress)) }
}
finally { $writer.Dispose() }
[pscustomobject]@{ output=$OutputJsonl; rows=$rows.Count; unique=$unique.Count } | ConvertTo-Json
