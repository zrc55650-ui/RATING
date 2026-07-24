param(
    [string]$InputCsv = "qwen3-8b_deletion_pairs.csv",
    [string]$OutputCsv = "qwen3-8b_cluster_bootstrap_metrics_5000.csv",
    [string]$OutputMarkdown = "qwen3-8b_cluster_bootstrap_metrics_5000.md",
    [int]$Replicates = 5000,
    [int]$Seed = 20260722
)

$ErrorActionPreference = "Stop"

$sourceRows = Import-Csv -LiteralPath $InputCsv
$clusterGroups = @($sourceRows | Group-Object sampleId | Sort-Object Name)

if ($sourceRows.Count -ne 2400) {
    throw "Expected 2400 observations, found $($sourceRows.Count)."
}
if ($clusterGroups.Count -ne 600) {
    throw "Expected 600 step clusters, found $($clusterGroups.Count)."
}
if (@($clusterGroups | Where-Object Count -ne 4).Count -ne 0) {
    throw "Every step cluster must contain exactly four observations."
}

$clusterCount = $clusterGroups.Count
$ratingGroup = [int[]]::new($clusterCount)
$typeGroup = [int[]]::new($clusterCount)
$comboGroup = [int[]]::new($clusterCount)
$clusterStats = [double[,]]::new($clusterCount, 7)

$ratingIndex = @{ "-1" = 0; "0" = 1; "1" = 2 }
$typeIndex = @{ "essential" = 0; "redundant" = 1; "harmful" = 2 }

for ($i = 0; $i -lt $clusterCount; $i++) {
    $records = @($clusterGroups[$i].Group)
    $first = $records[0]
    $r = [int]$ratingIndex[[string]$first.rating]
    $t = [int]$typeIndex[[string]$first.stepTypeLabel]

    if (@($records | Where-Object { $_.rating -ne $first.rating }).Count -ne 0) {
        throw "Rating is not constant within step $($first.sampleId)."
    }
    if (@($records | Where-Object { $_.stepTypeLabel -ne $first.stepTypeLabel }).Count -ne 0) {
        throw "Step type is not constant within step $($first.sampleId)."
    }

    $ratingGroup[$i] = 1 + $r
    $typeGroup[$i] = 4 + $t
    $comboGroup[$i] = 7 + (3 * $r) + $t

    $clusterStats[$i, 0] = $records.Count
    $clusterStats[$i, 1] = @($records | Where-Object controlCorrect -eq "True").Count
    $clusterStats[$i, 2] = @($records | Where-Object deletedCorrect -eq "True").Count
    $clusterStats[$i, 3] = @($records | Where-Object transition -eq "wrong_to_correct").Count
    $clusterStats[$i, 4] = @($records | Where-Object transition -eq "correct_to_wrong").Count
    $clusterStats[$i, 5] = ($records | Measure-Object controlTokens -Sum).Sum
    $clusterStats[$i, 6] = ($records | Measure-Object deletedTokens -Sum).Sum
}

$csharp = @'
using System;
using System.Collections.Generic;

public sealed class ClusterBootstrapResult
{
    public int GroupIndex { get; set; }
    public int MetricIndex { get; set; }
    public double PointEstimate { get; set; }
    public double Lower { get; set; }
    public double Upper { get; set; }
}

public static class ClusterBootstrapEngine
{
    private const int GroupCount = 16;
    private const int MetricCount = 4;
    private const int StatCount = 7;

    private static void AddCluster(double[,] totals, int group, double[,] clusterStats, int cluster)
    {
        for (int s = 0; s < StatCount; s++)
            totals[group, s] += clusterStats[cluster, s];
    }

    private static double Metric(double[,] totals, int group, int metric)
    {
        double n = totals[group, 0];
        double controlCorrect = totals[group, 1];
        double deletionCorrect = totals[group, 2];
        double wrongToCorrect = totals[group, 3];
        double correctToWrong = totals[group, 4];
        double controlTokens = totals[group, 5];
        double deletionTokens = totals[group, 6];

        switch (metric)
        {
            case 0: return (deletionCorrect / n) - (controlCorrect / n);
            case 1: return correctToWrong / controlCorrect;
            case 2: return wrongToCorrect / (n - controlCorrect);
            case 3: return (controlTokens - deletionTokens) / n;
            default: throw new ArgumentOutOfRangeException("metric");
        }
    }

