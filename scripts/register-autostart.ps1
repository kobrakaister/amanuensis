$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$uv = (Get-Command uv -ErrorAction Stop).Source
$action = New-ScheduledTaskAction -Execute $uv -Argument "run --project `"$repo`" lecture-study watch" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'LectureStudyWatch' -Action $action -Trigger $trigger -Settings $settings -Description 'Osserva la cartella delle lezioni e produce il materiale di studio' -Force | Out-Null
Write-Output "Registrata l'attività LectureStudyWatch per $env:USERNAME"
