# =====================================================================
#  MultiSportPredict - (re)register the Windows scheduled tasks.
#
#  Replaces the drifted "MultiSportPredict Daily Refresh" task, which was
#  registered against ingest_soccer.py only and last exited 0xC000013A.
#
#  Run from anywhere:
#    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\register_tasks.ps1
#
#  Registers two tasks, both running as the current user, limited rights:
#    MultiSportPredict_DailyRefresh   07:00 daily  -> scripts\run_daily_refresh.bat
#    MultiSportPredict_HourlyGrader   hourly       -> scripts\run_hourly_grading.bat
#
#  Each wrapper writes its own log under logs\ and records its exit code in
#  logs\automation_status.log, so Task Scheduler's LastTaskResult is meaningful.
# =====================================================================
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

$OldTask = 'MultiSportPredict Daily Refresh'
$DailyTask = 'MultiSportPredict_DailyRefresh'
$HourlyTask = 'MultiSportPredict_HourlyGrader'

# Shared settings: never overlap a run, catch up after sleep, do not stop on
# battery, and cap a stuck run at two hours instead of letting it hold the slot.
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

function Register-MspTask {
    param($Name, $Script, $Trigger, $Description)
    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    }
    $action = New-ScheduledTaskAction -Execute $Script -WorkingDirectory $Root
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Trigger `
        -Settings $settings -Principal $principal -Description $Description | Out-Null
    Write-Host "registered: $Name -> $Script"
}

# Remove the old drifted task.
if (Get-ScheduledTask -TaskName $OldTask -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $OldTask -Confirm:$false
    Write-Host "removed old task: $OldTask"
}

Register-MspTask -Name $DailyTask `
    -Script (Join-Path $Root 'scripts\run_daily_refresh.bat') `
    -Trigger (New-ScheduledTaskTrigger -Daily -At 7:00AM) `
    -Description 'Daily all-sport ingestion through msp.py daily --all'

Register-MspTask -Name $HourlyTask `
    -Script (Join-Path $Root 'scripts\run_hourly_grading.bat') `
    -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) `
        -RepetitionInterval (New-TimeSpan -Hours 1) `
        -RepetitionDuration (New-TimeSpan -Days 3650)) `
    -Description 'Hourly grading pass: settle saved selections against verified results'

Write-Host ''
Get-ScheduledTask -TaskName 'MultiSportPredict_*' |
    Select-Object TaskName, State |
    Format-Table -AutoSize
