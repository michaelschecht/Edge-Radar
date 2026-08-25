#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Recreate the .claude/skills junctions that point at the canonical /skills source.

.DESCRIPTION
    The Edge-Radar Claude Code skills (edge-radar, edge-radar-analysis) live once,
    under /skills at the repo root. Claude Code only discovers skills under
    .claude/skills/, so each is wired up as a Windows directory *junction*
    pointing back to /skills.

    Real symlinks can't be committed here (git core.symlinks=false on Windows),
    so the junctions are git-ignored and the content is tracked exactly once under
    /skills. That means a fresh clone has no junctions yet — run this script once
    after cloning (or after deleting/recreating the skill dirs) to wire them up.

    Idempotent: a junction that already points at the right target is left alone.

.EXAMPLE
    pwsh -File scripts/setup/link_skills.ps1
#>
$ErrorActionPreference = 'Stop'

# Repo root = two levels up from this script (scripts/setup/ -> repo).
$repo   = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$skills = @('edge-radar', 'edge-radar-analysis', 'betting-logic-review')

foreach ($name in $skills) {
    $link   = Join-Path $repo ".claude\skills\$name"
    $target = Join-Path $repo "skills\$name"

    if (-not (Test-Path -LiteralPath $target)) {
        Write-Warning "Source missing: $target - skipping '$name' (is /skills present?)"
        continue
    }

    if (Test-Path -LiteralPath $link) {
        $item = Get-Item -LiteralPath $link -Force
        if ($item.LinkType -eq 'Junction' -and ($item.Target -contains $target)) {
            Write-Host "ok      .claude/skills/$name already linked"
            continue
        }
        Remove-Item -LiteralPath $link -Recurse -Force
    }

    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Write-Host "linked  .claude/skills/$name -> skills/$name"
}

Write-Host "Done. Claude Code will discover the skills under .claude/skills/ via the junctions."
