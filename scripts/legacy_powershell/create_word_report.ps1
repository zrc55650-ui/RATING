$ErrorActionPreference = 'Stop'
$out = Join-Path (Get-Location) '推理步骤删除实验_过程与数据分析报告.docx'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $word.Documents.Add()
$selection = $word.Selection
$selection.Font.Name = 'Microsoft YaHei'
$selection.Font.Size = 10.5

function Add-Text([string]$text, [int]$size = 10, [bool]$bold = $false) {
    $script:selection.Font.Size = $size
    $script:selection.Font.Bold = [int]$bold
    $script:selection.TypeText($text)
    $script:selection.TypeParagraph()
    $script:selection.Font.Bold = 0
}

function Add-Table([string[]]$headers, [object[]]$rows) {
    $table = $script:doc.Tables.Add($script:selection.Range, $rows.Count + 1, $headers.Count)
    $table.Borders.Enable = 1
    for ($j = 0; $j -lt $headers.Count; $j++) {
        $table.Cell(1, $j + 1).Range.Text = $headers[$j]
        $table.Cell(1, $j + 1).Range.Font.Bold = 1
    }
    for ($i = 0; $i -lt $rows.Count; $i++) {
        for ($j = 0; $j -lt $headers.Count; $j++) {
            $table.Cell($i + 2, $j + 1).Range.Text = [string]$rows[$i][$j]
        }
    }
    $script:selection.SetRange($script:doc.Content.End - 1, $script:doc.Content.End - 1)
    $script:selection.TypeParagraph()
}

