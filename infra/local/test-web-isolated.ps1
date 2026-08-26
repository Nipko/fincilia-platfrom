[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]{1,64}$')]
    [string]$Distribution = 'Ubuntu'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$WslExe = Join-Path $env:SystemRoot 'System32\wsl.exe'
$Lifecycle = 'infra/local/test-web-isolated.sh'
$WebRoot = Join-Path $RepositoryRoot 'apps\web'
$BaseUrl = 'http://127.0.0.1:53100'
$Npm = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue

function Invoke-WslAction {
    param([Parameter(Mandatory = $true)][string]$Action)
    if ($Action -notin @('up', 'down', 'assert-isolated', 'assert-clean')) {
        throw 'Accion WSL fuera del allowlist del runtime E2E.'
    }
    & $WslExe --distribution $Distribution --cd $RepositoryRoot `
        --exec sh $Lifecycle $Action
    if ($LASTEXITCODE -ne 0) {
        throw "El lifecycle E2E fallo en $Action con exit $LASTEXITCODE."
    }
}

function Invoke-WebSuite {
    param([Parameter(Mandatory = $true)][string]$Script)
    if ($Script -notin @('test:e2e', 'test:a11y')) {
        throw 'Suite web fuera del allowlist.'
    }
    & $Npm.Source --prefix $WebRoot run $Script
    if ($LASTEXITCODE -ne 0) {
        throw "La suite $Script fallo con exit $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $WslExe)) {
    throw 'wsl.exe no existe.'
}
if ($null -eq $Npm) {
    throw 'npm.cmd no existe en PATH.'
}

$Keeper = $null
$RunFailure = $null
$CleanupFailure = $null
$PreviousBaseUrl = $env:FINCILIA_E2E_BASE_URL
$HadBaseUrl = Test-Path Env:FINCILIA_E2E_BASE_URL
$StartedAt = [DateTimeOffset]::UtcNow

try {
    $Keeper = Start-Process -FilePath $WslExe `
        -ArgumentList @('--distribution', $Distribution, '--exec', 'sleep', 'infinity') `
        -WindowStyle Hidden -PassThru

    $dockerReady = $false
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        if ($Keeper.HasExited) {
            throw 'El keepalive E2E termino antes de que Docker respondiera.'
        }
        & $WslExe --distribution $Distribution --exec docker version `
            --format '{{.Server.Version}}' *> $null
        if ($LASTEXITCODE -eq 0) {
            $dockerReady = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $dockerReady) {
        throw 'Docker no respondio dentro de 45 segundos.'
    }

    Invoke-WslAction 'up'
    Invoke-WslAction 'assert-isolated'
    $env:FINCILIA_E2E_BASE_URL = $BaseUrl
    Invoke-WebSuite 'test:e2e'
    Invoke-WebSuite 'test:a11y'
}
catch {
    $RunFailure = $_
}
finally {
    try {
        Invoke-WslAction 'down'
        Invoke-WslAction 'assert-clean'
    }
    catch {
        $CleanupFailure = $_
    }

    if ($HadBaseUrl) {
        $env:FINCILIA_E2E_BASE_URL = $PreviousBaseUrl
    }
    else {
        Remove-Item Env:FINCILIA_E2E_BASE_URL -ErrorAction SilentlyContinue
    }

    if ($null -ne $Keeper -and -not $Keeper.HasExited) {
        Stop-Process -Id $Keeper.Id -Force
        Wait-Process -Id $Keeper.Id -Timeout 10 -ErrorAction SilentlyContinue
    }
}

if ($null -ne $RunFailure) {
    if ($null -ne $CleanupFailure) {
        throw "La regresion fallo: $($RunFailure.Exception.Message) Cleanup tambien fallo: $($CleanupFailure.Exception.Message)"
    }
    throw $RunFailure
}
if ($null -ne $CleanupFailure) {
    throw $CleanupFailure
}

@{
    ok = $true
    project = 'fincilia-e2e'
    base_url = $BaseUrl
    suites = @('test:e2e', 'test:a11y')
    cleanup_verified = $true
    data_ceiling = 'synthetic_only'
    elapsed_seconds = [math]::Round(
        ([DateTimeOffset]::UtcNow - $StartedAt).TotalSeconds, 1)
} | ConvertTo-Json -Compress
