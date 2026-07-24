param(
    [string]$PairsCsv = "qwen3-8b_deletion_pairs.csv",
    [string]$GenerationPattern = "qwen_placebo_worker??.jsonl",
    [string]$JudgePattern = "qwen_placebo_judge??.jsonl",
    [string]$OutputStem = "qwen3-8b_placebo_effects_5000",
    [int]$Replicates = 5000,
    [int]$Seed = 20260722
)

$ErrorActionPreference = "Stop"

function Read-JsonlFiles([IO.FileInfo[]]$Files) {
    $rows = [Collections.Generic.List[object]]::new()
    foreach ($file in $Files) {
        foreach ($line in [IO.File]::ReadAllLines($file.FullName, [Text.Encoding]::UTF8)) {
            if ($line.Trim()) { $rows.Add(($line | ConvertFrom-Json)) }
        }
    }
    return @($rows)
}

$generationFiles = @(Get-ChildItem -File $GenerationPattern | Sort-Object Name)
$judgeFiles = @(Get-ChildItem -File $JudgePattern | Sort-Object Name)
if ($generationFiles.Count -ne 32) { throw "Expected 32 generation shards, found $($generationFiles.Count)." }
if ($judgeFiles.Count -ne 32) { throw "Expected 32 judge shards, found $($judgeFiles.Count)." }

$generations = Read-JsonlFiles $generationFiles
$judgments = Read-JsonlFiles $judgeFiles
if ($generations.Count -ne 1514 -or @($generations.taskId | Sort-Object -Unique).Count -ne 1514) {
    throw "Expected 1514 unique Placebo generations."
}
if ($judgments.Count -ne 1514 -or @($judgments.taskId | Sort-Object -Unique).Count -ne 1514) {
    throw "Expected 1514 unique Placebo judgments."
}

$judgeByTask = @{}
foreach ($judgment in $judgments) { $judgeByTask[[string]$judgment.taskId] = $judgment }
$placeboResults = [Collections.Generic.List[object]]::new()
foreach ($generation in $generations) {
    $judgment = $judgeByTask[[string]$generation.taskId]
    if ($null -eq $judgment) { throw "Missing judgment for $($generation.taskId)." }
    $placeboResults.Add([pscustomobject][ordered]@{
        taskId = [string]$generation.taskId
        sampleId = [string]$generation.sampleId
        displayOrder = [int]$generation.displayOrder
        placeboOrder = [int]$generation.placeboOrder
        placeboStepIndex = [int]$generation.placeboStepIndex
        placeboStepTokens = [int]$generation.placeboStepTokens
        targetStepIndex = [int]$generation.targetStepIndex
        targetStepTokens = [int]$generation.targetStepTokens
        lengthRatio = [double]$generation.lengthRatio
        rating = [int]$generation.rating
        position = [string]$generation.position
        stepTypeLabel = [string]$generation.stepTypeLabel
        placeboCorrect = [bool]$judgment.correct
        finalAnswer = [string]$generation.finalAnswer
        groundTruthAnswer = [string]$generation.groundTruthAnswer
        generatorStatus = [string]$generation.generatorStatus
        visibleOutputTokens = [long]$generation.visibleOutputTokens
        judgeReason = [string]$judgment.judgeReason
        judgeModel = [string]$judgment.judgeModel
    })
}
$placeboResults | Sort-Object displayOrder, placeboOrder |
    Export-Csv -LiteralPath "$OutputStem`_placebo_runs.csv" -NoTypeInformation -Encoding UTF8

$pairRows = @(Import-Csv -LiteralPath $PairsCsv)
$pairGroups = @($pairRows | Group-Object sampleId)
if ($pairRows.Count -ne 2400 -or $pairGroups.Count -ne 600 -or @($pairGroups | Where-Object Count -ne 4).Count -ne 0) {
    throw "Pairs CSV must contain 600 target steps with four runs each."
}
$pairsBySample = @{}
foreach ($group in $pairGroups) { $pairsBySample[[string]$group.Name] = @($group.Group) }

