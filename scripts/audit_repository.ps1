[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Tracked = @(git -C $ProjectRoot ls-files)
if ($LASTEXITCODE -ne 0) { throw 'git ls-files failed' }

$ForbiddenPath = '(?i)(^|/)(node_modules|__pycache__|\.pytest_cache|\.venv|DerivedData|xcuserdata|\.superpowers)(/|$)|(^|/)\.env$|(^|/)\.env\.(?!example$)[^/]+$|\.(db|sqlite|sqlite3|log|pid|pem|p12|pfx|key)$|(^|/)(id_rsa|id_ed25519)$|conceptnet-assertions-.*\.csv\.gz$'
$BadPaths = @($Tracked | Where-Object { $_ -match $ForbiddenPath })
if ($BadPaths.Count -gt 0) {
    $BadPaths | ForEach-Object { Write-Error "tracked sensitive/generated path: $_" }
    exit 2
}

$Oversized = [System.Collections.Generic.List[string]]::new()
foreach ($relative in $Tracked) {
    $absolute = Join-Path $ProjectRoot $relative
    if ((Get-Item -LiteralPath $absolute).Length -gt 50MB) { $Oversized.Add($relative) }
}
if ($Oversized.Count -gt 0) {
    $Oversized | ForEach-Object { Write-Error "tracked file over 50 MB: $_" }
    exit 3
}

$mergeMarkers = git -C $ProjectRoot grep -n -E '^(<<<<<<<|=======|>>>>>>>)' -- .
if ($LASTEXITCODE -eq 0) {
    $mergeMarkers | ForEach-Object { Write-Error "merge marker: $_" }
    exit 4
}
if ($LASTEXITCODE -ne 1) { throw 'git grep merge-marker scan failed' }

git -C $ProjectRoot diff --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git -C $ProjectRoot diff --cached --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[audit] $($Tracked.Count) tracked files checked; repository audit passed"
