param(
    [string]$InputCsv = "qwen3-8b_deletion_pairs.csv",
    [string]$OutputStem = "qwen3-8b_deletion_excluding_both_wrong"
)

$ErrorActionPreference = "Stop"

function Pct([int]$Numerator, [int]$Denominator) {
    if ($Denominator -eq 0) { return 0 }
    return [math]::Round(100.0 * $Numerator / $Denominator, 2)
}

function Median([double[]]$Values) {
    if ($Values.Count -eq 0) { return 0 }
    $ordered = @($Values | Sort-Object)
    $middle = [int]($ordered.Count / 2)
    if ($ordered.Count % 2) { return $ordered[$middle] }
    return [math]::Round(($ordered[$middle - 1] + $ordered[$middle]) / 2, 1)
}

function ConditionStats([object[]]$Pairs, [string]$Prefix) {
    $correctField = "${Prefix}Correct"
    $tokensField = "${Prefix}Tokens"
    $statusField = "${Prefix}Status"
    $tokens = [double[]]@($Pairs | ForEach-Object { [double]$_.$tokensField })
    $correct = @($Pairs | Where-Object { [bool]::Parse($_.$correctField) }).Count
    [ordered]@{
        n = $Pairs.Count
        correct = $correct
        accuracyPct = Pct $correct $Pairs.Count
        tokenTotal = [long](($tokens | Measure-Object -Sum).Sum)
        tokenMean = [math]::Round(($tokens | Measure-Object -Average).Average, 2)
        tokenMedian = Median $tokens
        completed = @($Pairs | Where-Object { $_.$statusField -eq "completed" }).Count
        cannotContinue = @($Pairs | Where-Object { $_.$statusField -eq "cannot_continue" }).Count
        logicalBreak = @($Pairs | Where-Object { $_.$statusField -eq "logical_break" }).Count
    }
}

function TransitionStats([object[]]$Pairs) {
    [ordered]@{
        correctToWrong = @($Pairs | Where-Object transition -eq "correct_to_wrong").Count
        wrongToCorrect = @($Pairs | Where-Object transition -eq "wrong_to_correct").Count
        stillCorrect = @($Pairs | Where-Object transition -eq "still_correct").Count
        stillWrongExcluded = 0
    }
}

function Summary([object[]]$Pairs) {
    $control = ConditionStats $Pairs "control"
    $deleted = ConditionStats $Pairs "deleted"
    $saved = [double[]]@($Pairs | ForEach-Object { [double]$_.tokensSaved })
    [ordered]@{
        pairs = $Pairs.Count
        control = $control
        deleted = $deleted
        accuracyDeltaPctPoint = [math]::Round($deleted.accuracyPct - $control.accuracyPct, 2)
        transitions = TransitionStats $Pairs
        tokens = [ordered]@{
            netSaved = [long](($saved | Measure-Object -Sum).Sum)
            savedPct = if ($control.tokenTotal) { [math]::Round(100.0 * (($saved | Measure-Object -Sum).Sum) / $control.tokenTotal, 2) } else { 0 }
            meanSaved = [math]::Round(($saved | Measure-Object -Average).Average, 2)
            medianSaved = Median $saved
            deletedUsedFewer = @($Pairs | Where-Object { [double]$_.tokensSaved -gt 0 }).Count
            same = @($Pairs | Where-Object { [double]$_.tokensSaved -eq 0 }).Count
            deletedUsedMore = @($Pairs | Where-Object { [double]$_.tokensSaved -lt 0 }).Count
        }
        deletionInduced = [ordered]@{
            newCannotContinue = @($Pairs | Where-Object { $_.controlStatus -ne "cannot_continue" -and $_.deletedStatus -eq "cannot_continue" }).Count
            newLogicalBreak = @($Pairs | Where-Object { $_.controlStatus -ne "logical_break" -and $_.deletedStatus -eq "logical_break" }).Count
            recoveredToCompleted = @($Pairs | Where-Object { $_.controlStatus -ne "completed" -and $_.deletedStatus -eq "completed" }).Count
        }
    }
}

$allPairs = @(Import-Csv $InputCsv)
$excluded = @($allPairs | Where-Object transition -eq "still_wrong")
$included = @($allPairs | Where-Object transition -ne "still_wrong")
if ($allPairs.Count -ne 2400) { throw "Expected 2400 pairs, found $($allPairs.Count)" }
if ($excluded.Count -eq 0) { throw "No both-wrong pairs found" }

$runs = @(
    foreach ($currentRun in 1..4) {
        [ordered]@{ run = $currentRun; summary = Summary @($included | Where-Object { [int]$_.run -eq $currentRun }) }
    }
)
$subgroups = foreach ($field in "rating", "position", "stepTypeLabel", "removableLabel") {
    foreach ($group in ($included | Group-Object $field | Sort-Object Name)) {
        $s = Summary @($group.Group)
        [ordered]@{ dimension = $field; value = $group.Name; summary = $s }
    }
}

$result = [ordered]@{
    inclusionRule = "Exclude a pair only when both control and deleted final answers are incorrect (transition = still_wrong)."
    originalPairs = $allPairs.Count
    excludedBothWrongPairs = $excluded.Count
    analyzedPairs = $included.Count
    overall = Summary $included
    runs = $runs
    subgroups = @($subgroups)
    generatedAt = (Get-Date).ToUniversalTime().ToString("o")
}

$included | Export-Csv -NoTypeInformation -Encoding utf8 "$OutputStem`_pairs.csv"
[IO.File]::WriteAllText("$OutputStem`_summary.json", ($result | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
$result | ConvertTo-Json -Depth 10