$stepEffects = [Collections.Generic.List[object]]::new()
foreach ($placeboGroup in @($placeboResults | Group-Object sampleId | Sort-Object Name)) {
    $sampleId = [string]$placeboGroup.Name
    $pairs = $pairsBySample[$sampleId]
    if ($null -eq $pairs -or $pairs.Count -ne 4) { throw "Missing four original runs for $sampleId." }
    $placebos = @($placeboGroup.Group)
    if ($placebos.Count -lt 1 -or $placebos.Count -gt 4) { throw "Invalid Placebo count for $sampleId." }

    $controlAverage = @($pairs | Where-Object controlCorrect -eq "True").Count / 4.0
    $targetAverage = @($pairs | Where-Object deletedCorrect -eq "True").Count / 4.0
    $placeboAverage = @($placebos | Where-Object placeboCorrect -eq $true).Count / [double]$placebos.Count
    $first = $pairs[0]
    $stepEffects.Add([pscustomobject][ordered]@{
        sampleId = $sampleId
        rating = [int]$first.rating
        stepTypeLabel = [string]$first.stepTypeLabel
        position = [string]$first.position
        placeboRuns = $placebos.Count
        placeboCorrect = @($placebos | Where-Object placeboCorrect -eq $true).Count
        controlAvgCorrect = $controlAverage
        targetAvgCorrect = $targetAverage
        placeboAvgCorrect = $placeboAverage
        targetEffect = $targetAverage - $controlAverage
        placeboEffect = $placeboAverage - $controlAverage
        pureSemanticEffect = $targetAverage - $placeboAverage
    })
}
if ($stepEffects.Count -ne 511) { throw "Expected 511 eligible target steps, found $($stepEffects.Count)." }
$stepEffects | Sort-Object sampleId |
    Export-Csv -LiteralPath "$OutputStem`_step_effects.csv" -NoTypeInformation -Encoding UTF8

$groupDefinitions = @(
    [pscustomobject]@{ Name = "Overall"; Predicate = { param($row) $true } },
    [pscustomobject]@{ Name = "rating=-1"; Predicate = { param($row) $row.rating -eq -1 } },
    [pscustomobject]@{ Name = "rating=0"; Predicate = { param($row) $row.rating -eq 0 } },
    [pscustomobject]@{ Name = "rating=1"; Predicate = { param($row) $row.rating -eq 1 } },
    [pscustomobject]@{ Name = "step_type=Harmful"; Predicate = { param($row) $row.stepTypeLabel -eq "harmful" } },
    [pscustomobject]@{ Name = "rating=-1 x step_type=Harmful"; Predicate = { param($row) $row.rating -eq -1 -and $row.stepTypeLabel -eq "harmful" } }
)

$groupRows = [Collections.Generic.List[object]]::new()
$effectMatrix = [Collections.Generic.List[double[]]]::new()
foreach ($definition in $groupDefinitions) {
    $rows = @($stepEffects | Where-Object { & $definition.Predicate $_ })
    if ($rows.Count -eq 0) { throw "Group has no eligible steps: $($definition.Name)." }
    $groupRows.Add([pscustomobject]@{
        Name = $definition.Name
        TargetSteps = $rows.Count
        PlaceboRuns = [int](($rows.placeboRuns | Measure-Object -Sum).Sum)
    })
    $flat = [double[]]::new(3 * $rows.Count)
    for ($i = 0; $i -lt $rows.Count; $i++) {
        $flat[3 * $i] = [double]$rows[$i].targetEffect
        $flat[(3 * $i) + 1] = [double]$rows[$i].placeboEffect
        $flat[(3 * $i) + 2] = [double]$rows[$i].pureSemanticEffect
    }
    $effectMatrix.Add($flat)
}

$csharp = @'
using System;
using System.Collections.Generic;

public sealed class PlaceboBootstrapResult
{
    public int GroupIndex { get; set; }
    public int EffectIndex { get; set; }
    public double PointEstimate { get; set; }
    public double Lower { get; set; }
    public double Upper { get; set; }
}

public static class PlaceboEffectBootstrapEngine
{
    private static double Quantile(double[] values, double probability)
    {
        Array.Sort(values);
        double position = (values.Length - 1) * probability;
        int lowerIndex = (int)Math.Floor(position);
        int upperIndex = (int)Math.Ceiling(position);
        if (lowerIndex == upperIndex) return values[lowerIndex];
        double fraction = position - lowerIndex;
        return values[lowerIndex] + fraction * (values[upperIndex] - values[lowerIndex]);
    }

    public static PlaceboBootstrapResult[] Run(int replicates, int seed, double[][] groups)
    {
        var random = new Random(seed);
        var results = new List<PlaceboBootstrapResult>();
        for (int groupIndex = 0; groupIndex < groups.Length; groupIndex++)
        {
            double[] flat = groups[groupIndex];
            int stepCount = flat.Length / 3;
            var point = new double[3];
            for (int step = 0; step < stepCount; step++)
                for (int effect = 0; effect < 3; effect++)
                    point[effect] += flat[(3 * step) + effect] / stepCount;

            var bootstrap = new double[3, replicates];
            for (int replicate = 0; replicate < replicates; replicate++)
            {
                for (int draw = 0; draw < stepCount; draw++)
                {
                    int sampledStep = random.Next(stepCount);
                    for (int effect = 0; effect < 3; effect++)
                        bootstrap[effect, replicate] += flat[(3 * sampledStep) + effect] / stepCount;
                }
            }
            for (int effect = 0; effect < 3; effect++)
            {
                var values = new double[replicates];
                for (int replicate = 0; replicate < replicates; replicate++)
                    values[replicate] = bootstrap[effect, replicate];
                results.Add(new PlaceboBootstrapResult {
                    GroupIndex = groupIndex,
                    EffectIndex = effect,
                    PointEstimate = point[effect],
                    Lower = Quantile((double[])values.Clone(), 0.025),
                    Upper = Quantile(values, 0.975)
                });
            }
        }
        return results.ToArray();
    }
}
'@
if (-not ("PlaceboEffectBootstrapEngine" -as [type])) {
    Add-Type -TypeDefinition $csharp -Language CSharp
}

