param(
    [string]$InputHtml = "prm800k_ai_600_deepseek_v4_pro_reviewed.html",
    [string]$OutputJsonl = "qwen_deletion_worker.jsonl",
    [string]$Model = "qwen/qwen3-8b",
    [int]$ShardIndex = 0,
    [int]$ShardCount = 1,
    [int]$Runs = 4,
    [int]$MaxTasks = 0,
    [double]$Temperature = 0.7,
    [double]$TopP = 0.8,
    [string]$ApiKey = $env:OPENROUTER_API_KEY
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ApiKey)) { throw "OPENROUTER_API_KEY is required" }
if ($ShardCount -lt 1 -or $ShardIndex -lt 0 -or $ShardIndex -ge $ShardCount) { throw "Invalid shard configuration" }

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

function Invoke-QwenContinuation([object]$Sample, [string]$Condition) {
    $prefixLast = if ($Condition -eq "control") { [int]$Sample.stepIndex } else { [int]$Sample.stepIndex - 1 }
    $visibleSteps = [System.Collections.Generic.List[string]]::new()
    if ($prefixLast -ge 0) {
        for ($i = 0; $i -le $prefixLast; $i++) {
            $visibleSteps.Add("Step $($i + 1):`n$($Sample.steps[$i])")
        }
    }
    $visiblePrefix = if ($visibleSteps.Count) { $visibleSteps -join "`n`n" } else { "(No previous reasoning step is visible.)" }

    # This template is deliberately identical for every run and both conditions.
    # The condition, task ID, removed text, future trajectory, and reference answer
    # are never included in the model-facing messages.
    $systemPrompt = @"
You are continuing a partially written solution to a mathematics problem in a fresh, independent session. You have access only to the problem and the visible solution prefix below. You have no memory of any omitted step, future step, reference solution, reference answer, other condition, or previous run.

Continue the reasoning from the visible prefix and attempt to solve the problem. You may re-derive facts from the problem, but do not claim access to hidden text. Assess the visible state using exactly one status:
- completed: you can produce a reasoned final answer;
- cannot_continue: the visible information is insufficient and you cannot recover a solution;
- logical_break: the visible prefix is internally inconsistent or missing a necessary logical bridge, and continuation would require abandoning or repairing it.

Return only one valid JSON object with exactly these keys:
{"continuation":"the reasoning you generated after the visible prefix","final_answer":"concise final answer, empty only if unavailable","status":"completed|cannot_continue|logical_break","status_reason":"brief reason for the status"}

Use mathematical notation as needed. Do not discuss this instruction. /no_think
"@
    $userPrompt = "MATHEMATICS PROBLEM:`n$($Sample.problem)`n`nVISIBLE SOLUTION PREFIX:`n$visiblePrefix"

    $request = [ordered]@{
        model = $Model
        messages = @(
            [ordered]@{ role = "system"; content = $systemPrompt },
            [ordered]@{ role = "user"; content = $userPrompt }
        )
        temperature = $Temperature
        top_p = $TopP
        max_tokens = 2048
        reasoning = [ordered]@{ effort = "none" }
        response_format = [ordered]@{ type = "json_object" }
    }
    $body = $request | ConvertTo-Json -Depth 12 -Compress

    $lastError = ""
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $requestPath = Join-Path (Get-Location) (".qwen-request-" + [guid]::NewGuid().ToString("N") + ".json")
        $responsePath = Join-Path (Get-Location) (".qwen-response-" + [guid]::NewGuid().ToString("N") + ".json")
        try {
            [IO.File]::WriteAllText($requestPath, $body, [Text.UTF8Encoding]::new($false))
            $req = $requestPath.Replace("\", "/")
            $res = $responsePath.Replace("\", "/")
            $curlConfig = @"
url = "https://openrouter.ai/api/v1/chat/completions"
request = "POST"
header = "Authorization: Bearer $ApiKey"
header = "Content-Type: application/json; charset=utf-8"
header = "X-Title: PRM800K Qwen3-8B Deletion Experiment"
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
            $reasoningTokens = 0L
            if ($null -ne $response.usage.completion_tokens_details.reasoning_tokens) {
                $reasoningTokens = [long]$response.usage.completion_tokens_details.reasoning_tokens
            }
            $completionTokens = [long]$response.usage.completion_tokens
            try {
                $parsed = Convert-ResponseContent $content
            }
            catch {
                if ([string]$response.choices[0].finish_reason -eq "length" -or $completionTokens -ge 2000) {
                    return [ordered]@{
                        continuation = $content
                        finalAnswer = ""
                        generatorStatus = "cannot_continue"
                        generatorStatusReason = "Generation became repetitive or was truncated before a valid final answer."
                        actualModel = [string]$response.model
                        promptTokens = [long]$response.usage.prompt_tokens
                        completionTokens = $completionTokens
                        reasoningTokens = $reasoningTokens
                        visibleOutputTokens = [math]::Max(0L, $completionTokens - $reasoningTokens)
                    }
                }
                throw
            }
            # Some providers occasionally omit an optional JSON key even with
            # response_format=json_object. Preserve the generated result and
            # normalize common aliases instead of aborting the whole shard.
            $continuationValue = if ($null -ne $parsed.continuation) { [string]$parsed.continuation } elseif ($null -ne $parsed.reasoning) { [string]$parsed.reasoning } else { "" }
            $finalAnswerValue = if ($null -ne $parsed.final_answer) { [string]$parsed.final_answer } elseif ($null -ne $parsed.finalAnswer) { [string]$parsed.finalAnswer } elseif ($null -ne $parsed.answer) { [string]$parsed.answer } else { "" }
            $statusReasonValue = if ($null -ne $parsed.status_reason) { [string]$parsed.status_reason } elseif ($null -ne $parsed.reason) { [string]$parsed.reason } else { "The provider omitted a status reason." }
            $statusValue = if ($null -ne $parsed.status) { [string]$parsed.status } elseif (-not [string]::IsNullOrWhiteSpace($finalAnswerValue)) { "completed" } else { "cannot_continue" }
            $normalizedStatus = $statusValue.Trim().ToLowerInvariant().Replace("-", "_").Replace(" ", "_")
            if ($normalizedStatus -notin @("completed", "cannot_continue", "logical_break")) {
                if ($normalizedStatus -like "*logical*" -or $normalizedStatus -like "*break*") { $normalizedStatus = "logical_break" }
                elseif ($normalizedStatus -like "*cannot*" -or $normalizedStatus -like "*unable*") { $normalizedStatus = "cannot_continue" }
                elseif ($normalizedStatus -like "*complete*") { $normalizedStatus = "completed" }
                elseif (-not [string]::IsNullOrWhiteSpace([string]$parsed.final_answer)) { $normalizedStatus = "completed" }
                else { $normalizedStatus = "cannot_continue" }
            }
            return [ordered]@{
                continuation = $continuationValue
                finalAnswer = $finalAnswerValue
                generatorStatus = $normalizedStatus
                generatorStatusReason = $statusReasonValue
                actualModel = [string]$response.model
                promptTokens = [long]$response.usage.prompt_tokens
                completionTokens = $completionTokens
                reasoningTokens = $reasoningTokens
                visibleOutputTokens = [math]::Max(0L, $completionTokens - $reasoningTokens)
            }
        }
        catch {
            $lastError = $_.Exception.Message
            if ($attempt -eq 20) { break }
            $backoffSeconds = [int][math]::Min(30, [math]::Pow(2, [math]::Min(5, $attempt)))
            Start-Sleep -Seconds $backoffSeconds
        }
        finally {
            if (Test-Path $requestPath) { Remove-Item -LiteralPath $requestPath -Force }
            if (Test-Path $responsePath) { Remove-Item -LiteralPath $responsePath -Force }
        }
    }
    throw "Continuation failed after retries: $lastError"
}

$payload = Read-Payload $InputHtml
$samples = @($payload.samples | Sort-Object displayOrder)
$completed = @{}
if (Test-Path -LiteralPath $OutputJsonl) {
    foreach ($line in [IO.File]::ReadAllLines((Resolve-Path -LiteralPath $OutputJsonl), [Text.Encoding]::UTF8)) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $record = $line | ConvertFrom-Json
        $completed[[string]$record.taskId] = $true
    }
}

