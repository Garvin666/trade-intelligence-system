param(
    [string]$PackagePath = "发布与材料\完整Demo运行包",
    [int]$Port = 8023,
    [string]$Python = "",
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"

$pkg = (Resolve-Path -LiteralPath $PackagePath -ErrorAction Stop).Path
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $Python = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found: $Python"
}
if (-not (Test-Path -LiteralPath (Join-Path $pkg "scripts\run_api.py"))) {
    throw "run_api.py not found in package: $pkg"
}

function Get-RelativeFiles([string]$base) {
    $ignoreSegments = @(
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "node_modules",
        "dist",
        "dist-offline",
        ".vite",
        "crawlee_storage",
        "hf"
    )
    Get-ChildItem -LiteralPath $base -Recurse -File -ErrorAction Stop |
        ForEach-Object {
            $relative = $_.FullName.Substring($base.Length + 1)
            $segments = $relative -split "\\"
            if (-not ($segments | Where-Object { $ignoreSegments -contains $_ })) {
                $relative.Replace("\", "/")
            }
        } |
        Where-Object { $_ } |
        Sort-Object
}

foreach ($dir in @("src", "scripts", "tests")) {
    $rootList = @(Get-RelativeFiles (Join-Path $repoRoot $dir))
    $pkgList = @(Get-RelativeFiles (Join-Path $pkg $dir))
    $diff = Compare-Object -ReferenceObject $rootList -DifferenceObject $pkgList
    if ($diff) {
        $diff | ForEach-Object {
            Write-Host ("{0}: {1} {2}" -f $dir, $_.SideIndicator, $_.InputObject)
        }
        throw "package/$dir differs from repository root"
    }
}

$keyFiles = @(
    "README.md",
    "AGENTS.md",
    "CONTEXT.md",
    ".env.example",
    "start_complete_demo.ps1",
    "stop_complete_demo.ps1",
    "一键启动.bat",
    "pytest.ini",
    "requirements.txt",
    "requirements.lock"
)
foreach ($name in $keyFiles) {
    $rootHash = (Get-FileHash -LiteralPath (Join-Path $repoRoot $name) -Algorithm SHA256).Hash
    $pkgHash = (Get-FileHash -LiteralPath (Join-Path $pkg $name) -Algorithm SHA256).Hash
    if ($rootHash -ne $pkgHash) {
        throw "package/$name hash differs from repository root"
    }
}

Write-Host "Package consistency OK: src/scripts/tests identical, $($keyFiles.Count) key files hash match."
if ($SkipSmoke) {
    exit 0
}

$logDir = Join-Path $pkg "tmp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$outLog = Join-Path $logDir "verify-backend.log"
$errLog = Join-Path $logDir "verify-backend.err.log"
Remove-Item -LiteralPath $outLog, $errLog -Force -ErrorAction SilentlyContinue

$env:BACKEND_PORT = [string]$Port
$proc = Start-Process -FilePath $Python `
    -ArgumentList @("scripts\run_api.py", "--serve") `
    -WorkingDirectory $pkg `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -PassThru

try {
    $healthy = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
            if ($health.status -eq "ok") {
                $healthy = $true
                break
            }
        } catch {
            # not ready yet
        }
    }
    if (-not $healthy) {
        Write-Host "Backend did not become healthy."
        if (Test-Path -LiteralPath $errLog) {
            Get-Content -LiteralPath $errLog -Tail 30
        }
        throw "health check failed"
    }

    $app = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/app" -UseBasicParsing -TimeoutSec 5
    $login = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/agent/login.html" -UseBasicParsing -TimeoutSec 5
    $loginBody = @{ username = "admin"; password = "123456" } | ConvertTo-Json
    $loginApi = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/agent/api/login" -Method Post -ContentType "application/json" -Body $loginBody -TimeoutSec 5
    $categories = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/categories" -TimeoutSec 5
    $dataStatus = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/data/status" -TimeoutSec 5
    $recommendations = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/recommendations?limit=3" -TimeoutSec 10
    $marketIntel = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/market-intel?limit=2" -TimeoutSec 10

    [PSCustomObject]@{
        Health       = $health.status
        Service      = $health.service
        AppStatus    = $app.StatusCode
        AppBytes     = $app.RawContentLength
        LoginStatus  = $login.StatusCode
        LoginTokenOk = [bool]$loginApi.access_token
        Categories   = @($categories.PSObject.Properties).Count
        DataAsOf     = $dataStatus.data_as_of
        Snapshot     = $dataStatus.snapshot_path
        RecRows      = @($recommendations).Count
        MarketRows   = @($marketIntel.rankings.items).Count
    } | Format-List
} finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}