$rawResults = [PlaceboEffectBootstrapEngine]::Run($Replicates, $Seed, $effectMatrix.ToArray())
$lookup = @{}
foreach ($result in $rawResults) { $lookup["$($result.GroupIndex):$($result.EffectIndex)"] = $result }
$culture = [Globalization.CultureInfo]::InvariantCulture
$formatted = for ($groupIndex = 0; $groupIndex -lt $groupRows.Count; $groupIndex++) {
    $target = $lookup["${groupIndex}:0"]
    $placebo = $lookup["${groupIndex}:1"]
    $semantic = $lookup["${groupIndex}:2"]
    [pscustomobject][ordered]@{
        Group = $groupRows[$groupIndex].Name
        Target_Steps = $groupRows[$groupIndex].TargetSteps
        Placebo_Runs = $groupRows[$groupIndex].PlaceboRuns
        Target_Effect = $target.PointEstimate.ToString("0.000000", $culture)
        Target_CI_Lower = $target.Lower.ToString("0.000000", $culture)
        Target_CI_Upper = $target.Upper.ToString("0.000000", $culture)
        Placebo_Effect = $placebo.PointEstimate.ToString("0.000000", $culture)
        Placebo_CI_Lower = $placebo.Lower.ToString("0.000000", $culture)
        Placebo_CI_Upper = $placebo.Upper.ToString("0.000000", $culture)
        Pure_Semantic_Effect = $semantic.PointEstimate.ToString("0.000000", $culture)
        Pure_Semantic_CI_Lower = $semantic.Lower.ToString("0.000000", $culture)
        Pure_Semantic_CI_Upper = $semantic.Upper.ToString("0.000000", $culture)
    }
}
$formatted | Export-Csv -LiteralPath "$OutputStem.csv" -NoTypeInformation -Encoding UTF8

function Effect-Cell([object]$Result) {
    $point = (100 * $Result.PointEstimate).ToString("0.00", $culture)
    $lower = (100 * $Result.Lower).ToString("0.00", $culture)
    $upper = (100 * $Result.Upper).ToString("0.00", $culture)
    return "$point [$lower, $upper]"
}

$markdown = [Collections.Generic.List[string]]::new()
$markdown.Add("# Qwen3-8B Placebo deletion effects")
$markdown.Add("")
$markdown.Add("- Eligible cohort: 511 of 600 target steps; 89 steps with no length-matched non-target step were skipped")
$markdown.Add("- Placebo selection: official Qwen3 tokenizer; non-target step length within 0.8-1.2 times target length; up to four random matches per target; seed = 20260723")
$markdown.Add("- Placebo runs: 1,514; one independent deletion continuation per selected Placebo step; judged with qwen/qwen3-8b")
$markdown.Add("- Step-level effects use the mean of four control runs, four target deletion runs, and all available Placebo runs for that target")
$markdown.Add("- Bootstrap: $Replicates replicates, resampling target steps with replacement within each reported group; seed = $Seed; percentile 95% CI")
$markdown.Add("- Effect cells are percentage points: point estimate [95% CI]")
$markdown.Add("")
$markdown.Add("| Group | Target steps | Placebo runs | Target Effect | Placebo Effect | Pure Semantic Effect |")
$markdown.Add("|---|---:|---:|---:|---:|---:|")
for ($groupIndex = 0; $groupIndex -lt $groupRows.Count; $groupIndex++) {
    $markdown.Add("| $($groupRows[$groupIndex].Name) | $($groupRows[$groupIndex].TargetSteps) | $($groupRows[$groupIndex].PlaceboRuns) | $(Effect-Cell $lookup["${groupIndex}:0"]) | $(Effect-Cell $lookup["${groupIndex}:1"]) | $(Effect-Cell $lookup["${groupIndex}:2"]) |")
}
[IO.File]::WriteAllLines((Join-Path (Get-Location) "$OutputStem.md"), $markdown, [Text.UTF8Encoding]::new($false))

[pscustomobject]@{
    EligibleTargetSteps = $stepEffects.Count
    PlaceboRuns = $placeboResults.Count
    Replicates = $Replicates
    ResultGroups = $formatted.Count
    OutputCsv = (Resolve-Path -LiteralPath "$OutputStem.csv").Path
    OutputMarkdown = (Resolve-Path -LiteralPath "$OutputStem.md").Path
    StepEffectsCsv = (Resolve-Path -LiteralPath "$OutputStem`_step_effects.csv").Path
    PlaceboRunsCsv = (Resolve-Path -LiteralPath "$OutputStem`_placebo_runs.csv").Path
}
