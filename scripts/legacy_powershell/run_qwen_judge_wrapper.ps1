param(
    [int]$ShardIndex,
    [int]$ShardCount = 16,
    [string]$OutputJsonl,
    [string]$LogPath
)
$ErrorActionPreference = "Stop"
try {
    & (Join-Path $PSScriptRoot "run_qwen_deletion_judge_worker.ps1") `
        -InputJsonl (Join-Path $PSScriptRoot "qwen_deletion_generations.jsonl") `
        -InputHtml (Join-Path $PSScriptRoot "prm800k_ai_600_deepseek_v4_pro_reviewed.html") `
        -OutputJsonl $OutputJsonl `
        -Model "qwen/qwen3-8b" `
        -ShardIndex $ShardIndex `
        -ShardCount $ShardCount `
        -BatchSize 8 *>> $LogPath
    exit $LASTEXITCODE
}
catch {
    $_ | Out-String | Add-Content -LiteralPath $LogPath -Encoding UTF8
    exit 1
}
