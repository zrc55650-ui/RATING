param(
    [string]$InputPath = "phase2_test.jsonl",
    [string]$TemplatePath = "prm800k_step_classifier.template.html",
    [string]$OutputPath = "prm800k_step_classifier.html",
    [int]$Seed = 800050,
    [int]$SamplesPerRating = 50,
    [string]$ExcludeHtmlPath = ""
)

$ErrorActionPreference = "Stop"

function Get-TextHash([string]$Text) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Shuffle-Array([object[]]$Items, [System.Random]$Random) {
    $copy = @($Items)
    for ($i = $copy.Count - 1; $i -gt 0; $i--) {
        $j = $Random.Next($i + 1)
        $tmp = $copy[$i]
        $copy[$i] = $copy[$j]
        $copy[$j] = $tmp
    }
    return $copy
}

if (-not (Test-Path -LiteralPath $InputPath)) {
    throw "Input dataset not found: $InputPath"
}
if (-not (Test-Path -LiteralPath $TemplatePath)) {
    throw "HTML template not found: $TemplatePath"
}
if ($SamplesPerRating -lt 3) {
    throw "SamplesPerRating must be at least 3"
}

$excludedSourceKeys = @{}
if (-not [string]::IsNullOrWhiteSpace($ExcludeHtmlPath)) {
    if (-not (Test-Path -LiteralPath $ExcludeHtmlPath)) {
        throw "Exclusion HTML not found: $ExcludeHtmlPath"
    }
    $excludeHtml = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $ExcludeHtmlPath))
    $prefix = "const DATA = "
    $suffix = ";`n    const samples = DATA.samples;"
    $jsonStart = $excludeHtml.IndexOf($prefix)
    if ($jsonStart -lt 0) { throw "Could not find embedded DATA in exclusion HTML" }
    $jsonStart += $prefix.Length
    $jsonEnd = $excludeHtml.IndexOf($suffix, $jsonStart)
    if ($jsonEnd -lt 0) { throw "Could not find end of embedded DATA in exclusion HTML" }
    $excludePayload = $excludeHtml.Substring($jsonStart, $jsonEnd - $jsonStart) | ConvertFrom-Json
    foreach ($sample in @($excludePayload.samples)) {
        $excludedSourceKeys["$($sample.source.line)|$($sample.stepIndex)|$($sample.rating)"] = $true
    }
}

$buckets = @{}
foreach ($rating in @(-1, 0, 1)) {
    foreach ($position in @("early", "middle", "late")) {
        $buckets["$rating|$position"] = [System.Collections.Generic.List[object]]::new()
    }
}

$seen = @{}
$lineNumber = 0
Get-Content -LiteralPath $InputPath | ForEach-Object {
    $lineNumber++
    if ([string]::IsNullOrWhiteSpace($_)) { return }

    $row = $_ | ConvertFrom-Json
    if ($row.is_quality_control_question -eq $true -or $row.is_initial_screening_question -eq $true) { return }

    $fullSteps = @($row.question.pre_generated_steps)
    $labeledSteps = @($row.label.steps)
    if ($fullSteps.Count -lt 3) { return }

    $solutionFingerprint = Get-TextHash(($row.question.problem + "`n" + ($fullSteps -join "`n---STEP---`n")))

    for ($stepIndex = 0; $stepIndex -lt $labeledSteps.Count -and $stepIndex -lt $fullSteps.Count; $stepIndex++) {
        $step = $labeledSteps[$stepIndex]
        $completionIndex = -1
        foreach ($completion in @($step.completions)) {
            $completionIndex++
            if ($null -eq $completion.rating) { continue }
            $rating = [int]$completion.rating
            if ($rating -notin @(-1, 0, 1)) { continue }
            if ($completion.flagged -eq $true) { continue }

            # In phase 2, the original labeled trajectory aligns by step index.
            # Alternative completions after the first error are deliberately excluded.
            if ($completion.text -cne $fullSteps[$stepIndex]) { continue }

            $sourceKey = "$lineNumber|$stepIndex|$rating"
            if ($excludedSourceKeys.ContainsKey($sourceKey)) { continue }

            $ratio = $stepIndex / [double]($fullSteps.Count - 1)
            if ($ratio -lt (1.0 / 3.0)) {
                $position = "early"
            }
            elseif ($ratio -lt (2.0 / 3.0)) {
                $position = "middle"
            }
            else {
                $position = "late"
            }

            $dedupeKey = "$solutionFingerprint|$stepIndex|$rating"
            if ($seen.ContainsKey($dedupeKey)) { continue }
            $seen[$dedupeKey] = $true

            $idHash = Get-TextHash("$Seed|$dedupeKey")
            $candidate = [ordered]@{
                id                     = "prm-" + $idHash.Substring(0, 16)
                targetKey              = $solutionFingerprint.Substring(0, 20) + "-$stepIndex-$rating"
                rating                 = $rating
                position               = $position
                positionRatio          = [math]::Round($ratio, 4)
                stepIndex              = $stepIndex
                stepNumber             = $stepIndex + 1
                totalSteps             = $fullSteps.Count
                targetText             = [string]$completion.text
                problem                = [string]$row.question.problem
                groundTruthAnswer      = [string]$row.question.ground_truth_answer
                groundTruthSolution    = [string]$row.question.ground_truth_solution
                preGeneratedAnswer     = [string]$row.question.pre_generated_answer
                finishReason           = [string]$row.label.finish_reason
                generation             = $row.generation
                steps                  = @($fullSteps)
                source                 = [ordered]@{
                    dataset = "OpenAI PRM800K"
                    phase   = 2
                    split   = "test"
                    line    = $lineNumber
                }
            }
            $buckets["$rating|$position"].Add([pscustomobject]$candidate)
        }
    }
}

