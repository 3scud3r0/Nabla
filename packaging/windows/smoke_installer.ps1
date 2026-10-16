param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference = 'Stop'
$installPath = Join-Path $env:RUNNER_TEMP 'nabla-release-install'
$dataPath = Join-Path $env:RUNNER_TEMP 'nabla-release-personal-data'
New-Item -ItemType Directory -Force $dataPath | Out-Null
$sentinel = Join-Path $dataPath 'personal-file.txt'
[System.IO.File]::WriteAllText($sentinel, 'preserve personal data')
$before = (Get-FileHash $sentinel -Algorithm SHA256).Hash
function Install-Candidate {
    $process = Start-Process -FilePath $Installer -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$installPath`"") -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Installer failed: $($process.ExitCode)" }
}
function Check-InstalledWorkflow {
    $exe = Join-Path $installPath 'NablaMath.exe'
    $process = Start-Process -FilePath $exe -ArgumentList @('--no-browser', '--port', '38292', '--data-dir', "`"$dataPath`"") -PassThru
    try {
        $page = $null
        for ($i = 0; $i -lt 30; $i++) {
            try { $page = Invoke-WebRequest 'http://127.0.0.1:38292/' -UseBasicParsing -TimeoutSec 2; break } catch { }
            $process.Refresh()
            if ($process.HasExited) { throw 'Installed desktop exited before readiness' }
            Start-Sleep -Seconds 1
        }
        if (-not $page -or $page.Content -notmatch "const auth='([^']+)'") { throw 'Missing desktop session' }
        $headers = @{ 'X-Nabla-Token' = $Matches[1]; 'Origin' = 'http://127.0.0.1:38292' }
        $body = @{expression='(x+x)/x'; values=@{x='3'}} | ConvertTo-Json
        $result = Invoke-RestMethod 'http://127.0.0.1:38292/api/run' -Method Post -Headers $headers -ContentType 'application/json' -Body $body
        if ($result.result.value -ne '2') { throw 'Installed calculation failed' }
        $export = Invoke-RestMethod 'http://127.0.0.1:38292/api/export' -Method Post -Headers $headers -ContentType 'application/json' -Body '{}'
        if ($export.records -lt 1) { throw 'Installed export failed' }
    } finally {
        $process.Refresh()
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force; $process.WaitForExit() }
    }
}
Install-Candidate
Check-InstalledWorkflow
# Repair/reinstall the same exact artifact; historical-version upgrade remains a separate gate.
Install-Candidate
Check-InstalledWorkflow
$uninstall = Start-Process -FilePath (Join-Path $installPath 'unins000.exe') -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru
if ($uninstall.ExitCode -ne 0) { throw 'Uninstall failed' }
if (Test-Path (Join-Path $installPath 'NablaMath.exe')) { throw 'Executable remains installed' }
if ((Get-FileHash $sentinel -Algorithm SHA256).Hash -ne $before) { throw 'Personal data changed' }
if (-not (Test-Path (Join-Path $dataPath 'results.sqlite3'))) { throw 'Personal database was removed' }
Write-Host 'Installed calculation/export, same-version repair and uninstall passed; personal data preserved.'
