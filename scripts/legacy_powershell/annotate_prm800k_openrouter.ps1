param(
    [string]$InputHtml = "prm800k_ai_600_unlabeled.html",
    [string]$OutputHtml = "prm800k_ai_600_deepseek_v4_flash.html",
    [string]$CheckpointPath = "prm800k_ai_600_annotations.checkpoint.json",
    [string]$Model = "deepseek/deepseek-v4-flash",
    [int]$BatchSize = 6,
    [int]$MaxBatches = 0,
    [int]$Seed = 820026,
    [int]$ShardIndex = 0,
    [int]$ShardCount = 1,
    [string]$FilterIdsPath = "",
    [string]$ApiKey = $env:OPENROUTER_API_KEY
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "Set OPENROUTER_API_KEY in the process environment. The key is never written to output files."
}
if (-not (Test-Path -LiteralPath $InputHtml)) { throw "Input HTML not found: $InputHtml" }
if ($BatchSize -lt 1 -or $BatchSize -gt 12) { throw "BatchSize must be between 1 and 12" }
if ($ShardCount -lt 1 -or $ShardIndex -lt 0 -or $ShardIndex -ge $ShardCount) { throw "Invalid shard configuration" }

function Read-EmbeddedPayload([string]$Path) {
    $html = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path))
    $prefix = "const DATA = "
    $suffix = ";`n    const samples = DATA.samples;"
    $start = $html.IndexOf($prefix)
    if ($start -lt 0) { throw "Could not find embedded DATA in $Path" }
    $start += $prefix.Length
    $end = $html.IndexOf($suffix, $start)
    if ($end -lt 0) { throw "Could not find end of embedded DATA in $Path" }
    return [ordered]@{
        html = $html
        prefix = $prefix
        suffix = $suffix
        jsonStart = $start
        jsonEnd = $end
        payload = ($html.Substring($start, $end - $start) | ConvertFrom-Json)
    }
}

