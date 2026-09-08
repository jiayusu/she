[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$tracked = @(git -C $ProjectRoot ls-files)
if ($LASTEXITCODE -ne 0) { throw 'git ls-files failed' }

$retired = @('engine', 'route', 'kg', 'store', 'po', 'zhihu')
$badPaths = @($tracked | Where-Object {
    $parts = $_ -split '/'
    $parts.Count -gt 1 -and $retired -contains $parts[0]
})
if ($badPaths.Count -gt 0) { throw "retired top-level paths are still tracked: $($badPaths -join ', ')" }

$codeFiles = @($tracked | Where-Object { $_ -match '\.(py|ts|tsx|js|mjs|swift|ps1|yml|yaml|json)$' })
$stale = [System.Collections.Generic.List[string]]::new()
foreach ($relative in $codeFiles) {
    $absolute = Join-Path $ProjectRoot $relative
    if (-not (Test-Path -LiteralPath $absolute)) { continue }
    $lineNo = 0
    foreach ($line in Get-Content -LiteralPath $absolute) {
        $lineNo++
        if ($line -match '(?i)(A:\\working\\she\\(engine|route|kg|store|po|zhihu)|(?:^|["''`])\.\.?[\\/](engine|route|kg|store|po|zhihu)[\\/])' -and $line -notmatch 'legacy|retired|migration') {
            $stale.Add("$relative`:$lineNo")
        }
    }
}
if ($stale.Count -gt 0) { throw "stale legacy operational references: $($stale -join ', ')" }

$secretPatterns = @('OPENAI_API_KEY\s*=\s*[^$\s]+', 'Bearer\s+[A-Za-z0-9._-]{16,}')
foreach ($relative in $tracked) {
    if ($relative -match '(^|/)(\.env|.*\.pem|.*\.key)$') { throw "secret-like tracked path: $relative" }
}
Write-Host "[release] canonical paths, legacy references, and tracked secret paths checked"
