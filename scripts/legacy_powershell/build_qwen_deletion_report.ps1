param(
    [string]$GenerationPattern = "qwen_deletion_fast_worker??.jsonl",
    [string]$JudgePattern = "qwen_deletion_fast_judge??.jsonl",
    [string]$OutputStem = "qwen3-8b_删除实验"
)

$ErrorActionPreference = "Stop"

function Read-JsonlFiles([IO.FileInfo[]]$Files) {
    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($file in $Files) {
        foreach ($line in [IO.File]::ReadAllLines($file.FullName, [Text.Encoding]::UTF8)) {
            if ($line.Trim()) { $rows.Add(($line | ConvertFrom-Json)) }
        }
    }
    return @($rows)
}

function Percent([int]$Numerator, [int]$Denominator) {
    if ($Denominator -eq 0) { return 0 }
    return [math]::Round(100.0 * $Numerator / $Denominator, 2)
}

function Percentile([double[]]$Values, [double]$P) {
    if ($Values.Count -eq 0) { return 0 }
    [array]::Sort($Values)
    $index = [math]::Max(0, [math]::Min($Values.Count - 1, [math]::Ceiling($P * $Values.Count) - 1))
    return [math]::Round($Values[$index], 1)
}

function Condition-Stats([object[]]$Rows) {
    $tokens = [double[]]@($Rows | ForEach-Object { [double]$_.visibleOutputTokens })
    $correct = @($Rows | Where-Object { $_.correct }).Count
    return [ordered]@{
        n = $Rows.Count
        correct = $correct
        accuracyPct = Percent $correct $Rows.Count
        tokenTotal = [long](($tokens | Measure-Object -Sum).Sum)
        tokenMean = if ($tokens.Count) { [math]::Round(($tokens | Measure-Object -Average).Average, 1) } else { 0 }
        tokenMedian = Percentile $tokens 0.5
        tokenP95 = Percentile $tokens 0.95
        completed = @($Rows | Where-Object { $_.generatorStatus -eq "completed" }).Count
        cannotContinue = @($Rows | Where-Object { $_.generatorStatus -eq "cannot_continue" }).Count
        logicalBreak = @($Rows | Where-Object { $_.generatorStatus -eq "logical_break" }).Count
    }
}

function Pair-Summary([object[]]$Pairs) {
    return [ordered]@{
        n = $Pairs.Count
        correctToWrong = @($Pairs | Where-Object { $_.transition -eq "correct_to_wrong" }).Count
        wrongToCorrect = @($Pairs | Where-Object { $_.transition -eq "wrong_to_correct" }).Count
        stillCorrect = @($Pairs | Where-Object { $_.transition -eq "still_correct" }).Count
        stillWrong = @($Pairs | Where-Object { $_.transition -eq "still_wrong" }).Count
    }
}

function H([object]$Value) { return [Net.WebUtility]::HtmlEncode([string]$Value) }

$generationFiles = @(Get-ChildItem -File $GenerationPattern | Sort-Object Name)
$judgeFiles = @(Get-ChildItem -File $JudgePattern | Sort-Object Name)
if ($generationFiles.Count -lt 1) { throw "No generation shards match $GenerationPattern" }
if ($judgeFiles.Count -lt 1) { throw "No judge shards match $JudgePattern" }

$generations = Read-JsonlFiles $generationFiles
$judgments = Read-JsonlFiles $judgeFiles
if ($generations.Count -ne 4800) { throw "Expected 4800 generation records, found $($generations.Count)" }
if (@($generations.taskId | Sort-Object -Unique).Count -ne 4800) { throw "Generation task IDs are not unique" }
if ($judgments.Count -ne 4800) { throw "Expected 4800 judgments, found $($judgments.Count)" }
if (@($judgments.taskId | Sort-Object -Unique).Count -ne 4800) { throw "Judgment task IDs are not unique" }

