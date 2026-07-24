param(
    [string]$InputJsonl = "qwen_deletion_generations.jsonl",
    [string]$InputHtml = "prm800k_ai_600_deepseek_v4_pro_reviewed.html",
    [string]$OutputJsonl = "qwen_deletion_judge.jsonl",
    [string]$Model = "qwen/qwen3-8b",
    [int]$ShardIndex = 0,
    [int]$ShardCount = 1,
    [int]$BatchSize = 8,
    [string]$ApiKey = $env:OPENROUTER_API_KEY
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ApiKey)) { throw "OPENROUTER_API_KEY is required" }

function Read-Payload([string]$Path) {
    $html = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path), [Text.Encoding]::UTF8)
    $prefix = "const DATA = "
    $suffix = ";`n    const samples = DATA.samples;"
    $start = $html.IndexOf($prefix)
    if ($start -lt 0) { throw "Embedded DATA not found" }
    $start += $prefix.Length
    $end = $html.IndexOf($suffix, $start)
    if ($end -lt 0) { throw "Embedded DATA end not found" }
    return ($html.Substring($start, $end - $start) | ConvertFrom-Json)
}

function Convert-ResponseContent([string]$Content) {
    $text = $Content.Trim()
    if ($text.StartsWith('```')) {
        $text = $text -replace '^```(?:json)?\s*', ''
        $text = $text -replace '\s*```$', ''
    }
    return ($text | ConvertFrom-Json)
}

