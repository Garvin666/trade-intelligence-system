param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$pidFile = Join-Path $root "tmp\complete-demo-backend.pid"
$frontendPidFile = Join-Path $root "tmp\complete-demo-frontend.pid"
$refreshPidFile = Join-Path $root "tmp\complete-demo-refresh.pid"
$desktopPidFile = Join-Path $root "tmp\complete-demo-desktop.pid"
$actionVerb = if ($DryRun) { "Would stop" } else { "Stopped" }

function Stop-RecordedProcess([string]$pidFilePath, [string]$label) {
    if (-not (Test-Path -LiteralPath $pidFilePath)) {
        Write-Host "No $label PID recorded by the launcher."
        return
    }
    $pidValue = (Get-Content -LiteralPath $pidFilePath -Raw).Trim()
    try {
        $proc = Get-Process -Id ([int]$pidValue) -ErrorAction Stop
        if (-not $DryRun) {
            Stop-Process -Id $proc.Id -Force
        }
        Write-Host "$actionVerb $label PID=$pidValue"
    } catch {
        Write-Host "$label process not found (stale PID file)."
    }
    if (-not $DryRun) {
        Remove-Item -LiteralPath $pidFilePath -Force -ErrorAction SilentlyContinue
    }
}

Stop-RecordedProcess -pidFilePath $pidFile -label "backend"
Stop-RecordedProcess -pidFilePath $refreshPidFile -label "startup refresh helper"
Stop-RecordedProcess -pidFilePath $desktopPidFile -label "desktop window"

$desktopProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '^(python|pyw)\.exe$' -and
        $_.CommandLine -and
        $_.CommandLine -match 'run_desktop_window\.py'
    }
foreach ($desktopProc in $desktopProcs) {
    if (-not $DryRun) {
        Stop-Process -Id $desktopProc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "$actionVerb desktop window PID=$($desktopProc.ProcessId)"
}

$refreshProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '^(python|py)\.exe$' -and
        $_.CommandLine -and
        $_.CommandLine -match 'run_daily_update\.py'
    }
foreach ($refreshProc in $refreshProcs) {
    if (-not $DryRun) {
        Stop-Process -Id $refreshProc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "$actionVerb startup data refresh PID=$($refreshProc.ProcessId)"
}

$backendProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '^(python|py)\.exe$' -and
        $_.CommandLine -and
        $_.CommandLine -match 'run_api\.py|scripts\.run_api'
    }
foreach ($backendProc in $backendProcs) {
    if (-not $DryRun) {
        Stop-Process -Id $backendProc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "$actionVerb backend PID=$($backendProc.ProcessId)"
}

Stop-RecordedProcess -pidFilePath $frontendPidFile -label "frontend dev server"

$frontendDir = Join-Path $root "frontend"
$frontendProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match 'vite' -and
        $_.CommandLine -match [regex]::Escape($frontendDir)
    }
foreach ($frontendProc in $frontendProcs) {
    if (-not $DryRun) {
        Stop-Process -Id $frontendProc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "$actionVerb frontend dev server PID=$($frontendProc.ProcessId)"
}

if ($DryRun) {
    Write-Host "[dry-run] Preview complete. No processes were stopped."
}