$judgeById = @{}
foreach ($judgment in $judgments) { $judgeById[[string]$judgment.taskId] = $judgment }
$results = [System.Collections.Generic.List[object]]::new()
foreach ($generation in $generations) {
    $judgment = $judgeById[[string]$generation.taskId]
    if ($null -eq $judgment) { throw "Missing judgment for $($generation.taskId)" }
    $generation | Add-Member -NotePropertyName correct -NotePropertyValue ([bool]$judgment.correct)
    $generation | Add-Member -NotePropertyName judgeReason -NotePropertyValue ([string]$judgment.judgeReason)
    $generation | Add-Member -NotePropertyName judgeModel -NotePropertyValue ([string]$judgment.judgeModel)
    $results.Add($generation)
}

$resultJsonl = "$OutputStem`_完整结果.jsonl"
$writer = [IO.StreamWriter]::new($resultJsonl, $false, [Text.UTF8Encoding]::new($false))
try { foreach ($row in $results) { $writer.WriteLine(($row | ConvertTo-Json -Depth 10 -Compress)) } } finally { $writer.Dispose() }

$pairGroups = $results | Group-Object { "$($_.sampleId)|$($_.run)" }
if ($pairGroups.Count -ne 2400) { throw "Expected 2400 condition pairs, found $($pairGroups.Count)" }
$pairs = [System.Collections.Generic.List[object]]::new()
foreach ($group in $pairGroups) {
    $control = @($group.Group | Where-Object { $_.condition -eq "control" })
    $deleted = @($group.Group | Where-Object { $_.condition -eq "deleted" })
    if ($control.Count -ne 1 -or $deleted.Count -ne 1) { throw "Invalid pair $($group.Name)" }
    $c = $control[0]; $d = $deleted[0]
    $transition = if ($c.correct -and -not $d.correct) { "correct_to_wrong" } elseif (-not $c.correct -and $d.correct) { "wrong_to_correct" } elseif ($c.correct -and $d.correct) { "still_correct" } else { "still_wrong" }
    $pairs.Add([pscustomobject][ordered]@{
        sampleId=$c.sampleId; displayOrder=$c.displayOrder; run=$c.run; rating=$c.rating; position=$c.position; removableLabel=$c.removableLabel; stepTypeLabel=$c.stepTypeLabel; targetStepIndex=$c.targetStepIndex
        controlCorrect=[bool]$c.correct; deletedCorrect=[bool]$d.correct; transition=$transition
        controlFinalAnswer=$c.finalAnswer; deletedFinalAnswer=$d.finalAnswer; groundTruthAnswer=$c.groundTruthAnswer
        controlTokens=$c.visibleOutputTokens; deletedTokens=$d.visibleOutputTokens; tokenDelta=([long]$d.visibleOutputTokens-[long]$c.visibleOutputTokens)
        controlStatus=$c.generatorStatus; deletedStatus=$d.generatorStatus
        controlStatusReason=$c.generatorStatusReason; deletedStatusReason=$d.generatorStatusReason
        controlJudgeReason=$c.judgeReason; deletedJudgeReason=$d.judgeReason
    })
}

$pairCsv = "$OutputStem`_配对结果.csv"
$pairs | Sort-Object run,displayOrder | Export-Csv -NoTypeInformation -Encoding UTF8 $pairCsv

$runSummaries = [System.Collections.Generic.List[object]]::new()
for ($run = 1; $run -le 4; $run++) {
    $runRows = @($results | Where-Object { $_.run -eq $run })
    $runPairs = @($pairs | Where-Object { $_.run -eq $run })
    $runSummaries.Add([ordered]@{ run=$run; transitions=(Pair-Summary $runPairs); control=(Condition-Stats @($runRows | Where-Object condition -eq "control")); deleted=(Condition-Stats @($runRows | Where-Object condition -eq "deleted")) })
}

$overall = [ordered]@{
    transitions = Pair-Summary @($pairs)
    control = Condition-Stats @($results | Where-Object condition -eq "control")
    deleted = Condition-Stats @($results | Where-Object condition -eq "deleted")
}