function Save-Checkpoint([hashtable]$Annotations, [hashtable]$Stats) {
    $orderedAnnotations = [ordered]@{}
    foreach ($key in @($Annotations.Keys | Sort-Object)) {
        $orderedAnnotations[$key] = $Annotations[$key]
    }
    $doc = [ordered]@{
        metadata = [ordered]@{
            model = $Model
            seed = $Seed
            updatedAt = (Get-Date).ToUniversalTime().ToString("o")
            annotationCount = $Annotations.Count
            promptTokens = $Stats.promptTokens
            completionTokens = $Stats.completionTokens
            totalTokens = $Stats.totalTokens
            apiCalls = $Stats.apiCalls
        }
        annotations = $orderedAnnotations
    }
    [System.IO.File]::WriteAllText(
        [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $CheckpointPath)),
        ($doc | ConvertTo-Json -Depth 10),
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Invoke-AnnotationBatch([object[]]$Batch, [int]$BatchNumber) {
    $items = foreach ($sample in $Batch) {
        $numberedSteps = for ($i = 0; $i -lt $sample.steps.Count; $i++) {
            $marker = if ($i -eq [int]$sample.stepIndex) { " [TARGET STEP]" } else { "" }
            "Step $($i + 1)$marker`n$($sample.steps[$i])"
        }
        [ordered]@{
            id = $sample.id
            prm_rating = $sample.rating
            trajectory_position = $sample.position
            problem = $sample.problem
            reasoning_trajectory = ($numberedSteps -join "`n`n")
            ground_truth_answer = $sample.groundTruthAnswer
            ground_truth_solution = $sample.groundTruthSolution
        }
    }

    $systemPrompt = @"
You are an expert annotator of mathematical reasoning steps. Classify only the marked TARGET STEP for every item.

Apply these definitions consistently:
1. removable=yes: deleting exactly the target step, while leaving all other steps unchanged, preserves a sufficiently coherent, logically valid derivation with all necessary support for the answer.
2. removable=no: deleting it loses a needed premise, calculation, transition, justification, or conclusion, or leaves later claims unsupported.
3. removable=uncertain: use only when the deletion effect is genuinely ambiguous.
4. step_type=essential: a necessary premise, computation, inference, justification, or final conclusion.
5. step_type=redundant: correct or harmless but repetitive, merely restates the task, is empty/meta commentary, or can be deleted without damaging the reasoning.
6. step_type=harmful: mathematically false, misleading, contradictory, irrelevant in a way that derails the solution, or contaminates later reasoning.
7. step_type=uncertain: the role or correctness cannot be determined reliably.

Essential usually pairs with removable=no, and redundant usually pairs with removable=yes. Harmful can pair with yes or no depending on whether deleting only that step repairs the remaining trajectory. The supplied PRM rating is context, not the answer, and must not override your own analysis.

For reason, write one or two concise Chinese sentences identifying the concrete information, inference, repetition, or error and the effect of deleting it. Confidence is your calibrated probability from 0 to 1 that the removable label, step_type, and reason are all correct. Lower confidence for ambiguous dependencies or difficult mathematics. Return exactly one annotation for every provided id.
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
                        removable = [ordered]@{ type = "string"; enum = @("yes", "no", "uncertain") }
                        step_type = [ordered]@{ type = "string"; enum = @("essential", "redundant", "harmful", "uncertain") }
                        reason = [ordered]@{ type = "string"; minLength = 4 }
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
            [ordered]@{ role = "user"; content = "Annotate this JSON array:`n" + ($items | ConvertTo-Json -Depth 8 -Compress) }
        )
        temperature = 0.1
        seed = $Seed + $BatchNumber
        max_tokens = 2600
        reasoning = [ordered]@{ effort = "none" }
        response_format = [ordered]@{
            type = "json_schema"
            json_schema = [ordered]@{ name = "step_annotations"; strict = $true; schema = $schema }
        }
        provider = [ordered]@{ require_parameters = $true }
    }

    $headers = @{
        Authorization = "Bearer $ApiKey"
        "X-Title" = "PRM800K Step Removability Annotation"
    }
    $body = $request | ConvertTo-Json -Depth 20 -Compress

    $lastError = ""
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $requestTempPath = Join-Path (Get-Location) (".openrouter-request-" + [guid]::NewGuid().ToString("N") + ".json")
        $responseTempPath = Join-Path (Get-Location) (".openrouter-response-" + [guid]::NewGuid().ToString("N") + ".json")
        try {
            [System.IO.File]::WriteAllText($requestTempPath, $body, [System.Text.UTF8Encoding]::new($false))
            # Feed the authorization header to curl over stdin so the API key is not
            # placed in curl's command-line arguments or written to a config file.
            $escapedRequestPath = $requestTempPath.Replace("\", "/")
            $escapedResponsePath = $responseTempPath.Replace("\", "/")
            $curlConfig = @"
url = "https://openrouter.ai/api/v1/chat/completions"
request = "POST"
header = "Authorization: Bearer $ApiKey"
header = "Content-Type: application/json; charset=utf-8"
header = "X-Title: PRM800K Step Removability Annotation"
data-binary = "@$escapedRequestPath"
output = "$escapedResponsePath"
silent
show-error
fail-with-body
compressed
connect-timeout = 30
max-time = 240
"@
            $curlMessage = ($curlConfig | & curl.exe --config - 2>&1 | Out-String)
            if ($LASTEXITCODE -ne 0) {
                $errorBody = if (Test-Path -LiteralPath $responseTempPath) { [System.IO.File]::ReadAllText($responseTempPath, [System.Text.Encoding]::UTF8) } else { "" }
                throw "curl exited with code $LASTEXITCODE`: $curlMessage $errorBody"
            }
            $rawResponse = [System.IO.File]::ReadAllText($responseTempPath, [System.Text.Encoding]::UTF8)
            $response = $rawResponse | ConvertFrom-Json
            if ($null -ne $response.error) { throw "API error: $($response.error.message)" }
            $content = [string]$response.choices[0].message.content
            if ([string]::IsNullOrWhiteSpace($content)) { throw "Model returned empty content" }
            $parsed = $content | ConvertFrom-Json
            $returned = @($parsed.annotations)
            if ($returned.Count -ne $Batch.Count) { throw "Expected $($Batch.Count) annotations, received $($returned.Count)" }

            $expectedIds = @{}; foreach ($sample in $Batch) { $expectedIds[$sample.id] = $true }
            $seenIds = @{}
            foreach ($ann in $returned) {
                if (-not $expectedIds.ContainsKey([string]$ann.id)) { throw "Unexpected annotation id" }
                if ($seenIds.ContainsKey([string]$ann.id)) { throw "Duplicate annotation id" }
                $seenIds[[string]$ann.id] = $true
                if ([string]$ann.removable -notin @("yes", "no", "uncertain")) { throw "Invalid removable value" }
                if ([string]$ann.step_type -notin @("essential", "redundant", "harmful", "uncertain")) { throw "Invalid step_type value" }
                $confidence = [double]$ann.confidence
                if ($confidence -lt 0 -or $confidence -gt 1) { throw "Confidence outside [0,1]" }
                if ([string]::IsNullOrWhiteSpace([string]$ann.reason)) { throw "Empty reason" }
            }
            return [ordered]@{ annotations = $returned; usage = $response.usage; actualModel = [string]$response.model }
        }
        catch {
            $lastError = $_.Exception.Message
            if ($attempt -eq 5) { break }
            $delay = @(2, 5, 10, 20)[$attempt - 1]
            Write-Output "Batch $BatchNumber attempt $attempt failed; retrying in ${delay}s."
            Start-Sleep -Seconds $delay
        }
        finally {
            if (Test-Path -LiteralPath $requestTempPath) { Remove-Item -LiteralPath $requestTempPath -Force }
            if (Test-Path -LiteralPath $responseTempPath) { Remove-Item -LiteralPath $responseTempPath -Force }
        }
    }
    throw "Batch $BatchNumber failed after retries: $lastError"
}

