param(
    [string]$InputPairsCsv = "qwen3-8b_deletion_pairs.csv",
    [string]$InputGenerationsJsonl = "qwen_deletion_generations.jsonl",
    [string]$OutputCsv = "qwen3-8b_cluster_bootstrap_stratified_5000.csv",
    [string]$OutputMarkdown = "qwen3-8b_cluster_bootstrap_stratified_5000.md",
    [int]$Replicates = 5000,
    [int]$Seed = 20260722
)

$ErrorActionPreference = "Stop"

$pairRows = @(Import-Csv -LiteralPath $InputPairsCsv)
$clusters = @($pairRows | Group-Object sampleId | Sort-Object Name)
if ($pairRows.Count -ne 2400) { throw "Expected 2400 pairs, found $($pairRows.Count)." }
if ($clusters.Count -ne 600) { throw "Expected 600 step clusters, found $($clusters.Count)." }
if (@($clusters | Where-Object Count -ne 4).Count -ne 0) { throw "Every step cluster must contain exactly four runs." }

$generationRows = @(
    [IO.File]::ReadAllLines((Resolve-Path -LiteralPath $InputGenerationsJsonl), [Text.Encoding]::UTF8) |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { $_ | ConvertFrom-Json }
)
if ($generationRows.Count -ne 4800) { throw "Expected 4800 generation records, found $($generationRows.Count)." }

$promptLengths = @{}
foreach ($sampleRun in @($generationRows | Group-Object sampleId, run)) {
    $control = @($sampleRun.Group | Where-Object condition -eq "control")
    $deleted = @($sampleRun.Group | Where-Object condition -eq "deleted")
    if ($control.Count -ne 1 -or $deleted.Count -ne 1) { throw "Each sample/run must have one control and one deleted generation." }
    $sampleId = [string]$control[0].sampleId
    $stepTokens = [int]$control[0].promptTokens - [int]$deleted[0].promptTokens
    $prefixTokens = [int]$deleted[0].promptTokens
    if (-not $promptLengths.ContainsKey($sampleId)) {
        $promptLengths[$sampleId] = [System.Collections.Generic.List[object]]::new()
    }
    $promptLengths[$sampleId].Add([pscustomobject]@{ StepTokens = $stepTokens; PrefixTokens = $prefixTokens })
}

$sampleMetadata = [System.Collections.Generic.List[object]]::new()
foreach ($cluster in $clusters) {
    $records = @($cluster.Group)
    $sampleId = [string]$cluster.Name
    if (-not $promptLengths.ContainsKey($sampleId) -or $promptLengths[$sampleId].Count -ne 4) {
        throw "Missing four prompt-length observations for $sampleId."
    }
    $stepValues = @($promptLengths[$sampleId] | ForEach-Object StepTokens | Sort-Object -Unique)
    $prefixValues = @($promptLengths[$sampleId] | ForEach-Object PrefixTokens | Sort-Object -Unique)
    if ($stepValues.Count -ne 1 -or $prefixValues.Count -ne 1) {
        throw "Prompt token lengths are not constant across runs for $sampleId."
    }

    $sampleMetadata.Add([pscustomobject]@{
        SampleId = $sampleId
        Position = ([string]$records[0].position).ToLowerInvariant()
        StepTokens = [int]$stepValues[0]
        PrefixTokens = [int]$prefixValues[0]
        ControlCorrectFrequency = @($records | Where-Object controlCorrect -eq "True").Count
    })
}

function Get-TertileAssignments([object[]]$Rows, [string]$Property) {
    $sorted = @($Rows | Sort-Object @{ Expression = { [int]($_.$Property) }; Ascending = $true }, SampleId)
    $assignments = @{}
    for ($rank = 0; $rank -lt $sorted.Count; $rank++) {
        $tertile = [math]::Min(2, [math]::Floor(3 * $rank / $sorted.Count))
        $assignments[[string]$sorted[$rank].SampleId] = [int]$tertile
    }
    return $assignments
}

$stepTertiles = Get-TertileAssignments @($sampleMetadata) "StepTokens"
$prefixTertiles = Get-TertileAssignments @($sampleMetadata) "PrefixTokens"
$tertileNames = @("short", "middle", "long")

