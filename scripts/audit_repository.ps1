[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Tracked = @(git -C $ProjectRoot ls-files)
if ($LASTEXITCODE -ne 0) { throw 'git ls-files failed' }

# Report a violation on stderr WITHOUT throwing.
#
# `Write-Error` raises a terminating error while $ErrorActionPreference is 'Stop', so the
# script died with exit 1 before reaching the specific `exit <n>` below it. Every distinct
# exit code in this file was unreachable — including the two checks that predate this
# function. Verified: `Write-Error` in a ForEach-Object then `exit 5` yields 1;
# `[Console]::Error.WriteLine` yields 5.
function Report([string] $Message) { [Console]::Error.WriteLine($Message) }

$ForbiddenPath = '(?i)(^|/)(node_modules|__pycache__|\.pytest_cache|\.venv|DerivedData|xcuserdata|\.superpowers)(/|$)|(^|/)\.env$|(^|/)\.env\.(?!example$)[^/]+$|\.(db|sqlite|sqlite3|log|pid|pem|p12|pfx|key)$|(^|/)(id_rsa|id_ed25519)$|conceptnet-assertions-.*\.csv\.gz$'
$BadPaths = @($Tracked | Where-Object { $_ -match $ForbiddenPath })
if ($BadPaths.Count -gt 0) {
    $BadPaths | ForEach-Object { Report "tracked sensitive/generated path: $_" }
    exit 2
}

# 5 MB, not 50 MB. The KG build artifacts that reached ~60 MB in aggregate were each
# well under 50 MB (largest ~8 MB), so a per-file cap that high never fired. The largest
# legitimately tracked file is ~320 KB (backend/knowledge_graph/raw/*.csv).
$SizeCap = 5MB
$Oversized = [System.Collections.Generic.List[string]]::new()
foreach ($relative in $Tracked) {
    $absolute = Join-Path $ProjectRoot $relative
    if ((Get-Item -LiteralPath $absolute).Length -gt $SizeCap) { $Oversized.Add($relative) }
}
if ($Oversized.Count -gt 0) {
    $Oversized | ForEach-Object { Report "tracked file over 5 MB: $_" }
    exit 3
}

# Generated model/index/graph artifacts. The ignore rules were once anchored at
# `data/`, so an identical set committed under `kg/data/` evaded every one of them.
# Match by type and location instead of by exact path.
$ForbiddenArtifact = '(?i)\.(npy|idx|pt|graphml)$|(^|/)knowledge_graph/kg/|(^|/)(embeddings|snapshots|packs)/|(^|/)edges_candidates\.csv\.gz$|(^|/)llm_clean_decisions[^/]*\.jsonl$'
$BadArtifacts = @($Tracked | Where-Object { $_ -match $ForbiddenArtifact })
if ($BadArtifacts.Count -gt 0) {
    $BadArtifacts | ForEach-Object { Report "tracked build artifact (regenerate it, do not commit it): $_" }
    exit 5
}

# Absolute drive-letter paths are not portable: the repository is cloned to arbitrary
# locations and CI runs on Linux (AGENTS.md §39).
#
# The pattern requires a drive letter NOT preceded by another letter, plus at least two
# path segments. Both parts are deliberate — a looser rule produced three false positives
# that are all legitimate content in this repository:
#   - `"...discarded:\n"`  a word ending in a letter, then a colon and an escape
#   - `# 如 D:\data`        a single-segment illustration in a comment
#   - `X:\` in prose        a bare example with no path segments
# The lookbehind does most of the work: ordinary prose colons follow a word ending in a
# letter, so only single-letter tokens can trigger.
#
# The character class deliberately contains NO double quote. An earlier version used a
# negated class `[^\\/:*?"<>|\r\n]+`, and PowerShell's native-argument passing mangled the
# embedded quote so the pattern silently matched NOTHING — including real violations. A
# check that never fires looks exactly like a check that passes; only the negative test
# below caught it. Keep this pattern quote-free.
#
# `scripts/` is excluded because it holds this rule and its sibling detector in
# release_readiness.ps1; `docs/archive/` and `playbooks/` are excluded because they are
# historical records whose then-current paths must not be rewritten (INC-0006: never scan
# a policy's own explanatory text with the policy's literal rule).
$absolutePathHits = git -C $ProjectRoot grep -n -I -P '(?<![A-Za-z])[A-Za-z]:[\\/][A-Za-z0-9_.~ -]+[\\/]' -- . ':!scripts' ':!docs/archive' ':!playbooks'
if ($LASTEXITCODE -eq 0) {
    $absolutePathHits | ForEach-Object { Report "absolute drive-letter path (use a repo-relative path): $_" }
    exit 6
}
if ($LASTEXITCODE -ne 1) {
    # The pattern needs a lookbehind, so it requires a git built with PCRE (`-P`). Exit
    # codes other than 0/1 usually mean `-P` is unavailable rather than a violation.
    throw "git grep absolute-path scan failed (exit $LASTEXITCODE); this check requires a git built with PCRE support for -P"
}

# Every component directory must document itself: what it owns, how to run it, how to
# test it. Five component READMEs were once superseded PRDs describing a forbidden
# architecture, and three components had no README at all.
# Derived from the index ($Tracked), not from `git ls-tree HEAD`: ls-tree reads the last
# commit, so a newly staged component directory would be invisible and the check would
# pass on exactly the change it exists to catch.
$ComponentDirs = @(
    $Tracked |
        Where-Object { $_ -match '^(agents|backend|clients)/[^/]+/' } |
        ForEach-Object { ($_ -split '/')[0..1] -join '/' }
    'shared/contracts'
) | Sort-Object -Unique
$MissingReadme = @($ComponentDirs | Where-Object { $Tracked -notcontains "$_/README.md" })
if ($MissingReadme.Count -gt 0) {
    $MissingReadme | ForEach-Object { Report "component has no tracked README.md: $_" }
    exit 7
}

# Match actual Git conflict markers only. Long `====` section rules in
# docs/archive/program-methodology.md and other docs are valid.
$mergeMarkers = git -C $ProjectRoot grep -n -E '^(<<<<<<<|>>>>>>>|=======$)' -- .
if ($LASTEXITCODE -eq 0) {
    $mergeMarkers | ForEach-Object { Report "merge marker: $_" }
    exit 4
}
if ($LASTEXITCODE -ne 1) { throw 'git grep merge-marker scan failed' }

git -C $ProjectRoot diff --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git -C $ProjectRoot diff --cached --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[audit] $($Tracked.Count) tracked files checked; repository audit passed"
