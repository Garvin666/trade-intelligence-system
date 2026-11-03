param(
    [switch]$NoBrowser,
    [switch]$NoWait,
    [int]$Port = 0,
    [switch]$SkipDataRefresh,
    [switch]$OfflineData,
    [switch]$FullUpdate,
    [switch]$WaitForRefresh,
    [switch]$Desktop
)

$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$pidFile = Join-Path $projectRoot "tmp\complete-demo-backend.pid"
$desktopPidFile = Join-Path $projectRoot "tmp\complete-demo-desktop.pid"
$script:DesktopProc = $null
$desktopMode = [bool]$Desktop
$loginPath = if ($env:DEMO_LOGIN_URL) { $env:DEMO_LOGIN_URL } else { "/agent/login.html?v=20260822-starfield-v2" }

function ConvertTo-ProcessArgument([string]$value) {
    if ($value -match " ") {
        return '"' + $value + '"'
    }
    return $value
}

$pythonArgs = @()
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $python = $pythonCmd.Source
    } else {
        $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
        if (-not $pythonCmd) {
            Write-Host "Python 3.10+ not found."
            Write-Host "Install Python first, or create .venv with: python -m venv .venv"
            exit 1
        }
        $python = $pythonCmd.Source
        $pythonArgs = @("-3")
    }
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating local virtual environment (.venv) ..."
    & $python @pythonArgs -m venv (Join-Path $projectRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create .venv."
        exit 1
    }
    $python = $venvPython
    $pythonArgs = @()
}

& $python @pythonArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 3.10+ not found. Please install Python first."
    exit 1
}

function Invoke-PipInstall([string[]]$pipArgs) {
    $commonArgs = @(
        "--disable-pip-version-check",
        "--timeout", "20",
        "--retries", "1"
    )
    & $python @pythonArgs -m pip @pipArgs @commonArgs
    if ($LASTEXITCODE -eq 0) {
        return $true
    }

    $fallbackIndex = if ($env:DEMO_PIP_INDEX_URL) {
        $env:DEMO_PIP_INDEX_URL
    } else {
        "https://pypi.tuna.tsinghua.edu.cn/simple"
    }
    Write-Host "[warn] Default pip source failed. Retrying without the system proxy..."
    $fallbackArgs = @(
        "--index-url", $fallbackIndex,
        "--proxy="
    )
    & $python @pythonArgs -m pip @pipArgs @fallbackArgs @commonArgs
    return ($LASTEXITCODE -eq 0)
}

function Test-Dependencies {
    $dependencyCheck = "import importlib.util as u; mods=('fastapi','uvicorn','pytrends','comtradeapicall','keepa','ebaysdk','statsforecast','mcp'); raise SystemExit(0 if all(u.find_spec(m) for m in mods) else 1)"
    & $python @pythonArgs -c $dependencyCheck 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $false
    }
    if ($desktopMode) {
        & $python @pythonArgs -c "import importlib.util as u; raise SystemExit(0 if u.find_spec('webview') else 1)" 2>$null
        return $LASTEXITCODE -eq 0
    }
    return $true
}

if (-not (Test-Dependencies)) {
    Write-Host "Dependencies missing. Installing requirements ..."
    $requirementsFile = Join-Path $projectRoot "requirements.lock"
    if (-not (Test-Path -LiteralPath $requirementsFile)) {
        $requirementsFile = Join-Path $projectRoot "requirements.txt"
    }
    if (-not (Invoke-PipInstall -pipArgs @("install", "--upgrade", "pip"))) {
        Write-Host "Failed to upgrade pip."
        exit 1
    }
    if (-not (Invoke-PipInstall -pipArgs @("install", "-r", $requirementsFile))) {
        Write-Host "Dependency install failed. Check network and retry."
        exit 1
    }
}

if (-not (Test-Dependencies)) {
    Write-Host "Dependencies are still missing after install."
    exit 1
}