function Invoke-QwenJudge([object[]]$Items) {
    $systemPrompt = @"
You are a strict mathematical answer evaluator. For each independent item, decide whether the candidate final answer is mathematically equivalent to the reference answer for the stated problem. Accept algebraically equivalent forms and harmless formatting differences. Reject wrong values, incomplete sets/tuples, missing required units or cases, and answers to a different quantity. Do not infer a missing answer from reasoning: evaluate only candidate_answer. Items are unrelated; never transfer information between them.

Return only one valid JSON object in this exact shape:
{"results":[{"id":"item id","correct":true,"reason":"brief comparison"}]}
Return exactly one result for every input id. /no_think
"@
    $userPrompt = [ordered]@{ items = $Items } | ConvertTo-Json -Depth 8 -Compress
    $request = [ordered]@{
        model = $Model
        messages = @(
            [ordered]@{ role = "system"; content = $systemPrompt },
            [ordered]@{ role = "user"; content = $userPrompt }
        )
        temperature = 0
        top_p = 1
        max_tokens = 2048
        reasoning = [ordered]@{ effort = "none" }
        response_format = [ordered]@{ type = "json_object" }
    }
    $body = $request | ConvertTo-Json -Depth 12 -Compress
    $lastError = ""
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $requestPath = Join-Path (Get-Location) (".qwen-judge-request-" + [guid]::NewGuid().ToString("N") + ".json")
        $responsePath = Join-Path (Get-Location) (".qwen-judge-response-" + [guid]::NewGuid().ToString("N") + ".json")
        try {
            [IO.File]::WriteAllText($requestPath, $body, [Text.UTF8Encoding]::new($false))
            $req = $requestPath.Replace("\", "/")
            $res = $responsePath.Replace("\", "/")
            $curlConfig = @"
url = "https://openrouter.ai/api/v1/chat/completions"
request = "POST"
header = "Authorization: Bearer $ApiKey"
header = "Content-Type: application/json; charset=utf-8"
header = "X-Title: PRM800K Qwen3-8B Deletion Judge"
data-binary = "@$req"
output = "$res"
silent
show-error
fail-with-body
compressed
connect-timeout = 30
max-time = 300
"@
            $curlMessage = ($curlConfig | & curl.exe --config - 2>&1 | Out-String)
            if ($LASTEXITCODE -ne 0) {
                $errorBody = if (Test-Path $responsePath) { [IO.File]::ReadAllText($responsePath, [Text.Encoding]::UTF8) } else { "" }
                throw "curl code $LASTEXITCODE`: $curlMessage $errorBody"
            }
            $response = [IO.File]::ReadAllText($responsePath, [Text.Encoding]::UTF8) | ConvertFrom-Json
            if ($null -ne $response.error) { throw "API error: $($response.error.message)" }
            $content = [string]$response.choices[0].message.content
            if ([string]::IsNullOrWhiteSpace($content)) { throw "Empty response content" }
            $parsed = Convert-ResponseContent $content
            $results = @($parsed.results)
            if ($results.Count -ne $Items.Count) { throw "Expected $($Items.Count) results, received $($results.Count)" }
            $byId = @{}
            foreach ($result in $results) { $byId[[string]$result.id] = $result }
            foreach ($item in $Items) { if (-not $byId.ContainsKey([string]$item.id)) { throw "Missing result id $($item.id)" } }
            return [ordered]@{
                results = $byId
                actualModel = [string]$response.model
                promptTokens = [long]$response.usage.prompt_tokens
                completionTokens = [long]$response.usage.completion_tokens
            }
        }
        catch {
            $lastError = $_.Exception.Message
            if ($attempt -eq 20) { break }
            Start-Sleep -Seconds ([int][math]::Min(30, [math]::Pow(2, [math]::Min(5, $attempt))))
        }
        finally {
            if (Test-Path $requestPath) { Remove-Item -LiteralPath $requestPath -Force }
            if (Test-Path $responsePath) { Remove-Item -LiteralPath $responsePath -Force }
        }
    }
    throw "Judge failed after retries: $lastError"
}

$payload = Read-Payload $InputHtml
$samples = @{}
foreach ($sample in $payload.samples) { $samples[[string]$sample.id] = $sample }
$records = @([IO.File]::ReadAllLines((Resolve-Path -LiteralPath $InputJsonl), [Text.Encoding]::UTF8) | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
$completed = @{}
if (Test-Path -LiteralPath $OutputJsonl) {
    foreach ($line in [IO.File]::ReadAllLines((Resolve-Path -LiteralPath $OutputJsonl), [Text.Encoding]::UTF8)) {
        if ($line.Trim()) { $done = $line | ConvertFrom-Json; $completed[[string]$done.taskId] = $true }
    }
}

$tasks = [System.Collections.Generic.List[object]]::new()
for ($i = 0; $i -lt $records.Count; $i++) {
    if (($i % $ShardCount) -ne $ShardIndex) { continue }
    if (-not $completed.ContainsKey([string]$records[$i].taskId)) { $tasks.Add($records[$i]) }
}

$outputPath = if ([IO.Path]::IsPathRooted($OutputJsonl)) { [IO.Path]::GetFullPath($OutputJsonl) } else { [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputJsonl)) }
$stream = [IO.File]::Open($outputPath, [IO.FileMode]::Append, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
$append = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
$processed = 0
try {
    for ($offset = 0; $offset -lt $tasks.Count;) {
        $apiItems = [System.Collections.Generic.List[object]]::new()
        $batchRecords = [System.Collections.Generic.List[object]]::new()
        while ($offset -lt $tasks.Count -and $apiItems.Count -lt $BatchSize) {
            $record = $tasks[$offset++]
            if ([string]::IsNullOrWhiteSpace([string]$record.finalAnswer)) {
                $auto = [ordered]@{ taskId=[string]$record.taskId; correct=$false; judgeReason="No candidate final answer was produced."; judgeModel="rule:no-answer"; judgedAt=(Get-Date).ToUniversalTime().ToString("o") }
                $append.WriteLine(($auto | ConvertTo-Json -Compress)); $append.Flush(); $processed++
                continue
            }
            $sample = $samples[[string]$record.sampleId]
            $apiItems.Add([ordered]@{ id=[string]$record.taskId; problem=[string]$sample.problem; reference_answer=[string]$record.groundTruthAnswer; candidate_answer=[string]$record.finalAnswer })
            $batchRecords.Add($record)
        }
        if ($apiItems.Count -eq 0) { continue }
        $judged = Invoke-QwenJudge @($apiItems)
        foreach ($record in $batchRecords) {
            $result = $judged.results[[string]$record.taskId]
            $correctValue = if ($result.correct -is [bool]) { [bool]$result.correct } else { ([string]$result.correct).Trim().ToLowerInvariant() -eq "true" }
            $row = [ordered]@{ taskId=[string]$record.taskId; correct=$correctValue; judgeReason=[string]$result.reason; judgeModel=$judged.actualModel; judgeBatchPromptTokens=$judged.promptTokens; judgeBatchCompletionTokens=$judged.completionTokens; judgedAt=(Get-Date).ToUniversalTime().ToString("o") }
            $append.WriteLine(($row | ConvertTo-Json -Compress)); $processed++
        }
        $append.Flush()
        if (($processed % 40) -lt $BatchSize) { Write-Output "judge_shard=$ShardIndex processed=$processed remaining=$($tasks.Count-$processed)" }
    }
}
finally { $append.Dispose() }
Write-Output "judge_shard=$ShardIndex completed_this_run=$processed"
