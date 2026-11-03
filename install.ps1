# 安装 skills/ 下的技能到各工具的技能目录（Windows PowerShell 版）。
#
#   .\install.ps1                     自动扫描所有已安装工具的 skills 目录，逐个安装（默认）
#   .\install.ps1 -List               只列出扫描到的安装位置，不安装
#   .\install.ps1 -Project            额外把当前项目的工具级目录纳入扫描
#   .\install.ps1 -Workbuddy          只装 $HOME\.workbuddy\skills
#   .\install.ps1 -Agents             只装 $HOME\.agents\skills
#   .\install.ps1 -Claude             只装 $HOME\.claude\skills
#   .\install.ps1 -Codebuddy          只装 $HOME\.codebuddy\skills
#   .\install.ps1 -Qoder              只装 $HOME\.qoder\skills
#   .\install.ps1 -Dest D:\some\dir   只装到自定义目录
#   .\install.ps1 -Only dify-workflow-dsl
#   .\install.ps1 -DryRun
#   .\install.ps1 -Backup             覆盖前先备份

[CmdletBinding()]
param(
    [switch]$Workbuddy,
    [switch]$Agents,
    [switch]$Claude,
    [switch]$Codebuddy,
    [switch]$Qoder,
    [string]$Dest,
    [string]$Only,
    [switch]$Project,
    [switch]$List,
    [switch]$DryRun,
    [switch]$Backup
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcDir = Join-Path $repoRoot 'skills'
$projectRoot = (Get-Location).Path

if (-not (Test-Path $srcDir)) { throw "找不到 $srcDir" }

# 常见工具的用户级 skills 目录。命中规则：目标父目录存在即认为该工具在用
#（可能还没建过 skills\ 子目录，安装时会创建）；父目录不存在则跳过。
function Get-UserTargets {
    @(
        @{ Name = 'workbuddy'; Path = (Join-Path $HOME '.workbuddy\skills'); Label = 'WorkBuddy' }
        @{ Name = 'agents';    Path = (Join-Path $HOME '.agents\skills');    Label = 'OpenClaw / Claude Code 风格通用目录' }
        @{ Name = 'claude';    Path = (Join-Path $HOME '.claude\skills');    Label = 'Claude Code' }
        @{ Name = 'codebuddy'; Path = (Join-Path $HOME '.codebuddy\skills'); Label = 'CodeBuddy' }
        @{ Name = 'qoder';     Path = (Join-Path $HOME '.qoder\skills');     Label = 'Qoder Desktop' }
        @{ Name = 'cursor';    Path = (Join-Path $HOME '.cursor\skills');    Label = 'Cursor' }
        @{ Name = 'gemini';    Path = (Join-Path $HOME '.gemini\skills');    Label = 'Gemini CLI' }
        @{ Name = 'codex';     Path = (Join-Path $HOME '.codex\skills');     Label = 'Codex CLI' }
    )
}

# 项目级目录：只在当前工作区里存在才命中
function Get-ProjectTargets {
    @(
        @{ Name = 'project-agents';    Path = (Join-Path $projectRoot '.agents\skills');    Label = '项目级通用目录' }
        @{ Name = 'project-claude';    Path = (Join-Path $projectRoot '.claude\skills');    Label = '项目级 Claude Code' }
        @{ Name = 'project-codebuddy'; Path = (Join-Path $projectRoot '.codebuddy\skills'); Label = '项目级 CodeBuddy' }
        @{ Name = 'project-workbuddy'; Path = (Join-Path $projectRoot '.workbuddy\skills'); Label = '项目级 WorkBuddy' }
        @{ Name = 'project-qoder';     Path = (Join-Path $projectRoot '.qoder\skills');     Label = '项目级 Qoder' }
    )
}

function Test-Target {
    param([hashtable]$Target)
    if (Test-Path $Target.Path) { return 'HIT' }          # skills 目录已存在（覆盖更新）
    if (Test-Path (Split-Path -Parent $Target.Path)) { return 'NEW' }  # 工具在用（将新建）
    return 'MISS'                                          # 工具都没装（跳过）
}

function Show-Scan {
    param([string]$Scope, [array]$Targets)
    $hits = 0
    $news = 0
    $misses = 0
    Write-Output "扫描到的 skills 安装位置（$Scope）："
    foreach ($t in $Targets) {
        switch (Test-Target $t) {
            'HIT' {
                $hits++
                Write-Output ("  [装] {0,-40} {1}（已有，覆盖更新）" -f $t.Path, $t.Label)
            }
            'NEW' {
                $news++
                Write-Output ("  [新] {0,-40} {1}（工具在用，将新建 skills 子目录）" -f $t.Path, $t.Label)
            }
            default {
                $misses++
                $parent = Split-Path -Parent $t.Path
                Write-Output ("  [跳] {0,-40} {1}（未检测到 {2}）" -f $t.Path, $t.Label, $parent)
            }
        }
    }
    Write-Output "  命中 $hits 个，新建 $news 个，跳过 $misses 个"
}

$explicit = @()
if (-not $Dest) {
    if ($Workbuddy) { $explicit += (Join-Path $HOME '.workbuddy\skills') }
    if ($Agents)    { $explicit += (Join-Path $HOME '.agents\skills') }
    if ($Claude)    { $explicit += (Join-Path $HOME '.claude\skills') }
    if ($Codebuddy) { $explicit += (Join-Path $HOME '.codebuddy\skills') }
    if ($Qoder)     { $explicit += (Join-Path $HOME '.qoder\skills') }
}

$targets = @()
$autoTargets = @()
if ($Dest) {
    $targets = @($Dest)
}
elseif ($explicit.Count -gt 0) {
    $targets = $explicit
}
else {
    $candidates = @(Get-UserTargets)
    if ($Project) { $candidates += @(Get-ProjectTargets) }
    $autoTargets = @($candidates | Where-Object { (Test-Target $_) -ne 'MISS' } | ForEach-Object { $_.Path })
    $targets = $autoTargets
}

if ($List) {
    Write-Output '用户级位置：'
    Show-Scan -Scope '用户级' -Targets (Get-UserTargets)
    if ($Project) {
        Write-Output ''
        Write-Output '项目级位置：'
        Show-Scan -Scope '项目级' -Targets (Get-ProjectTargets)
    }
    Write-Output ''
    Write-Output '会安装到的目标：'
    if ($autoTargets.Count -eq 0) { Write-Output '  （无）' }
    else { foreach ($t in $autoTargets) { Write-Output "  $t" } }
    exit 0
}

if ($targets.Count -eq 0) {
    $fallback = Join-Path $HOME '.agents\skills'
    $targets = @($fallback)
    Write-Error "没有扫描到已安装工具的 skills 目录，回退到 $fallback。"
}

$skills = Get-ChildItem -Path $srcDir -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') }
if ($Only) { $skills = $skills | Where-Object { $_.Name -eq $Only } }
if (-not $skills) { throw '没有可安装的技能（检查 -Only 或 skills/ 目录）' }

$count = 0
foreach ($dest in $targets) {
    Write-Output "-> $dest"
    foreach ($skill in $skills) {
        $target = Join-Path $dest $skill.Name
        if ($DryRun) {
            Write-Output "  [dry-run] $($skill.Name) -> $target"
            $count++
            continue
        }

        if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }

        if (Test-Path $target) {
            if ($Backup) {
                $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
                $bak = "$target.bak.$stamp"
                Move-Item -LiteralPath $target -Destination $bak
                Write-Output "  已备份旧版本 -> $bak"
            }
            else {
                Remove-Item -LiteralPath $target -Recurse -Force
            }
        }

        Copy-Item -LiteralPath $skill.FullName -Destination $target -Recurse -Force
        Write-Output "  已安装 $($skill.Name) -> $target"
        $count++
    }
}

Write-Output "完成：$count 个技能。重启或新开会话后生效。"
if (-not $Project -and -not $DryRun) {
    Write-Output '提示：-Project 可额外装到当前项目下的工具级目录。'
}