try {
    Add-Text '推理步骤删除实验：过程与数据分析报告' 18 $true
    Add-Text '日期：2026-07-21；实验执行：2026-07-20'
    Add-Text '一、实验目的' 14 $true
    Add-Text '本实验检验：在数学推理轨迹中删除一个目标步骤后，模型仅依据该步骤之前的前缀继续推理，最终答案的正确率是否改变。同时比较 PRM rating（1、0、−1）与步骤类型（essential、redundant、harmful）的对应关系，并评估人工示例校准对初始 AI 标注的影响。'
    Add-Text '二、实验过程' 14 $true
    Add-Text '1. 样本：从 PRM800K 构建600个目标步骤，rating=1、0、−1各200个，并覆盖early、middle、late三种位置。'
    Add-Text '2. 初始标注：DeepSeek V4 Flash标注415条、V4 Pro标注185条，为每一步给出removable与step type。'
    Add-Text '3. 人工校准：75条已完成的人工标注作为示例，DeepSeek V4 Flash对600条进行盲测复标。人工示例中，可删45条、不可删30条；essential 29条、harmful 19条、redundant 27条。'
    Add-Text '4. 删除实验：Qwen3-8B在每个样本上进行4次独立运行；每次包含保留目标步骤（control）和在目标步骤之前截断（deleted）两个条件。共2,400对、4,800次生成。两条件共享模型、提示词、temperature=0.7、top_p=0.8、max_tokens=2048和/no_think。'
    Add-Text '5. 判定：独立Qwen3-8B判定器以temperature=0判断最终答案与参考答案是否数学等价。'
    Add-Text '三、总体实验结果' 14 $true
    Add-Table @('指标','保留目标步骤','删除目标步骤','删除−保留') @(
        @('正确答案','1,353 / 2,400','1,526 / 2,400','+173'),
        @('准确率','56.38%','63.58%','+7.20 pp'),
        @('平均可见输出 token','326.36','313.38','−12.98（−3.98%）'),
        @('无法继续','125','120','−5'),
        @('逻辑断裂','65','26','−39')
    )
    Add-Text '配对转移：错误→正确377对；正确→错误204对；仍正确1,149对；仍错误670对。在581个两条件不一致的配对中，改善明显多于恶化。四次独立运行的准确率变化为+7.16、+7.67、+5.00、+9.00 pp，方向均为正。'
    Add-Text '四、rating × type 的对应关系（校准后；按1 / 0 / −1排列）' 14 $true
    Add-Table @('rating','essential','redundant','harmful','合计') @(
        @('1','118（59.0%）','69（34.5%）','13（6.5%）','200'),
        @('0','55（27.5%）','115（57.5%）','30（15.0%）','200'),
        @('−1','25（12.5%）','15（7.5%）','160（80.0%）','200'),
        @('合计','198','199','203','600')
    )
    Add-Text '表格呈清晰对角线：rating=1主要对应essential，rating=0主要对应redundant，rating=−1主要对应harmful。对角线三格共有393/600（65.5%）。按−1、0、1对rating编码，按harmful、redundant、essential对类型编码，相关系数r=0.599；列联表χ²(4)=334.93，Cramér’s V=0.528，p<0.001。关联较强，但仍有34.5%处于非对角线，因此rating不能直接等同于类型或删除决策。'
    Add-Text '五、初始标注与人工示例校准后的比较' 14 $true
    Add-Table @('指标','初始AI标注','校准后','变化') @(
        @('可删除 yes','261（43.5%）','392（65.3%）','+131'),
        @('essential','165（27.5%）','198（33.0%）','+33'),
        @('redundant','201（33.5%）','199（33.2%）','−2'),
        @('harmful','234（39.0%）','203（33.8%）','−31'),
        @('可删除标签一致','357（59.5%）','—','243条翻转'),
        @('步骤类型一致','436（72.7%）','—','164条翻转')
    )
    Add-Text '校准主要将“不可删”修正为“可删”：187条no→yes，56条yes→no。初始标签偏保守；删除实验按初始标签分组的结论需结合此不稳定性理解。'
    Add-Text '六、按rating的删除实验比较（初始分层；按1 / 0 / −1排列）' 14 $true
    Add-Table @('rating','样本数','保留准确率','删除准确率','变化','错误→正确 / 正确→错误') @(
        @('1','200','72.75%','72.12%','−0.62 pp','73 / 78'),
        @('0','200','65.25%','65.50%','+0.25 pp','91 / 89'),
        @('−1','200','31.12%','53.12%','+22.00 pp','213 / 37')
    )
    Add-Text '总体增益并非三个rating组平均共享，主要来自rating=−1；rating=0基本持平，rating=1略降。因此低分步骤可优先作为删除候选，但不能推广为无条件删除。'
    Add-Text '七、按步骤类型的删除实验比较' 14 $true
    Add-Table @('type','样本数','保留准确率','删除准确率','变化','错误→正确 / 正确→错误') @(
        @('essential','165','64.55%','63.33%','−1.21 pp','68 / 76'),
        @('redundant','201','72.89%','74.00%','+1.12 pp','79 / 70'),
        @('harmful','234','36.43%','54.81%','+18.38 pp','230 / 58')
    )
    Add-Text 'harmful是最强的正向删除信号；essential平均为轻微负向；redundant接近中性。'
    Add-Text '八、重点交叉格比较' 14 $true
    Add-Table @('rating × type','样本数','保留准确率','删除准确率','变化','错误→正确 / 正确→错误') @(
        @('1 × redundant','72','81.25%','81.60%','+0.35 pp','23 / 22'),
        @('0 × essential','41','58.54%','52.44%','−6.10 pp','16 / 26'),
        @('−1 × harmful','178','28.51%','51.83%','+23.31 pp','194 / 28')
    )
    Add-Text '1×redundant几乎中性，适合为了压缩篇幅尝试删除，但不能声称会提升正确率。0×essential出现明确负向信号，说明0分步骤仍可能承担必要计算或推理连接，默认不应删除。−1×harmful改善最大，最符合删除污染后续推理的错误步骤这一机制解释。'
    Add-Text '九、其他发现、限制与结论' 14 $true
    Add-Text '位置方面，early/middle/late的变化分别为+4.98/+9.45/+7.20 pp。token总量减少31,156（−3.98%），但1,271/2,400个删除条件反而使用更多token，说明删除改变了生成路径，而非纯粹缩短回答。实验测量的是从截断前缀继续生成的效果，不等同于在完整既有答案中机械删除一句。对小交叉格应进行更多人工盲标和重抽样验证。'
    Add-Text '可执行建议：将rating×type对角线作为候选排序而非硬规则；优先复核或删除−1×harmful；对0×essential默认保留；对1×redundant可以为了压缩而尝试删除，但应保留结果验证与回退机制。'
    $doc.SaveAs2($out, 16)
    $doc.Close()
    $word.Quit()
    Get-Item -LiteralPath $out | Select-Object Name, Length, LastWriteTime
}
catch {
    if ($doc) { $doc.Close($false) }
    if ($word) { $word.Quit() }
    throw
}