function Test-RequiredFiles {
    $required = @(
        (Join-Path $projectRoot "scripts\run_api.py"),
        (Join-Path $projectRoot "scripts\complete_demo_refresh.ps1"),
        (Join-Path $projectRoot "output\app\index.html")
    )
    foreach ($file in $required) {
        if (-not (Test-Path -LiteralPath $file)) {
            Write-Host "[error] Missing required file: $file"
            return $false
        }
    }
    return $true
}

if (-not (Test-RequiredFiles)) {
    exit 1
}

function Test-Health([int]$port) {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health" -TimeoutSec 2
        return ($r.status -eq "ok" -and $r.service -eq "cross-border-selection-backend")
    } catch {
        return $false
    }
}

# Version fingerprint: current code must expose the dashboard data-depth
# endpoints. An older backend can still report 66 categories but 404 on
# /api/market-intel, so also require the route to exist in OpenAPI.
# Keep this in sync with src/api/app.py routes.
function Test-VersionMatches([int]$port) {
    try {
        $cats = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/categories" -TimeoutSec 5
        $count = @($cats.PSObject.Properties).Count
        $openapi = Invoke-RestMethod -Uri "http://127.0.0.1:$port/openapi.json" -TimeoutSec 5
        $paths = @($openapi.paths.PSObject.Properties.Name)
        return $count -ge 66 -and $paths -contains "/api/market-intel"
    } catch {
        return $false
    }
}

function Stop-OldBackendOnPort([int]$port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($conn) {
        try {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction Stop
            Write-Host "[version] Stopped stale backend PID=$($conn.OwningProcess) on port $port (running older code)."
            Start-Sleep -Milliseconds 800
        } catch {
            Write-Warning "[version] Failed to stop stale backend on port ${port}: $_"
        }
    }
}

function Test-AppReady([int]$port) {
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/app" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) {
                return $true
            }
        } catch {
            # backend up but /app not ready yet; retry
        }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Test-LoginReady([int]$port) {
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port$loginPath" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) {
                return $true
            }
        } catch {
            # backend up but login page not ready yet; retry
        }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

function Test-PortFree([int]$port) {
    try {
        $null = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        return $false
    } catch {
        return $true
    }
}

function Open-Browser([string]$url) {
    if (-not $NoBrowser -and $env:COMPLETE_DEMO_NO_BROWSER -ne "1") {
        Start-Process $url
    }
}