    private static double Quantile(double[] values, double probability)
    {
        var finiteValues = new List<double>(values.Length);
        foreach (double value in values)
            if (!Double.IsNaN(value) && !Double.IsInfinity(value))
                finiteValues.Add(value);
        if (finiteValues.Count == 0) return Double.NaN;

        double[] sortedValues = finiteValues.ToArray();
        Array.Sort(sortedValues);
        double position = (sortedValues.Length - 1) * probability;
        int lowerIndex = (int)Math.Floor(position);
        int upperIndex = (int)Math.Ceiling(position);
        if (lowerIndex == upperIndex) return sortedValues[lowerIndex];
        double fraction = position - lowerIndex;
        return sortedValues[lowerIndex] + fraction * (sortedValues[upperIndex] - sortedValues[lowerIndex]);
    }

    public static ClusterBootstrapResult[] Run(
        int replicates,
        int seed,
        int[] ratingGroup,
        int[] typeGroup,
        int[] comboGroup,
        double[,] clusterStats)
    {
        int clusterCount = ratingGroup.Length;
        var original = new double[GroupCount, StatCount];
        for (int cluster = 0; cluster < clusterCount; cluster++)
        {
            AddCluster(original, 0, clusterStats, cluster);
            AddCluster(original, ratingGroup[cluster], clusterStats, cluster);
            AddCluster(original, typeGroup[cluster], clusterStats, cluster);
            AddCluster(original, comboGroup[cluster], clusterStats, cluster);
        }

        var bootstrap = new double[GroupCount, MetricCount, replicates];
        var random = new Random(seed);

        for (int replicate = 0; replicate < replicates; replicate++)
        {
            var totals = new double[GroupCount, StatCount];
            for (int draw = 0; draw < clusterCount; draw++)
            {
                int cluster = random.Next(clusterCount);
                AddCluster(totals, 0, clusterStats, cluster);
                AddCluster(totals, ratingGroup[cluster], clusterStats, cluster);
                AddCluster(totals, typeGroup[cluster], clusterStats, cluster);
                AddCluster(totals, comboGroup[cluster], clusterStats, cluster);
            }

            for (int group = 0; group < GroupCount; group++)
                for (int metric = 0; metric < MetricCount; metric++)
                    bootstrap[group, metric, replicate] = Metric(totals, group, metric);
        }

        var results = new List<ClusterBootstrapResult>(GroupCount * MetricCount);
        for (int group = 0; group < GroupCount; group++)
        {
            for (int metric = 0; metric < MetricCount; metric++)
            {
                var values = new double[replicates];
                for (int replicate = 0; replicate < replicates; replicate++)
                    values[replicate] = bootstrap[group, metric, replicate];

                double lower = Quantile((double[])values.Clone(), 0.025);
                double upper = Quantile(values, 0.975);
                results.Add(new ClusterBootstrapResult
                {
                    GroupIndex = group,
                    MetricIndex = metric,
                    PointEstimate = Metric(original, group, metric),
                    Lower = lower,
                    Upper = upper
                });
            }
        }
        return results.ToArray();
    }
}
'@

if (-not ("ClusterBootstrapEngine" -as [type])) {
    Add-Type -TypeDefinition $csharp -Language CSharp
}

$groupNames = @(
    "Overall",
    "rating=-1", "rating=0", "rating=1",
    "step_type=Essential", "step_type=Redundant", "step_type=Harmful",
    "rating=-1 x step_type=Essential",
    "rating=-1 x step_type=Redundant",
    "rating=-1 x step_type=Harmful",
    "rating=0 x step_type=Essential",
    "rating=0 x step_type=Redundant",
    "rating=0 x step_type=Harmful",
    "rating=1 x step_type=Essential",
    "rating=1 x step_type=Redundant",
    "rating=1 x step_type=Harmful"
)

$metricNames = @(
    "accuracy_change",
    "harm_rate",
    "recovery_rate",
    "mean_token_change"
)

$rawResults = [ClusterBootstrapEngine]::Run(
    $Replicates,
    $Seed,
    $ratingGroup,
    $typeGroup,
    $comboGroup,
    $clusterStats
)

$culture = [System.Globalization.CultureInfo]::InvariantCulture

function Format-Number([double]$value, [string]$format) {
    if ([double]::IsNaN($value) -or [double]::IsInfinity($value)) { return "NA" }
    return $value.ToString($format, $culture)
}

$resultLookup = @{}
foreach ($result in $rawResults) {
    $resultLookup["$($result.GroupIndex):$($result.MetricIndex)"] = $result
}

$groupStepCounts = [int[]]::new($groupNames.Count)
for ($i = 0; $i -lt $clusterCount; $i++) {
    foreach ($groupIndex in @(0, $ratingGroup[$i], $typeGroup[$i], $comboGroup[$i])) {
        $groupStepCounts[$groupIndex]++
    }
}