$embedded = Read-EmbeddedPayload $InputHtml
$payload = $embedded.payload
$allSamples = @($payload.samples | Sort-Object displayOrder)
if (-not [string]::IsNullOrWhiteSpace($FilterIdsPath)) {
    if (-not (Test-Path -LiteralPath $FilterIdsPath)) { throw "Filter ID file not found: $FilterIdsPath" }
    $filterIds = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $FilterIdsPath), [Text.Encoding]::UTF8) | ConvertFrom-Json
    $filterSet = @{}; foreach ($id in $filterIds) { $filterSet[[string]$id] = $true }
    $allSamples = @($allSamples | Where-Object { $filterSet.ContainsKey([string]$_.id) })
    if ($allSamples.Count -ne $filterSet.Count) { throw "Some filter IDs were not found in the input HTML" }
}
$samples = @($allSamples | Where-Object { (([int]$_.displayOrder - 1) % $ShardCount) -eq $ShardIndex })
$annotations = @{}
$stats = @{ promptTokens = 0L; completionTokens = 0L; totalTokens = 0L; apiCalls = 0L }

if (Test-Path -LiteralPath $CheckpointPath) {
    $checkpoint = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $CheckpointPath), [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    if ($checkpoint.metadata.model -ne $Model) { throw "Checkpoint model does not match requested model" }
    foreach ($property in $checkpoint.annotations.PSObject.Properties) {
        $annotations[$property.Name] = $property.Value
    }
    foreach ($name in @("promptTokens", "completionTokens", "totalTokens", "apiCalls")) {
        if ($null -ne $checkpoint.metadata.$name) { $stats[$name] = [long]$checkpoint.metadata.$name }
    }
    Write-Output "Shard $($ShardIndex + 1)/$ShardCount resuming from checkpoint with $($annotations.Count) annotations."
}

$pending = @($samples | Where-Object { -not $annotations.ContainsKey($_.id) })
$batchNumber = 0
$processedThisRun = 0
for ($offset = 0; $offset -lt $pending.Count; $offset += $BatchSize) {
    if ($MaxBatches -gt 0 -and $batchNumber -ge $MaxBatches) { break }
    $batchNumber++
    $last = [math]::Min($offset + $BatchSize - 1, $pending.Count - 1)
    $batch = @($pending[$offset..$last])
    $result = Invoke-AnnotationBatch $batch $batchNumber
    $annotatedAt = (Get-Date).ToUniversalTime().ToString("o")
    foreach ($ann in @($result.annotations)) {
        $annotations[[string]$ann.id] = [ordered]@{
            removable = [string]$ann.removable
            stepType = [string]$ann.step_type
            reason = [string]$ann.reason
            confidence = [math]::Round([double]$ann.confidence, 4)
            model = $(if ([string]::IsNullOrWhiteSpace($result.actualModel)) { $Model } else { $result.actualModel })
            annotatedAt = $annotatedAt
        }
        $processedThisRun++
    }
    $stats.apiCalls++
    if ($null -ne $result.usage) {
        $stats.promptTokens += [long]$result.usage.prompt_tokens
        $stats.completionTokens += [long]$result.usage.completion_tokens
        $stats.totalTokens += [long]$result.usage.total_tokens
    }
    Save-Checkpoint $annotations $stats
    Write-Output "Shard $($ShardIndex + 1)/$ShardCount progress: $($annotations.Count)/$($samples.Count); API calls=$($stats.apiCalls); tokens=$($stats.totalTokens)"
}

foreach ($sample in $samples) {
    if ($annotations.ContainsKey($sample.id)) {
        if ($sample.PSObject.Properties.Name -contains "aiAnnotation") {
            $sample.aiAnnotation = $annotations[$sample.id]
        }
        else {
            $sample | Add-Member -NotePropertyName aiAnnotation -NotePropertyValue $annotations[$sample.id]
        }
    }
}
$payload.metadata | Add-Member -Force -NotePropertyName aiAnnotation -NotePropertyValue ([ordered]@{
    requestedModel = $Model
    annotationCount = $annotations.Count
    completed = ($annotations.Count -eq $samples.Count)
    shardIndex = $ShardIndex
    shardCount = $ShardCount
    promptTokens = $stats.promptTokens
    completionTokens = $stats.completionTokens
    totalTokens = $stats.totalTokens
    apiCalls = $stats.apiCalls
    generatedAt = (Get-Date).ToUniversalTime().ToString("o")
})

$newJson = $payload | ConvertTo-Json -Depth 15 -Compress
$newJson = $newJson.Replace("</script", "<\/script")
$newHtml = $embedded.html.Substring(0, $embedded.jsonStart) + $newJson + $embedded.html.Substring($embedded.jsonEnd)
[System.IO.File]::WriteAllText(
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputHtml)),
    $newHtml,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Output "Wrote: $([System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputHtml)))"
Write-Output "Completed annotations: $($annotations.Count)/$($samples.Count)"
Write-Output "Processed this run: $processedThisRun"
