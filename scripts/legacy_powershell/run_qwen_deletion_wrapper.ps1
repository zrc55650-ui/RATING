param(
    [int]$ShardIndex,
    [int]$ShardCount = 16,
    [string]$OutputJsonl,
    [string]$LogPath,
    [string]$KeyFile = ""
)

$ErrorActionPreference = "Stop"
try {
    if (-not [string]::IsNullOrWhiteSpace($KeyFile)) {
        $env:OPENROUTER_API_KEY = [IO.File]::ReadAllText($KeyFile, [Text.Encoding]::UTF8).Trim()
        Remove-Item -LiteralPath $KeyFile -Force
    }
    & (Join-Path $PSScriptRoot "run_qwen_deletion_worker.ps1") `
        -InputHtml (Join-Path $PSScriptRoot "prm800k_ai_600_deepseek_v4_pro_reviewed.html") `
        -OutputJsonl $OutputJsonl `
        -Model "qwen/qwen3-8b" `
        -ShardIndex $ShardIndex `
        -ShardCount $ShardCount `
        -Runs 4 `
        -Temperature 0.7 `
        -TopP 0.8 *>> $LogPath
    exit $LASTEXITCODE
}
catch {
    $_ | Out-String | Add-Content -LiteralPath $LogPath -Encoding UTF8
    exit 1
}