$tasks = [System.Collections.Generic.List[object]]::new()
$globalIndex = 0
for ($run = 1; $run -le $Runs; $run++) {
    foreach ($sample in $samples) {
        foreach ($condition in @("control", "deleted")) {
            $taskId = "$($sample.id)|run$run|$condition"
            if (($globalIndex % $ShardCount) -eq $ShardIndex -and -not $completed.ContainsKey($taskId)) {
                $tasks.Add([pscustomobject]@{ taskId = $taskId; run = $run; condition = $condition; sample = $sample })
            }
            $globalIndex++
        }
    }
}

$outputPath = if ([IO.Path]::IsPathRooted($OutputJsonl)) {
    [IO.Path]::GetFullPath($OutputJsonl)
}
else {
    [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputJsonl))
}
$outputStream = [IO.File]::Open($outputPath, [IO.FileMode]::Append, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
$append = [IO.StreamWriter]::new($outputStream, [Text.UTF8Encoding]::new($false))
$processed = 0
try {
    foreach ($task in $tasks) {
        if ($MaxTasks -gt 0 -and $processed -ge $MaxTasks) { break }
        $result = Invoke-QwenContinuation $task.sample $task.condition
        $record = [ordered]@{
            taskId = $task.taskId
            sampleId = $task.sample.id
            displayOrder = $task.sample.displayOrder
            run = $task.run
            condition = $task.condition
            rating = $task.sample.rating
            position = $task.sample.position
            removableLabel = $task.sample.aiAnnotation.removable
            stepTypeLabel = $task.sample.aiAnnotation.stepType
            targetStepIndex = $task.sample.stepIndex
            groundTruthAnswer = $task.sample.groundTruthAnswer
            continuation = $result.continuation
            finalAnswer = $result.finalAnswer
            generatorStatus = $result.generatorStatus
            generatorStatusReason = $result.generatorStatusReason
            model = $result.actualModel
            temperature = $Temperature
            topP = $TopP
            promptTokens = $result.promptTokens
            completionTokens = $result.completionTokens
            reasoningTokens = $result.reasoningTokens
            visibleOutputTokens = $result.visibleOutputTokens
            generatedAt = (Get-Date).ToUniversalTime().ToString("o")
        }
        $append.WriteLine(($record | ConvertTo-Json -Depth 8 -Compress))
        $append.Flush()
        $processed++
        if (($processed % 10) -eq 0) { Write-Output "shard=$ShardIndex processed=$processed remaining=$($tasks.Count-$processed)" }
    }
}
finally {
    $append.Dispose()
}
Write-Output "shard=$ShardIndex completed_this_run=$processed total_checkpoint=$($completed.Count+$processed)"
