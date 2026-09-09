# Negative tests for scripts/audit_repository.ps1.
#
# Why this exists: a check that never fires is indistinguishable from a check that passes.
# When these checks were added, four defects were found only by asserting that each one
# actually rejects its violation:
#   1. `Write-Error` under $ErrorActionPreference='Stop' threw, so the script exited 1 and
#      never reached its specific `exit <n>` — this also silently broke the two checks that
#      predated the change.
#   2. A `"` inside the absolute-path regex was mangled by PowerShell's native-argument
#      passing, so the pattern matched NOTHING, including real violations.
#   3. The README check read `git ls-tree HEAD`, which cannot see a newly staged directory —
#      it would have passed on exactly the change it exists to catch.
#   4. (In the test itself) bash `printf` ate `\U` as a unicode escape, corrupting a fixture.
#
# Isolation: every case runs in a throwaway `git worktree`, so the live repository's index
# and working tree are never modified.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Passed = 0
$Failed = [System.Collections.Generic.List[string]]::new()

function Invoke-AuditIn([string] $WorkTree) {
    # Two hazards, both of which killed an earlier version of this harness after its first
    # negative case:
    #   - PowerShell 7.3+ can turn a native command's non-zero exit into a TERMINATING error
    #     while $ErrorActionPreference is 'Stop'. Every case below expects a non-zero exit,
    #     so opt out for the duration of the call.
    #   - The audit writes violations via [Console]::Error, which leaks past `*> $null`.
    #     Merge stderr into the pipeline and discard it instead.
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $prevNative = $null
    if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
        $prevNative = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }
    try {
        pwsh -NoProfile -File (Join-Path $WorkTree 'scripts/audit_repository.ps1') 2>&1 | Out-Null
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prevEap
        if ($null -ne $prevNative) { $PSNativeCommandUseErrorActionPreference = $prevNative }
    }
}

# The worktree is checked out at HEAD, so it carries the COMMITTED audit script. Copy the
# one sitting next to this test over it, so the tests exercise the current working copy
# rather than the last commit — otherwise uncommitted changes go unverified, which is the
# exact blind spot this file exists to close.
function Sync-AuditScript([string] $WorkTree) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'audit_repository.ps1') `
        -Destination (Join-Path $WorkTree 'scripts/audit_repository.ps1') -Force
}

function Test-Case {
    param(
        [Parameter(Mandatory)] [string] $Name,
        [Parameter(Mandatory)] [int] $Expected,
        # Receives the worktree path; stages whatever violation the case needs.
        [Parameter(Mandatory)] [scriptblock] $Setup
    )
    $wt = Join-Path ([System.IO.Path]::GetTempPath()) ("she-audit-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
    git -C $ProjectRoot worktree add --detach --quiet $wt HEAD
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed for case '$Name'" }
    try {
        Sync-AuditScript $wt
        & $Setup $wt
        $actual = Invoke-AuditIn $wt
        if ($actual -eq $Expected) {
            Write-Host "  PASS  $Name -> exit $actual"
            $script:Passed++
        }
        else {
            Write-Host "  FAIL  $Name -> got $actual, want $Expected"
            $script:Failed.Add($Name)
        }
    }
    finally {
        git -C $ProjectRoot worktree remove --force $wt *> $null
        if (Test-Path -LiteralPath $wt) { Remove-Item -LiteralPath $wt -Recurse -Force }
    }
}

function Add-File([string] $WorkTree, [string] $RelPath, [string] $Content) {
    $full = Join-Path $WorkTree $RelPath
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $full) | Out-Null
    # utf8NoBOM: a BOM would make `git grep -I` treat short fixtures inconsistently.
    Set-Content -LiteralPath $full -Value $Content -Encoding utf8NoBOM
    git -C $WorkTree add -f -- $RelPath
    if ($LASTEXITCODE -ne 0) { throw "git add failed for $RelPath" }
}

Write-Host '[audit-test] negative tests for audit_repository.ps1'

Test-Case 'clean worktree passes' 0 { param($wt) }

# exit 3 — per-file size cap. The KG artifacts that reached ~60 MB in aggregate were each
# under the old 50 MB cap, so aggregate size is not what this guards; type/location is.
Test-Case 'file over 5 MB' 3 {
    param($wt)
    $full = Join-Path $wt 'docs/_audittest-big.bin'
    [System.IO.File]::WriteAllBytes($full, (New-Object byte[] (6 * 1024 * 1024)))
    git -C $wt add -f -- 'docs/_audittest-big.bin'
}

# exit 5 — generated artifacts, matched by type and by location.
Test-Case 'artifact by type (.npy at any depth)' 5 {
    param($wt) Add-File $wt 'docs/_audittest.npy' 'x'
}
Test-Case 'artifact by location (knowledge_graph/kg/)' 5 {
    param($wt) Add-File $wt 'backend/knowledge_graph/kg/_audittest.txt' 'x'
}

# exit 6 — absolute drive-letter paths. Built with [char]92 so no shell or PowerShell
# escaping can corrupt the fixture (defect 4 above).
$b = [char]92
Test-Case 'absolute drive-letter path' 6 {
    param($wt)
    Add-File $wt 'docs/_audittest.md' "See C:${b}Users${b}someone${b}project${b}file.txt for details."
}
Test-Case 'known false-positive shapes are allowed' 0 {
    param($wt)
    Add-File $wt 'docs/_audittest2.md' "escape `"discarded:${b}n`" and one segment D:${b}data and bare X:${b} prose"
}

# exit 7 — every component directory must document itself.
Test-Case 'component without README' 7 {
    param($wt) Add-File $wt 'backend/_audittestcomp/x.txt' 'x'
}

Write-Host ''
if ($Failed.Count -gt 0) {
    Write-Host "[audit-test] FAILED: $($Failed -join ', ')"
    exit 1
}
Write-Host "[audit-test] all $Passed negative tests passed"
