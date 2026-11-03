param(
    [Parameter(Mandatory = $true)]
    [int]$BackendPort,
    [switch]$OfflineData,
    [switch]$SkipPipeline,
    [switch]$Wait
)

# Trigger the in-process daily-update job on the already-running unified
# backend. The update no longer runs as a separate python subprocess and no
# backend restart is needed: the job refreshes artifacts and invalidates the
# backend's in-memory caches by itself.

$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:$BackendPort"

function Invoke-JobStart {
    $body = @{}
    if ($OfflineData) { $body["offline"] = $true }
    if ($SkipPipeline) { $body["skip_pipeline"] = $true }
    $json = $body | ConvertTo-Json -Compress
    Invoke-RestMethod -Uri "$base/api/jobs/daily_update/start" -Method Post -ContentType "application/json" -Body $json -TimeoutSec 10
}

function Get-JobStatus {
    Invoke-RestMethod -Uri "$base/api/jobs/daily_update" -TimeoutSec 10
}

Write-Host "[refresh] Triggering in-process daily update on the unified backend..."
try {
    $started = Invoke-JobStart
    Write-Host ("[refresh] Started job " + $started.job.job_id)
} catch {
    $state = $null
    try { $state = Get-JobStatus } catch { }
    if ($state -and $state.status -eq "running") {
        Write-Host "[refresh] Daily update already running; reusing it."
    } else {
        Write-Warning ("[refresh] Failed to start daily update: " + $_.Exception.Message)
        exit 1
    }
}

if ($Wait) {
    $terminal = @("done", "error", "cancelled")
    while ($true) {
        Start-Sleep -Seconds 2
        $state = Get-JobStatus
        $msg = ""
        if ($state.progress) { $msg = $state.progress.message }
        Write-Host ("[refresh] " + $state.status + " - " + $msg)
        if ($terminal -contains $state.status) {
            if ($state.status -eq "done") {
                Write-Host "[refresh] Daily update completed (no backend restart needed)."
                exit 0
            }
            Write-Warning ("[refresh] Daily update finished with status " + $state.status + ": " + $state.error)
            exit 1
        }
    }
}

Write-Host "[refresh] Daily update is running inside the backend; demo is ready now."
exit 0