$baseQuota = [math]::Floor($SamplesPerRating / 3)
$remainder = $SamplesPerRating % 3
$quotas = @{
    early  = $baseQuota + $(if ($remainder -ge 1) { 1 } else { 0 })
    middle = $baseQuota + $(if ($remainder -ge 2) { 1 } else { 0 })
    late   = $baseQuota
}
$random = [System.Random]::new($Seed)
$selected = [System.Collections.Generic.List[object]]::new()
$available = [ordered]@{}

foreach ($rating in @(-1, 0, 1)) {
    foreach ($position in @("early", "middle", "late")) {
        $key = "$rating|$position"
        $pool = @($buckets[$key])
        $available[$key] = $pool.Count
        $need = $quotas[$position]
        if ($pool.Count -lt $need) {
            throw "Not enough candidates for $key (need $need, found $($pool.Count))"
        }
        $shuffled = Shuffle-Array $pool $random
        for ($i = 0; $i -lt $need; $i++) {
            $selected.Add($shuffled[$i])
        }
    }
}

$final = @(Shuffle-Array @($selected) $random)
for ($i = 0; $i -lt $final.Count; $i++) {
    $final[$i] | Add-Member -NotePropertyName displayOrder -NotePropertyValue ($i + 1)
}

$payload = [ordered]@{
    metadata = [ordered]@{
        title               = "PRM800K Step Removability Classification"
        version             = "prm800k-p2test-balanced-v1-n$SamplesPerRating-seed-$Seed"
        seed                = $Seed
        sampleCount         = $final.Count
        createdAt           = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        sourceUrl           = "https://github.com/openai/prm800k"
        mirrorUrl           = "https://huggingface.co/datasets/tasksource/PRM800K"
        samplingDescription = "$SamplesPerRating steps per rating (-1, 0, 1); within each rating: early=$($quotas.early), middle=$($quotas.middle), late=$($quotas.late). Position is stepIndex/(totalSteps-1), split into thirds. Excludes quality-control, initial-screening, flagged, duplicate, non-aligned, excluded prior samples, and trajectories shorter than 3 steps."
        excludedPriorSamples = $excludedSourceKeys.Count
        availableCandidates = $available
    }
    samples = $final
}

$json = $payload | ConvertTo-Json -Depth 12 -Compress
$json = $json.Replace("</script", "<\/script")
$template = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $TemplatePath))
if (-not $template.Contains("__PRM800K_PAYLOAD__")) {
    throw "Template placeholder __PRM800K_PAYLOAD__ was not found"
}
$html = $template.Replace("__PRM800K_PAYLOAD__", $json)
$outputFullPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $OutputPath))
[System.IO.File]::WriteAllText($outputFullPath, $html, [System.Text.UTF8Encoding]::new($false))

Write-Output "Created: $outputFullPath"
Write-Output "Samples: $($final.Count)"
foreach ($rating in @(-1, 0, 1)) {
    $summary = foreach ($position in @("early", "middle", "late")) {
        $count = @($final | Where-Object { $_.rating -eq $rating -and $_.position -eq $position }).Count
        "$position=$count"
    }
    Write-Output "rating=$rating  $($summary -join '  ')"
}