$subgroups = [System.Collections.Generic.List[object]]::new()
foreach ($definition in @(
    @{field="rating"; label="PRM rating"},
    @{field="position"; label="推理位置"},
    @{field="stepTypeLabel"; label="AI step type"},
    @{field="removableLabel"; label="AI removable"}
)) {
    foreach ($group in ($pairs | Group-Object -Property $definition.field | Sort-Object Name)) {
        $groupPairs = @($group.Group)
        $controlCorrect = @($groupPairs | Where-Object controlCorrect).Count
        $deletedCorrect = @($groupPairs | Where-Object deletedCorrect).Count
        $transitions = Pair-Summary $groupPairs
        $subgroups.Add([ordered]@{ dimension=$definition.label; value=$group.Name; n=$groupPairs.Count; controlAccuracyPct=(Percent $controlCorrect $groupPairs.Count); deletedAccuracyPct=(Percent $deletedCorrect $groupPairs.Count); deltaPctPoint=[math]::Round((Percent $deletedCorrect $groupPairs.Count)-(Percent $controlCorrect $groupPairs.Count),2); transitions=$transitions })
    }
}

$summary = [ordered]@{
    experiment = [ordered]@{ model="qwen/qwen3-8b"; runs=4; samples=600; generationCalls=4800; temperature=0.7; topP=0.8; maxTokens=2048; mode="non-thinking (/no_think)"; generatedConditions=@("control: prefix includes target step","deleted: prefix ends before target step") }
    overall = $overall
    runs = @($runSummaries)
    subgroups = @($subgroups)
    generatedAt = (Get-Date).ToUniversalTime().ToString("o")
}
$summaryPath = "$OutputStem`_汇总.json"
[IO.File]::WriteAllText($summaryPath, ($summary | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))