$groupDefinitions = [System.Collections.Generic.List[object]]::new()
foreach ($level in @("early", "middle", "late")) {
    $groupDefinitions.Add([pscustomobject]@{ Dimension = "step_position"; Level = $level; Definition = $level })
}
for ($tertile = 0; $tertile -lt 3; $tertile++) {
    $values = @($sampleMetadata | Where-Object { $stepTertiles[$_.SampleId] -eq $tertile } | ForEach-Object StepTokens)
    $rankStart = 1 + (200 * $tertile)
    $rankEnd = 200 * ($tertile + 1)
    $groupDefinitions.Add([pscustomobject]@{
        Dimension = "step_length"
        Level = $tertileNames[$tertile]
        Definition = "ranks $rankStart-$rankEnd; $(($values | Measure-Object -Minimum).Minimum)-$(($values | Measure-Object -Maximum).Maximum) prompt tokens"
    })
}
for ($tertile = 0; $tertile -lt 3; $tertile++) {
    $values = @($sampleMetadata | Where-Object { $prefixTertiles[$_.SampleId] -eq $tertile } | ForEach-Object PrefixTokens)
    $rankStart = 1 + (200 * $tertile)
    $rankEnd = 200 * ($tertile + 1)
    $groupDefinitions.Add([pscustomobject]@{
        Dimension = "prefix_length"
        Level = $tertileNames[$tertile]
        Definition = "ranks $rankStart-$rankEnd; $(($values | Measure-Object -Minimum).Minimum)-$(($values | Measure-Object -Maximum).Maximum) prompt tokens"
    })
}
for ($frequency = 0; $frequency -le 4; $frequency++) {
    $groupDefinitions.Add([pscustomobject]@{
        Dimension = "control_correct_frequency"
        Level = "$frequency/4"
        Definition = "$frequency of 4 control runs correct"
    })
}

$clusterCount = $clusters.Count
$membershipCount = 4
$memberships = [int[,]]::new($clusterCount, $membershipCount)
$clusterStats = [double[,]]::new($clusterCount, 5)

for ($i = 0; $i -lt $clusterCount; $i++) {
    $records = @($clusters[$i].Group)
    $metadata = $sampleMetadata[$i]
    $positionIndex = [array]::IndexOf(@("early", "middle", "late"), $metadata.Position)
    if ($positionIndex -lt 0) { throw "Unknown step position for $($metadata.SampleId): $($metadata.Position)" }

    $memberships[$i, 0] = $positionIndex
    $memberships[$i, 1] = 3 + $stepTertiles[$metadata.SampleId]
    $memberships[$i, 2] = 6 + $prefixTertiles[$metadata.SampleId]
    $memberships[$i, 3] = 9 + $metadata.ControlCorrectFrequency

    $clusterStats[$i, 0] = $records.Count
    $clusterStats[$i, 1] = @($records | Where-Object controlCorrect -eq "True").Count
    $clusterStats[$i, 2] = @($records | Where-Object deletedCorrect -eq "True").Count
    $clusterStats[$i, 3] = @($records | Where-Object transition -eq "wrong_to_correct").Count
    $clusterStats[$i, 4] = @($records | Where-Object transition -eq "correct_to_wrong").Count
}

$csharp = @'
using System;
using System.Collections.Generic;

public sealed class StratifiedBootstrapResult
{
    public int GroupIndex { get; set; }
    public int TargetSteps { get; set; }
    public int Pairs { get; set; }
    public int WrongToCorrect { get; set; }
    public int CorrectToWrong { get; set; }
    public double PointEstimate { get; set; }
    public double Lower { get; set; }
    public double Upper { get; set; }
}

public static class StratifiedClusterBootstrapEngine
{
    private static double Quantile(double[] values, double probability)
    {
        var finite = new List<double>(values.Length);
        foreach (double value in values)
            if (!Double.IsNaN(value) && !Double.IsInfinity(value)) finite.Add(value);
        if (finite.Count == 0) return Double.NaN;
        double[] sorted = finite.ToArray();
        Array.Sort(sorted);
        double position = (sorted.Length - 1) * probability;
        int lowerIndex = (int)Math.Floor(position);
        int upperIndex = (int)Math.Ceiling(position);
        if (lowerIndex == upperIndex) return sorted[lowerIndex];
        double fraction = position - lowerIndex;
        return sorted[lowerIndex] + fraction * (sorted[upperIndex] - sorted[lowerIndex]);
    }

