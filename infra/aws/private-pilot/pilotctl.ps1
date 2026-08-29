param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("status", "plan-cold", "plan-warm", "cold", "warm")]
    [string]$Command,
    [string]$AccountId = $env:FINCILIA_PILOT_ACCOUNT_ID,
    [string]$Profile = "fincilia-sandbox",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
if (-not $AccountId) {
    throw "Defina FINCILIA_PILOT_ACCOUNT_ID o use -AccountId."
}
if ($Apply -and $Command -notin @("cold", "warm")) {
    throw "-Apply solo es valido con cold o warm."
}

$moduleCommand = switch ($Command) {
    "plan-cold" { @("plan", "cold") }
    "plan-warm" { @("plan", "warm") }
    default { @($Command) }
}
$arguments = @(
    "python3", "-m", "tools.aws_pilot_control.cli",
    "--account-id", $AccountId,
    "--profile", $Profile
) + $moduleCommand
if ($Apply) {
    $arguments += "--apply"
}

& wsl @arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