$formatted = for ($groupIndex = 0; $groupIndex -lt $groupNames.Count; $groupIndex++) {
    $accuracy = $resultLookup["${groupIndex}:0"]
    $harm = $resultLookup["${groupIndex}:1"]
    $recovery = $resultLookup["${groupIndex}:2"]
    $tokens = $resultLookup["${groupIndex}:3"]

    [pscustomobject]@{
        Group = $groupNames[$groupIndex]
        Target_Steps = $groupStepCounts[$groupIndex]
        Pairs = 4 * $groupStepCounts[$groupIndex]
        Accuracy_Change = Format-Number $accuracy.PointEstimate "0.000000"
        Accuracy_CI_Lower = Format-Number $accuracy.Lower "0.000000"
        Accuracy_CI_Upper = Format-Number $accuracy.Upper "0.000000"
        Harm_Rate = Format-Number $harm.PointEstimate "0.000000"
        Harm_CI_Lower = Format-Number $harm.Lower "0.000000"
        Harm_CI_Upper = Format-Number $harm.Upper "0.000000"
        Recovery_Rate = Format-Number $recovery.PointEstimate "0.000000"
        Recovery_CI_Lower = Format-Number $recovery.Lower "0.000000"
        Recovery_CI_Upper = Format-Number $recovery.Upper "0.000000"
        Mean_Token_Change = Format-Number $tokens.PointEstimate "0.00"
        Token_CI_Lower = Format-Number $tokens.Lower "0.00"
        Token_CI_Upper = Format-Number $tokens.Upper "0.00"
    }
}

$formatted | Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding UTF8

$markdown = [System.Collections.Generic.List[string]]::new()
$markdown.Add("# Qwen3-8B Deletion Experiment: Cluster Bootstrap Results")
$markdown.Add("")
$markdown.Add("- Source: ``$InputCsv`` (2,400 observations; 600 step clusters; 4 runs per step)")
$markdown.Add("- Cluster unit: ``sampleId`` (treated as ``step_id``)")
$markdown.Add("- Step type: original ``stepTypeLabel`` in the source CSV")
$markdown.Add("- Bootstrap: $Replicates replicates; 600 clusters sampled with replacement per replicate; seed = $Seed")
$markdown.Add("- CI: percentile 95% interval using the 2.5% and 97.5% quantiles")
$markdown.Add("- Metrics: accuracy change; harm rate = P(deleted incorrect | control correct); recovery rate = P(deleted correct | control incorrect); mean token change = control tokens - deleted tokens (positive means tokens saved)")
$markdown.Add("- Table cells show point estimate [95% CI]; accuracy change is in percentage points and rate metrics are percentages")
$markdown.Add("")
$markdown.Add("| Group | Target steps | Pairs | Accuracy change (pp) | Harm rate | Recovery rate | Mean token change |")
$markdown.Add("|---|---:|---:|---:|---:|---:|---:|")
for ($groupIndex = 0; $groupIndex -lt $groupNames.Count; $groupIndex++) {
    $row = $formatted[$groupIndex]
    $accuracy = $resultLookup["${groupIndex}:0"]
    $harm = $resultLookup["${groupIndex}:1"]
    $recovery = $resultLookup["${groupIndex}:2"]
    $tokens = $resultLookup["${groupIndex}:3"]
    $accuracyCell = "$(Format-Number (100 * $accuracy.PointEstimate) '0.00') [$(Format-Number (100 * $accuracy.Lower) '0.00'), $(Format-Number (100 * $accuracy.Upper) '0.00')]"
    $harmCell = "$(Format-Number (100 * $harm.PointEstimate) '0.00')% [$(Format-Number (100 * $harm.Lower) '0.00')%, $(Format-Number (100 * $harm.Upper) '0.00')%]"
    $recoveryCell = "$(Format-Number (100 * $recovery.PointEstimate) '0.00')% [$(Format-Number (100 * $recovery.Lower) '0.00')%, $(Format-Number (100 * $recovery.Upper) '0.00')%]"
    $tokenCell = "$(Format-Number $tokens.PointEstimate '0.00') [$(Format-Number $tokens.Lower '0.00'), $(Format-Number $tokens.Upper '0.00')]"
    $markdown.Add("| $($row.Group) | $($row.Target_Steps) | $($row.Pairs) | $accuracyCell | $harmCell | $recoveryCell | $tokenCell |")
}

[System.IO.File]::WriteAllLines((Join-Path (Get-Location) $OutputMarkdown), $markdown, [System.Text.UTF8Encoding]::new($false))

[pscustomobject]@{
    InputRows = $sourceRows.Count
    Clusters = $clusterCount
    Replicates = $Replicates
    ResultRows = $formatted.Count
    Seed = $Seed
    OutputCsv = (Resolve-Path -LiteralPath $OutputCsv).Path
    OutputMarkdown = (Resolve-Path -LiteralPath $OutputMarkdown).Path
}