$runRowsHtml = foreach ($item in $runSummaries) {
    $t=$item.transitions;$c=$item.control;$d=$item.deleted
    "<tr><td>第 $($item.run) 次</td><td>$($t.correctToWrong)</td><td>$($t.wrongToCorrect)</td><td>$($t.stillCorrect)</td><td>$($t.stillWrong)</td><td>$($c.accuracyPct)%</td><td>$($d.accuracyPct)%</td><td>$($c.tokenMean) / $($d.tokenMean)</td><td>$($c.cannotContinue) / $($d.cannotContinue)</td><td>$($c.logicalBreak) / $($d.logicalBreak)</td></tr>"
}
$subgroupRowsHtml = foreach ($item in $subgroups) {
    "<tr><td>$(H $item.dimension)</td><td>$(H $item.value)</td><td>$($item.n)</td><td>$($item.controlAccuracyPct)%</td><td>$($item.deletedAccuracyPct)%</td><td>$($item.deltaPctPoint) pp</td><td>$($item.transitions.correctToWrong)</td><td>$($item.transitions.wrongToCorrect)</td></tr>"
}
$c=$overall.control;$d=$overall.deleted;$t=$overall.transitions
$html = @"
<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Qwen3-8B 删除步骤实验</title>
<style>:root{--bg:#f5f7fb;--card:#fff;--ink:#172033;--muted:#667085;--line:#e4e7ec;--blue:#315efb;--red:#d92d20;--green:#079455}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 system-ui,-apple-system,"Segoe UI","Microsoft YaHei",sans-serif}.wrap{max-width:1260px;margin:32px auto;padding:0 20px}h1{font-size:30px;margin:0 0 8px}.lead{color:var(--muted);margin:0 0 24px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.card,.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 3px 12px #1018280a}.card{padding:18px}.card .k{color:var(--muted);font-size:13px}.card .v{font-size:25px;font-weight:750;margin-top:5px}.card .s{color:var(--muted)}.panel{padding:22px;margin-top:18px}h2{font-size:19px;margin:0 0 14px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;white-space:nowrap}th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right}th{color:var(--muted);font-weight:650;background:#fafbfc}th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}.good{color:var(--green)}.bad{color:var(--red)}code{background:#f2f4f7;padding:2px 5px;border-radius:5px}.note{color:var(--muted)}@media(max-width:850px){.grid{grid-template-columns:repeat(2,1fr)}}
</style></head><body><main class="wrap"><h1>Qwen3-8B 删除步骤实验</h1><p class="lead">600 个步骤 × 2 个条件 × 4 次独立运行；控制组保留目标 step，删除组在目标 step 前截断并从零继续推理。</p>
<section class="grid"><div class="card"><div class="k">不删正确率</div><div class="v">$($c.accuracyPct)%</div><div class="s">$($c.correct) / $($c.n)</div></div><div class="card"><div class="k">删除后正确率</div><div class="v">$($d.accuracyPct)%</div><div class="s">$($d.correct) / $($d.n)</div></div><div class="card"><div class="k">准确率变化</div><div class="v">$([math]::Round($d.accuracyPct-$c.accuracyPct,2)) pp</div><div class="s">deleted − control</div></div><div class="card"><div class="k">平均后续 token（不删 / 删）</div><div class="v">$($c.tokenMean) / $($d.tokenMean)</div><div class="s">P95: $($c.tokenP95) / $($d.tokenP95)</div></div></section>
<section class="panel"><h2>总体结果转移</h2><div class="grid"><div class="card"><div class="k">正确 → 错误</div><div class="v bad">$($t.correctToWrong)</div></div><div class="card"><div class="k">错误 → 正确</div><div class="v good">$($t.wrongToCorrect)</div></div><div class="card"><div class="k">仍然正确</div><div class="v">$($t.stillCorrect)</div></div><div class="card"><div class="k">仍然错误</div><div class="v">$($t.stillWrong)</div></div></div></section>
<section class="panel"><h2>四次独立运行</h2><div class="scroll"><table><thead><tr><th>运行</th><th>正确→错误</th><th>错误→正确</th><th>仍正确</th><th>仍错误</th><th>不删正确率</th><th>删除正确率</th><th>平均 token 不删/删</th><th>无法继续 不删/删</th><th>逻辑断裂 不删/删</th></tr></thead><tbody>$($runRowsHtml -join "`n")</tbody></table></div></section>
<section class="panel"><h2>生成状态与 token</h2><p>不删：无法继续 <b>$($c.cannotContinue)</b>，逻辑断裂 <b>$($c.logicalBreak)</b>；删除：无法继续 <b>$($d.cannotContinue)</b>，逻辑断裂 <b>$($d.logicalBreak)</b>。</p><p>后续可见 token（均值 / 中位数 / P95 / 总计）：不删 <b>$($c.tokenMean) / $($c.tokenMedian) / $($c.tokenP95) / $($c.tokenTotal)</b>；删除 <b>$($d.tokenMean) / $($d.tokenMedian) / $($d.tokenP95) / $($d.tokenTotal)</b>。</p></section>
<section class="panel"><h2>分组结果</h2><div class="scroll"><table><thead><tr><th>维度</th><th>值</th><th>配对数</th><th>不删正确率</th><th>删除正确率</th><th>变化</th><th>正确→错误</th><th>错误→正确</th></tr></thead><tbody>$($subgroupRowsHtml -join "`n")</tbody></table></div></section>
<section class="panel"><h2>实验口径</h2><p class="note">所有生成调用使用同一模型 <code>qwen/qwen3-8b</code>、同一提示词、temperature=0.7、top_p=0.8、max_tokens=2048、<code>/no_think</code>。每个条件和每次运行均为全新会话；删除组从目标 step 前的可见前缀继续，未提供目标 step、未来原推理、参考答案、另一条件输出或此前运行。答案正确性由独立的 Qwen3-8B 判分调用仅根据题目、候选最终答案和参考答案判定（temperature=0）。完整逐条数据见配套 JSONL 和 CSV。</p></section>
</main></body></html>
"@
$htmlPath = "$OutputStem`_报告.html"
[IO.File]::WriteAllText($htmlPath, $html, [Text.UTF8Encoding]::new($false))

[pscustomobject]@{ html=$htmlPath; summary=$summaryPath; pairsCsv=$pairCsv; fullJsonl=$resultJsonl; overall=$overall } | ConvertTo-Json -Depth 8