function Start-DesktopWindow([int]$port, [switch]$StopBackendOnClose) {
    $desktopScript = Join-Path $projectRoot "scripts\run_desktop_window.py"
    if (-not (Test-Path -LiteralPath $desktopScript)) {
        Write-Warning "[desktop] Desktop script missing: $desktopScript"
        return $null
    }
    $desktopPython = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
    if (-not (Test-Path -LiteralPath $desktopPython)) {
        $desktopPython = Join-Path (Split-Path -Parent $python) "pythonw.exe"
        if (-not (Test-Path -LiteralPath $desktopPython)) {
            $desktopPython = $python
        }
    }
    $desktopArgs = @(
        (ConvertTo-ProcessArgument $desktopScript),
        "--port", ([string]$port),
        "--browser-fallback",
        "--login-path", (ConvertTo-ProcessArgument $loginPath)
    )
    if ($StopBackendOnClose) {
        $desktopArgs += "--stop-backend-on-close"
    }
    try {
        $proc = Start-Process -FilePath $desktopPython `
            -ArgumentList $desktopArgs `
            -WorkingDirectory $projectRoot `
            -PassThru
        Set-Content -LiteralPath $desktopPidFile -Value $proc.Id -Encoding UTF8
        Write-Host "[desktop] Opening native desktop window on port $port (close window to exit this demo session)."
        return $proc
    } catch {
        Write-Warning "[desktop] Failed to start desktop window: $_"
        return $null
    }
}

function Open-Frontend([string]$url, [int]$port, [bool]$stopBackendOnClose) {
    if ($desktopMode) {
        $script:DesktopProc = Start-DesktopWindow -port $port -StopBackendOnClose:$stopBackendOnClose
        if ($null -eq $script:DesktopProc) {
            Write-Warning "[desktop] Falling back to the default browser."
            Open-Browser $url
        }
        return
    }
    Open-Browser $url
}

function Test-RefreshRunning([int]$port) {
    try {
        $state = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/jobs/daily_update" -TimeoutSec 5
        return ($state.status -eq "running")
    } catch {
        return $false
    }
}

function Start-DataRefresh([int]$port, [switch]$Foreground, [switch]$OfflineData, [switch]$SkipPipeline) {
    $refreshHelper = Join-Path $projectRoot "scripts\complete_demo_refresh.ps1"
    if (-not (Test-Path -LiteralPath $refreshHelper)) {
        Write-Warning "[data] Refresh helper not found: $refreshHelper"
        return $false
    }
    $powershell = (Get-Command powershell.exe -ErrorAction Stop).Source
    $helperArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", (ConvertTo-ProcessArgument $refreshHelper),
        "-BackendPort", ([string]$port)
    )
    if ($OfflineData) {
        $helperArgs += "-OfflineData"
    }
    if ($SkipPipeline) {
        $helperArgs += "-SkipPipeline"
    }
    if ($Foreground) {
        $helperArgs += "-Wait"
        & $powershell @helperArgs
        return ($LASTEXITCODE -eq 0)
    }
    $logDir = Join-Path $projectRoot "tmp"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $refreshLog = Join-Path $logDir "complete-demo-refresh.log"
    $refreshErr = Join-Path $logDir "complete-demo-refresh.err.log"
    Remove-Item -LiteralPath $refreshLog, $refreshErr -Force -ErrorAction SilentlyContinue
    $proc = Start-Process -FilePath $powershell `
        -ArgumentList $helperArgs `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $refreshLog `
        -RedirectStandardError $refreshErr `
        -PassThru
    Set-Content -LiteralPath (Join-Path $logDir "complete-demo-refresh.pid") -Value $proc.Id -Encoding UTF8
    Write-Host "[data] Startup data refresh started in background; Demo opens now."
    return $true
}

function Invoke-StartupRefresh([int]$port) {
    if ($SkipDataRefresh) {
        Write-Host "[data] Startup data refresh skipped (-SkipDataRefresh)."
        return
    }
    $skipPipeline = -not $FullUpdate
    if ($WaitForRefresh) {
        Write-Host "[data] Refreshing to today's latest data (foreground, may take minutes)..."
        $ok = Start-DataRefresh -port $port -Foreground -OfflineData:$OfflineData -SkipPipeline:$skipPipeline
        if (-not $ok) {
            Write-Warning "[data] Refresh did not complete; Demo stays on current data."
        }
    } elseif (Test-RefreshRunning -port $port) {
        Write-Warning "[data] A startup data refresh is already running; reusing it."
    } else {
        if ($OfflineData) {
            Write-Host "[data] Refreshing to today's data (offline, background)..."
        } else {
            Write-Host "[data] Refreshing to today's latest data (online, background)..."
        }
        $null = Start-DataRefresh -port $port -OfflineData:$OfflineData -SkipPipeline:$skipPipeline
    }
}

if ($Port -gt 0) {
    $candidates = @($Port)
} else {
    $candidates = @(8000, 8001, 8010, 8020)
}
$selectedPort = $null
$stalePorts = @()

foreach ($port in $candidates) {
    if (Test-Health $port) {
        if (Test-VersionMatches $port) {
            $selectedPort = $port
            break
        } else {
            Write-Host "[version] Port $port is running an older backend; it will be restarted with current code."
            $stalePorts += $port
        }
    }
}

if (-not $selectedPort) {
    foreach ($port in $stalePorts) {
        Stop-OldBackendOnPort $port
    }
    foreach ($port in $candidates) {
        if (Test-PortFree $port) {
            $selectedPort = $port
            break
        }
    }
}

if (-not $selectedPort) {
    Write-Host "No available port found. Please close programs occupying 8000/8001/8010/8020."
    exit 1
}

if (Test-Health $selectedPort) {
    $url = "http://127.0.0.1:$selectedPort$loginPath"
    if (-not (Test-AppReady -port $selectedPort)) {
        Write-Host "[error] Backend is running but /app is not responding."
        Write-Host "Please check frontend build: output\app\index.html"
        exit 1
    }
    if (-not (Test-LoginReady -port $selectedPort)) {
        Write-Host "[error] Backend is running but the login page is not responding."
        Write-Host "Please check the login page folder mounted at /agent."
        exit 1
    }
    Write-Host "Backend is already running. Opening login page: $url"
    Invoke-StartupRefresh -port $selectedPort
    Open-Frontend -url $url -port $selectedPort -stopBackendOnClose:$false
    if ($desktopMode -and -not $NoWait -and $null -ne $script:DesktopProc) {
        Wait-Process -Id $script:DesktopProc.Id -ErrorAction SilentlyContinue
    }
    exit 0
}

Write-Host "Starting backend on port $selectedPort ..."
$env:BACKEND_PORT = "$selectedPort"

$logDir = Join-Path $projectRoot "tmp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "complete-demo-backend.log"
$errFile = Join-Path $logDir "complete-demo-backend.err.log"
Remove-Item -LiteralPath $logFile, $errFile -Force -ErrorAction SilentlyContinue

$procArgs = $pythonArgs + @("scripts\run_api.py", "--watchdog")
$proc = Start-Process -FilePath $python `
    -ArgumentList $procArgs `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $errFile `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $proc.Id -Encoding UTF8

$healthy = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 250
    if ($proc.HasExited) {
        break
    }
    if (Test-Health $selectedPort) {
        $healthy = $true
        break
    }
}

if (-not $healthy) {
    Write-Host "Backend failed to start."
    if (Test-Path -LiteralPath $logFile) {
        Get-Content -LiteralPath $logFile -Tail 20
    }
    if (Test-Path -LiteralPath $errFile) {
        Get-Content -LiteralPath $errFile -Tail 20
    }
    exit 1
}

if (-not (Test-AppReady -port $selectedPort)) {
    Write-Host "[error] Backend started but /app is not responding."
    Write-Host "Please check frontend build: output\app\index.html"
    if (Test-Path -LiteralPath $logFile) {
        Get-Content -LiteralPath $logFile -Tail 20
    }
    exit 1
}

if (-not (Test-LoginReady -port $selectedPort)) {
    Write-Host "[error] Backend started but the login page is not responding."
    Write-Host "Please check the login page folder mounted at /agent."
    if (Test-Path -LiteralPath $logFile) {
        Get-Content -LiteralPath $logFile -Tail 20
    }
    exit 1
}

$listener = Get-NetTCPConnection -LocalPort $selectedPort -State Listen |
    Select-Object -First 1
if ($listener) {
    Set-Content -LiteralPath $pidFile -Value $listener.OwningProcess -Encoding UTF8
}

$url = "http://127.0.0.1:$selectedPort$loginPath"
Write-Host "Backend started. Opening login page: $url"
Open-Frontend -url $url -port $selectedPort -stopBackendOnClose:$true
Invoke-StartupRefresh -port $selectedPort
Write-Host ""
if ($desktopMode -and -not $NoWait -and $null -ne $script:DesktopProc) {
    Write-Host "Desktop window is running. Closing it stops the backend started by this launcher."
    Wait-Process -Id $script:DesktopProc.Id -ErrorAction SilentlyContinue
} elseif (-not $NoWait) {
    $null = Read-Host "Press Enter to close this launcher (backend keeps running)"
}
