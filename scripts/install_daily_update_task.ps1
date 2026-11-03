param(
    [string]$TaskName = "TradeAI_DailyDataUpdate",
    [string]$Time = "08:00"
)

$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root "scripts\run_daily_update.py"

$python = Join-Path $root ".venv\Scripts\python.exe"
$pythonArgs = @()
if (-not (Test-Path $python)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $python = $cmd.Source
    } else {
        $cmd = Get-Command py -ErrorAction SilentlyContinue
        if (-not $cmd) {
            Write-Error "Python 3.10+ not found. Install Python first."
            exit 1
        }
        $python = $cmd.Source
        $pythonArgs = @("-3")
    }
}
if (-not (Test-Path $script)) {
    Write-Error "Script not found: $script"
    exit 1
}

$arguments = $pythonArgs + @("`"$script`"")
$action = New-ScheduledTaskAction -Execute $python -Argument ($arguments -join " ") -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Registered daily task: $TaskName at $Time"
Write-Host "Python: $python"
Write-Host "Script: $script"
Write-Host "Run now with: schtasks /Run /TN $TaskName"
