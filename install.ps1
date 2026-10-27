# 安装 skills/ 下的技能到各工具的技能目录（Windows PowerShell 版）。
#
#   .\install.ps1                     默认装到 $HOME\.workbuddy\skills
#   .\install.ps1 -Workbuddy
#   .\install.ps1 -Agents             $HOME\.agents\skills
#   .\install.ps1 -Claude             $HOME\.claude\skills
#   .\install.ps1 -Codebuddy          $HOME\.codebuddy\skills
#   .\install.ps1 -Dest D:\some\dir
#   .\install.ps1 -Only dify-workflow-dsl
#   .\install.ps1 -DryRun
#   .\install.ps1 -Backup             覆盖前先备份

[CmdletBinding()]
param(
    [switch]$Workbuddy,
    [switch]$Agents,
    [switch]$Claude,
    [switch]$Codebuddy,
    [string]$Dest,
    [string]$Only,
    [switch]$DryRun,
    [switch]$Backup
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$srcDir = Join-Path $repoRoot 'skills'

if (-not (Test-Path $srcDir)) { throw "找不到 $srcDir" }

if (-not $Dest) {
    if ($Agents)    { $Dest = Join-Path $HOME '.agents\skills' }
    elseif ($Claude)    { $Dest = Join-Path $HOME '.claude\skills' }
    elseif ($Codebuddy) { $Dest = Join-Path $HOME '.codebuddy\skills' }
    else                { $Dest = Join-Path $HOME '.workbuddy\skills' }
}

$skills = Get-ChildItem -Path $srcDir -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') }
if ($Only) { $skills = $skills | Where-Object { $_.Name -eq $Only } }
if (-not $skills) { throw '没有可安装的技能（检查 -Only 或 skills/ 目录）' }

$count = 0
foreach ($skill in $skills) {
    $target = Join-Path $Dest $skill.Name
    if ($DryRun) {
        Write-Output "[dry-run] $($skill.Name) -> $target"
        $count++
        continue
    }

    if (-not (Test-Path $Dest)) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }

    if (Test-Path $target) {
        if ($Backup) {
            $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
            $bak = "$target.bak.$stamp"
            Move-Item -LiteralPath $target -Destination $bak
            Write-Output "已备份旧版本 -> $bak"
        }
        else {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }

    Copy-Item -LiteralPath $skill.FullName -Destination $target -Recurse -Force
    Write-Output "已安装 $($skill.Name) -> $target"
    $count++
}

Write-Output "完成：$count 个技能。重启或新开会话后生效。"
