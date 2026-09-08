[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Passed = [System.Collections.Generic.List[string]]::new()
$Skipped = [System.Collections.Generic.List[string]]::new()

function Invoke-Checked {
    param(
        [Parameter(Mandatory)] [string] $Name,
        [Parameter(Mandatory)] [string] $WorkingDirectory,
        [Parameter(Mandatory)] [scriptblock] $Command
    )
    Write-Host "[verify] $Name"
    Push-Location -LiteralPath $WorkingDirectory
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) {
            throw "$Name failed with exit code $LASTEXITCODE"
        }
        $Passed.Add($Name)
    }
    finally {
        Pop-Location
    }
}

Invoke-Checked 'shared contracts' (Join-Path $ProjectRoot 'shared/contracts') {
    python -m pytest (Join-Path $ProjectRoot 'shared/contracts/tests') -q
    if ($LASTEXITCODE -eq 0) { python (Join-Path $ProjectRoot 'shared/contracts/validate_contracts.py') }
}
Invoke-Checked 'device gateway tests' (Join-Path $ProjectRoot 'backend/device_gateway') { npm test }
Invoke-Checked 'device gateway typecheck' (Join-Path $ProjectRoot 'backend/device_gateway') { npm run typecheck }
Invoke-Checked 'device gateway build' (Join-Path $ProjectRoot 'backend/device_gateway') { npm run build }
Invoke-Checked 'parent web tests' (Join-Path $ProjectRoot 'clients/web') { npm test }
Invoke-Checked 'parent web typecheck' (Join-Path $ProjectRoot 'clients/web') { npm run typecheck }
Invoke-Checked 'parent web build' (Join-Path $ProjectRoot 'clients/web') { npm run build }
Invoke-Checked 'RDK X5 runtime' (Join-Path $ProjectRoot 'clients/hardware-rx5') { python -m pytest (Join-Path $ProjectRoot 'clients/hardware-rx5/tests') -q }
Invoke-Checked 'RDK X5 deterministic simulator' (Join-Path $ProjectRoot 'clients/hardware-rx5') { python -m she_device.cli simulate --once }
Invoke-Checked 'interaction engine' (Join-Path $ProjectRoot 'agents/interaction') { python -m pytest (Join-Path $ProjectRoot 'agents/interaction/tests') -q }
Invoke-Checked 'shared memory store' (Join-Path $ProjectRoot 'backend/memory_store') { python -m pytest (Join-Path $ProjectRoot 'backend/memory_store/tests') -q }
Invoke-Checked 'learning director' (Join-Path $ProjectRoot 'agents/director') { npm test }
Invoke-Checked 'learning director typecheck' (Join-Path $ProjectRoot 'agents/director') { npm run typecheck }
Invoke-Checked 'pointing' (Join-Path $ProjectRoot 'backend/pointing') { npm test }
Invoke-Checked 'intel' (Join-Path $ProjectRoot 'backend/intel') { python -m pytest (Join-Path $ProjectRoot 'backend/intel/tests') -q }
Invoke-Checked 'release readiness' $ProjectRoot { & (Join-Path $ProjectRoot 'scripts/release_readiness.ps1') }
# Negative tests for audit_repository.ps1. Without these, a check that silently matches
# nothing is indistinguishable from a check that passes — four such defects were found
# this way. Each case runs in a throwaway git worktree.
Invoke-Checked 'audit self-test' $ProjectRoot { & (Join-Path $ProjectRoot 'scripts/test_audit_repository.ps1') }

Invoke-Checked 'iOS source contract' (Join-Path $ProjectRoot 'clients/ios') {
    $appSources = Join-Path $ProjectRoot 'clients/ios/SHEParentApp'
    $required = rg -n 'accessibilityReduceMotion|accessibilityReduceTransparency|accessibilityLabel|dynamicTypeSize|protocol AppAPI|@Observable' $appSources
    if ($LASTEXITCODE -ne 0) { throw 'required iOS source patterns missing' }
    $deployment = rg -n 'IPHONEOS_DEPLOYMENT_TARGET: "17\.0"' (Join-Path $ProjectRoot 'clients/ios/project.yml')
    if ($LASTEXITCODE -ne 0) { throw 'iOS 17 deployment target missing' }
    $forbidden = rg -n 'SceneKit|RealityKit|UserDefaults.*mastery|print\(.*response|T[O]DO|T[B]D|\.animation\([^,]+\)' $appSources
    if ($LASTEXITCODE -eq 0) { $forbidden; throw 'forbidden iOS source pattern found' }
    $global:LASTEXITCODE = 0
}

if ($IsMacOS -and (Get-Command xcodebuild -ErrorAction SilentlyContinue) -and (Get-Command xcodegen -ErrorAction SilentlyContinue)) {
    Invoke-Checked 'iOS XcodeGen' (Join-Path $ProjectRoot 'clients/ios') { xcodegen generate --spec (Join-Path $ProjectRoot 'clients/ios/project.yml') }
    $Skipped.Add('iOS build/XCTest: use the CI-selected iOS 17+ simulator or run the commands in clients/ios/README.md')
}
else {
    $Skipped.Add("iOS build/XCTest: requires macOS, Xcode, and XcodeGen; current platform is $([System.Environment]::OSVersion.Platform)")
}
$Skipped.Add('physical RDK X5: requires SSH access to the Ubuntu 22 board and operator-approved hardware checks')

Write-Host "[verify] passed $($Passed.Count) checks"
foreach ($item in $Skipped) { Write-Host "[verify] skipped — $item" }
