param(
    [string]$InputHtml = "prm800k_ai_600_deepseek_v4_pro_reviewed.html",
    [string]$HumanCsv = "human.csv",
    [string]$FilterIdsPath = "blind100_ids.json",
    [string]$OutputJsonl = "blind100_worker.jsonl",
    [string]$Model = "deepseek/deepseek-v4-flash",
    [int]$ShardIndex = 0,
    [int]$ShardCount = 1,
    [int]$BatchSize = 5,
    [int]$Seed = 920026,
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

function Invoke-AnnotationBatch([object[]]$Batch, [int]$BatchNumber, [string]$ExamplesJson) {
    $items = foreach ($sample in $Batch) {
        $numberedSteps = for ($i = 0; $i -lt $sample.steps.Count; $i++) {
            $marker = if ($i -eq [int]$sample.stepIndex) { " [TARGET STEP]" } else { "" }
            "Step $($i + 1)$marker`n$($sample.steps[$i])"
        }
        [ordered]@{
            id = [string]$sample.id
            prm_rating = $sample.rating
            trajectory_position = $sample.position
            problem = $sample.problem
            reasoning_trajectory = ($numberedSteps -join "`n`n")
            ground_truth_answer = $sample.groundTruthAnswer
            ground_truth_solution = $sample.groundTruthSolution
        }
    }

    $systemPrompt = @"
You are an expert annotator of mathematical reasoning steps. Reclassify every test item from scratch. You have no access to, and must not try to infer, any previous model annotation.

The HUMAN-LABELED EXAMPLES below define the intended annotation boundary. Learn their policy, including how concrete errors, merely proposed directions, repeated statements, and necessary calculations are treated. The examples are from a separate sample set and are not test answers.

Apply these output definitions:
1. removable=yes: deleting exactly the target step, while leaving all other steps unchanged, preserves a sufficiently coherent, logically valid derivation with all necessary support for the answer.
2. removable=no: deleting it loses a needed premise, calculation, transition, justification, or conclusion, or leaves later claims unsupported.
3. step_type=essential: a necessary premise, computation, inference, justification, or final conclusion.
4. step_type=redundant: correct or harmless but repetitive, merely restates the task, is empty/meta commentary, or can be deleted without damaging the reasoning.
5. step_type=harmful: mathematically false, misleading, contradictory, irrelevant in a way that derails the solution, or contaminates later reasoning.

The PRM rating is context only and must not determine the label. Analyze the full trajectory and classify only the marked TARGET STEP. For reason, write one or two concise Chinese sentences. Return one annotation for every test id.

HUMAN-LABELED EXAMPLES:
$ExamplesJson
"@

    $schema = [ordered]@{
        type = "object"
        properties = [ordered]@{
            annotations = [ordered]@{
                type = "array"
                minItems = $Batch.Count
                maxItems = $Batch.Count
                items = [ordered]@{
                    type = "object"
                    properties = [ordered]@{
                        id = [ordered]@{ type = "string" }
                        removable = [ordered]@{ type = "string"; enum = @("yes", "no") }
                        step_type = [ordered]@{ type = "string"; enum = @("essential", "redundant", "harmful") }
                        reason = [ordered]@{ type = "string"; minLength = 2 }
                        confidence = [ordered]@{ type = "number"; minimum = 0; maximum = 1 }
                    }
                    required = @("id", "removable", "step_type", "reason", "confidence")
                    additionalProperties = $false
                }
            }
        }
        required = @("annotations")
        additionalProperties = $false
    }

    $request = [ordered]@{
        model = $Model
        messages = @(
            [ordered]@{ role = "system"; content = $systemPrompt },
            [ordered]@{ role = "user"; content = "Classify these blind-test items:`n" + ($items | ConvertTo-Json -Depth 9 -Compress) }
        )
        temperature = 0.1
        seed = $Seed + ($ShardIndex * 1000) + $BatchNumber
        max_tokens = 2600
        reasoning = [ordered]@{ effort = "none" }
        response_format = [ordered]@{
            type = "json_schema"
            json_schema = [ordered]@{ name = "blind_step_annotations"; strict = $true; schema = $schema }
        }
        provider = [ordered]@{ require_parameters = $true }
    }
    $body = $request | ConvertTo-Json -Depth 20 -Compress

    $lastError = ""
    for ($attempt = 1; $attempt -le 8; $attempt++) {
        $requestPath = Join-Path (Get-Location) (".blind-request-" + [guid]::NewGuid().ToString("N") + ".json")
        $responsePath = Join-Path (Get-Location) (".blind-response-" + [guid]::NewGuid().ToString("N") + ".json")
        try {
            [IO.File]::WriteAllText($requestPath, $body, [Text.UTF8Encoding]::new($false))
            $req = $requestPath.Replace("\", "/")
            $res = $responsePath.Replace("\", "/")
            $curlConfig = @"
url = "https://openrouter.ai/api/v1/chat/completions"
request = "POST"
header = "Authorization: Bearer $ApiKey"
header = "Content-Type: application/json; charset=utf-8"
header = "X-Title: PRM800K Human-Calibrated Blind Test"
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
            $parsed = ([string]$response.choices[0].message.content) | ConvertFrom-Json
            $annotations = @($parsed.annotations)
            if ($annotations.Count -ne $Batch.Count) { throw "Expected $($Batch.Count), received $($annotations.Count)" }
            $byId = @{}; foreach ($ann in $annotations) { $byId[[string]$ann.id] = $ann }
            foreach ($item in $Batch) { if (-not $byId.ContainsKey([string]$item.id)) { throw "Missing id $($item.id)" } }
            return [ordered]@{ annotations = $annotations; model = [string]$response.model; usage = $response.usage }
        }
        catch {
            $lastError = $_.Exception.Message
            if ($attempt -lt 8) { Start-Sleep -Seconds ([math]::Min(20, [math]::Pow(2, $attempt))) }
        }
        finally {
            if (Test-Path $requestPath) { Remove-Item -LiteralPath $requestPath -Force }
            if (Test-Path $responsePath) { Remove-Item -LiteralPath $responsePath -Force }
        }
    }
    throw "Batch failed: $lastError"
}

$payload = Read-Payload $InputHtml
$ids = [string[]]([IO.File]::ReadAllText((Resolve-Path -LiteralPath $FilterIdsPath), [Text.Encoding]::UTF8) | ConvertFrom-Json)
$sampleMap = @{}; foreach ($sample in $payload.samples) { $sampleMap[[string]$sample.id] = $sample }
$ordered = foreach ($id in $ids) { if (-not $sampleMap.ContainsKey([string]$id)) { throw "Unknown id $id" }; $sampleMap[[string]$id] }
$samples = @($ordered | Where-Object { (([array]::IndexOf($ids, [string]$_.id)) % $ShardCount) -eq $ShardIndex })

$humanRows = @(Import-Csv -LiteralPath $HumanCsv | Where-Object { $_.complete -eq "true" })
if ($humanRows.Count -ne 75) { throw "Expected 75 completed human examples, found $($humanRows.Count)" }
$examples = @($humanRows | ForEach-Object {
    [ordered]@{
        prm_rating = $_.prm_rating
        trajectory_position = $_.position
        problem = $_.problem
        target_step = $_.target_step
        removable = $_.removable
        step_type = $_.step_type
        reason = $_.reason
    }
})
$examplesJson = $examples | ConvertTo-Json -Depth 7 -Compress

$completed = @{}
if (Test-Path -LiteralPath $OutputJsonl) {
    foreach ($line in [IO.File]::ReadAllLines((Resolve-Path -LiteralPath $OutputJsonl), [Text.Encoding]::UTF8)) {
        if ($line.Trim()) { $row = $line | ConvertFrom-Json; $completed[[string]$row.id] = $true }
    }
}
$pending = @($samples | Where-Object { -not $completed.ContainsKey([string]$_.id) })
$outputPath = if ([IO.Path]::IsPathRooted($OutputJsonl)) {
    [IO.Path]::GetFullPath($OutputJsonl)
}
else {
    [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputJsonl))
}
$stream = [IO.File]::Open($outputPath, [IO.FileMode]::Append, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
$writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
$processed = 0
try {
    for ($offset = 0; $offset -lt $pending.Count; $offset += $BatchSize) {
        $last = [math]::Min($offset + $BatchSize - 1, $pending.Count - 1)
        $batch = @($pending[$offset..$last])
        $result = Invoke-AnnotationBatch $batch ([int]($offset / $BatchSize) + 1) $examplesJson
        foreach ($ann in $result.annotations) {
            $row = [ordered]@{
                id = [string]$ann.id
                removable = [string]$ann.removable
                stepType = [string]$ann.step_type
                reason = [string]$ann.reason
                confidence = [double]$ann.confidence
                model = $result.model
                promptTokens = [long]$result.usage.prompt_tokens
                completionTokens = [long]$result.usage.completion_tokens
                annotatedAt = (Get-Date).ToUniversalTime().ToString("o")
            }
            $writer.WriteLine(($row | ConvertTo-Json -Compress)); $processed++
        }
        $writer.Flush()
        Write-Output "blind_shard=$ShardIndex processed=$processed remaining=$($pending.Count-$processed)"
    }
}
finally { $writer.Dispose() }
Write-Output "blind_shard=$ShardIndex complete total=$($completed.Count+$processed)"
