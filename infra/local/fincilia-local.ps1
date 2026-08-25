[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('doctor', 'up', 'status', 'down')]
    [string]$Action = 'status',

    [ValidatePattern('^[A-Za-z0-9._-]{1,64}$')]
    [string]$Distribution = 'Ubuntu'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Project = 'fincilia-local'
$ComposeFile = 'infra/local/compose.yaml'
$RepositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$WslExe = Join-Path $env:SystemRoot 'System32\wsl.exe'
$StateDirectory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Fincilia'
$StatePath = Join-Path $StateDirectory 'wsl-local-runtime.json'
$LockPath = Join-Path $StateDirectory 'wsl-local-runtime.lock'

function Write-Result {
    param([hashtable]$Value)
    $Value | ConvertTo-Json -Depth 8 -Compress
}

function Remove-StateFile {
    if (Test-Path -LiteralPath $StatePath) {
        Remove-Item -LiteralPath $StatePath -Force
    }
}

function Get-KeeperState {
    if (-not (Test-Path -LiteralPath $StatePath)) {
        return $null
    }
    try {
        $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
        if ($state.project -ne $Project -or $state.distribution -ne $Distribution -or
            $state.pid -notmatch '^\d+$') {
            Remove-StateFile
            return $null
        }
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($state.pid)" `
            -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            Remove-StateFile
            return $null
        }
        $name = [IO.Path]::GetFileName([string]$process.ExecutablePath)
        $commandLine = [string]$process.CommandLine
        $distributionPattern = [regex]::Escape($Distribution)
        if ($name -ine 'wsl.exe' -or $commandLine -notmatch 'sleep\s+infinity' -or
            $commandLine -notmatch "--distribution\s+$distributionPattern") {
            Remove-StateFile
            return $null
        }
        return $state
    }
    catch {
        Remove-StateFile
        return $null
    }
}

function Invoke-WslCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Command,
        [switch]$Quiet
    )
    $arguments = @('--distribution', $Distribution, '--cd', $RepositoryRoot,
        '--exec') + $Command
    $output = & $WslExe @arguments 2>&1
    $exitCode = $LASTEXITCODE
    if (-not $Quiet) {
        $output | ForEach-Object { Write-Host $_ }
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join [Environment]::NewLine)
    }
}

function Write-KeeperState {
    param([System.Diagnostics.Process]$Process)
    New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
    $temporary = "$StatePath.$PID.tmp"
    @{
        pid = $Process.Id
        distribution = $Distribution
        project = $Project
        started_at = [DateTimeOffset]::UtcNow.ToString('O')
    } | ConvertTo-Json -Compress | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $StatePath -Force
}

function Start-Keeper {
    $current = Get-KeeperState
    if ($null -ne $current) {
        return $current
    }

    New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
    $process = Start-Process -FilePath $WslExe `
        -ArgumentList @('--distribution', $Distribution, '--exec', 'sleep', 'infinity') `
        -WindowStyle Hidden -PassThru
    Write-KeeperState -Process $process

    try {
        for ($attempt = 0; $attempt -lt 45; $attempt++) {
            if ($process.HasExited) {
                throw 'El keepalive de WSL termino antes de que Docker respondiera.'
            }
            $probe = Invoke-WslCommand -Quiet -Command @(
                'docker', 'version', '--format', '{{.Server.Version}}')
            if ($probe.ExitCode -eq 0) {
                return Get-KeeperState
            }
            Start-Sleep -Seconds 1
        }
        throw 'Docker no respondio dentro de 45 segundos.'
    }
    catch {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
        Remove-StateFile
        throw
    }
}

function Stop-Keeper {
    $state = Get-KeeperState
    if ($null -ne $state) {
        Stop-Process -Id ([int]$state.pid) -Force
        try {
            Wait-Process -Id ([int]$state.pid) -Timeout 10 -ErrorAction SilentlyContinue
        }
        catch {
            # El proceso ya termino; el estado se elimina igualmente.
        }
    }
    Remove-StateFile
}

function Enter-LifecycleLock {
    New-Item -ItemType Directory -Path $StateDirectory -Force | Out-Null
    try {
        return [IO.File]::Open($LockPath, [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write, [IO.FileShare]::None)
    }
    catch [IO.IOException] {
        throw "Otro lifecycle local conserva el lock $LockPath"
    }
}

function Exit-LifecycleLock {
    param([IO.FileStream]$Lock)
    $Lock.Dispose()
    if (Test-Path -LiteralPath $LockPath) {
        Remove-Item -LiteralPath $LockPath -Force
    }
}

if (-not (Test-Path -LiteralPath $WslExe)) {
    Write-Result @{ action = $Action; ok = $false; reason = 'wsl.exe no existe' }
    exit 3
}

if ($Action -eq 'doctor') {
    $keeper = Get-KeeperState
    $probe = Invoke-WslCommand -Quiet -Command @('systemctl', 'is-enabled', 'docker')
    Write-Result @{
        action = 'doctor'
        ok = ($probe.ExitCode -eq 0)
        distribution = $Distribution
        docker_service_enabled = ($probe.ExitCode -eq 0)
        keepalive = if ($null -eq $keeper) { 'stopped' } else { 'running' }
        modifies_configuration = $false
    }
    if ($probe.ExitCode -eq 0) { exit 0 } else { exit 3 }
}

if ($Action -eq 'status') {
    $keeper = Get-KeeperState
    if ($null -eq $keeper) {
        Write-Result @{
            action = 'status'; ok = $false; keepalive = 'stopped'; services = @()
        }
        exit 3
    }
    $status = Invoke-WslCommand -Quiet -Command @(
        'docker', 'compose', '-f', $ComposeFile, '-p', $Project,
        'ps', '--format', 'json')
    $services = @()
    foreach ($line in ($status.Output -split "`r?`n")) {
        if (-not $line.Trim().StartsWith('{')) {
            continue
        }
        try {
            $row = $line | ConvertFrom-Json
            $services += @{
                service = [string]$row.Service
                state = [string]$row.State
                health = [string]$row.Health
                ports = [string]$row.Ports
            }
        }
        catch {
            # Una linea no interpretable no se expone como metadato libre.
        }
    }
    Write-Result @{
        action = 'status'
        ok = ($status.ExitCode -eq 0)
        keepalive = 'running'
        keeper_pid = [int]$keeper.pid
        services = @($services | Sort-Object service)
    }
    if ($status.ExitCode -eq 0) { exit 0 } else { exit 1 }
}

$lock = Enter-LifecycleLock
try {
    $keeper = Start-Keeper
    if ($Action -eq 'up') {
        $result = Invoke-WslCommand -Command @('sh', 'infra/local/up.sh')
        Write-Result @{
            action = 'up'
            ok = ($result.ExitCode -eq 0)
            keepalive = 'running'
            keeper_pid = [int]$keeper.pid
            web = 'http://127.0.0.1:53000'
            api = 'http://127.0.0.1:58080/docs'
        }
        if ($result.ExitCode -eq 0) { exit 0 } else { exit 1 }
    }

    $result = Invoke-WslCommand -Command @(
        'docker', 'compose', '-f', $ComposeFile, '-p', $Project, 'down')
    if ($result.ExitCode -eq 0) {
        Stop-Keeper
    }
    Write-Result @{
        action = 'down'
        ok = ($result.ExitCode -eq 0)
        keepalive = if ($result.ExitCode -eq 0) { 'stopped' } else { 'running' }
        data_volumes_preserved = $true
    }
    if ($result.ExitCode -eq 0) { exit 0 } else { exit 1 }
}
finally {
    Exit-LifecycleLock -Lock $lock
}