    public static StratifiedBootstrapResult[] Run(int replicates, int seed, int[,] memberships, double[,] stats, int groupCount)
    {
        int clusterCount = memberships.GetLength(0);
        int membershipCount = memberships.GetLength(1);
        var original = new double[groupCount, 5];
        var stepCounts = new int[groupCount];

        for (int cluster = 0; cluster < clusterCount; cluster++)
        {
            for (int m = 0; m < membershipCount; m++)
            {
                int group = memberships[cluster, m];
                stepCounts[group]++;
                for (int s = 0; s < 5; s++) original[group, s] += stats[cluster, s];
            }
        }

        var bootstrap = new double[groupCount, replicates];
        var random = new Random(seed);
        for (int replicate = 0; replicate < replicates; replicate++)
        {
            var totals = new double[groupCount, 3];
            for (int draw = 0; draw < clusterCount; draw++)
            {
                int cluster = random.Next(clusterCount);
                for (int m = 0; m < membershipCount; m++)
                {
                    int group = memberships[cluster, m];
                    for (int s = 0; s < 3; s++) totals[group, s] += stats[cluster, s];
                }
            }
            for (int group = 0; group < groupCount; group++)
            {
                double n = totals[group, 0];
                bootstrap[group, replicate] = n > 0 ? (totals[group, 2] - totals[group, 1]) / n : Double.NaN;
            }
        }

        var results = new List<StratifiedBootstrapResult>(groupCount);
        for (int group = 0; group < groupCount; group++)
        {
            var values = new double[replicates];
            for (int replicate = 0; replicate < replicates; replicate++) values[replicate] = bootstrap[group, replicate];
            results.Add(new StratifiedBootstrapResult {
                GroupIndex = group,
                TargetSteps = stepCounts[group],
                Pairs = (int)original[group, 0],
                WrongToCorrect = (int)original[group, 3],
                CorrectToWrong = (int)original[group, 4],
                PointEstimate = (original[group, 2] - original[group, 1]) / original[group, 0],
                Lower = Quantile(values, 0.025),
                Upper = Quantile(values, 0.975)
            });
        }
        return results.ToArray();
    }
}
'@

if (-not ("StratifiedClusterBootstrapEngine" -as [type])) {
    Add-Type -TypeDefinition $csharp -Language CSharp
}

$rawResults = [StratifiedClusterBootstrapEngine]::Run(
    $Replicates, $Seed, $memberships, $clusterStats, $groupDefinitions.Count
)
$culture = [Globalization.CultureInfo]::InvariantCulture
$formatted = foreach ($result in $rawResults) {
    $definition = $groupDefinitions[$result.GroupIndex]
    [pscustomobject]@{
        Dimension = $definition.Dimension
        Group = $definition.Level
        Definition = $definition.Definition
        Target_Steps = $result.TargetSteps
        Pairs = $result.Pairs
        Accuracy_Change = $result.PointEstimate.ToString("0.000000", $culture)
        CI_Lower = $result.Lower.ToString("0.000000", $culture)
        CI_Upper = $result.Upper.ToString("0.000000", $culture)
        Wrong_To_Correct = $result.WrongToCorrect
        Correct_To_Wrong = $result.CorrectToWrong
    }
}
$formatted | Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding UTF8

$markdown = [Collections.Generic.List[string]]::new()
$markdown.Add("# Stratified target-step cluster bootstrap")
$markdown.Add("")
$markdown.Add("- Source: ``$InputPairsCsv``; 600 target steps; 4 runs per step; 2,400 pairs")
$markdown.Add("- Bootstrap: $Replicates replicates; each replicate samples 600 target steps with replacement and retains all four runs; seed = $Seed")
$markdown.Add("- CI: percentile 95% interval; cells show point estimate [95% CI] in percentage points")
$markdown.Add("- Step length: control prompt tokens minus deleted prompt tokens; prefix length: deleted-condition prompt tokens")
$markdown.Add("- Length tertiles: rank-based at the step level (200 steps each; ties broken deterministically by sampleId)")
$markdown.Add("- Transition counts are observed counts in the original data, not bootstrap averages")
$markdown.Add("")
$markdown.Add("| Dimension | Group | Definition | Steps | Pairs | Accuracy change (pp) | Wrong to correct | Correct to wrong |")
$markdown.Add("|---|---|---|---:|---:|---:|---:|---:|")
foreach ($row in $formatted) {
    $estimate = 100 * [double]::Parse($row.Accuracy_Change, $culture)
    $lower = 100 * [double]::Parse($row.CI_Lower, $culture)
    $upper = 100 * [double]::Parse($row.CI_Upper, $culture)
    $cell = "$($estimate.ToString('0.00', $culture)) [$($lower.ToString('0.00', $culture)), $($upper.ToString('0.00', $culture))]"
    $markdown.Add("| $($row.Dimension) | $($row.Group) | $($row.Definition) | $($row.Target_Steps) | $($row.Pairs) | $cell | $($row.Wrong_To_Correct) | $($row.Correct_To_Wrong) |")
}
[IO.File]::WriteAllLines((Join-Path (Get-Location) $OutputMarkdown), $markdown, [Text.UTF8Encoding]::new($false))

[pscustomobject]@{
    InputRows = $pairRows.Count
    Clusters = $clusterCount
    Replicates = $Replicates
    ResultRows = $formatted.Count
    Seed = $Seed
    OutputCsv = (Resolve-Path -LiteralPath $OutputCsv).Path
    OutputMarkdown = (Resolve-Path -LiteralPath $OutputMarkdown).Path
}
