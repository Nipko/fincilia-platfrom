param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("status", "cleanup")]
    [string]$Command,
    [string]$AccountId = $env:FINCILIA_PILOT_ACCOUNT_ID,
    [string]$Profile = "fincilia-sandbox",
    [string]$Region = "sa-east-1",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$LambdaFunction = "fincilia-credit-lab-web"
$LambdaRole = "fincilia-credit-lab-lambda-role"
$RdsIdentifier = "fincilia-credit-lab-rds"
$PurposeTag = "aws-credit-activity"
$LambdaBasicPolicyArn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

if (-not $AccountId) {
    throw "Defina FINCILIA_PILOT_ACCOUNT_ID o use -AccountId."
}
if ($Apply -and $Command -ne "cleanup") {
    throw "-Apply solo es valido con cleanup."
}
if ($Command -eq "cleanup" -and -not $Apply) {
    throw "La limpieza es destructiva y exige cleanup -Apply."
}

function Invoke-Aws {
    param([Parameter(Mandatory = $true)][string[]]$AwsArguments)

    $capturedOutput = & wsl aws @AwsArguments --profile $Profile --no-cli-pager 2>&1
    if ($LASTEXITCODE -ne 0) {
        $safeCommand = ($AwsArguments -join " ")
        throw "Fallo AWS CLI en: aws $safeCommand"
    }
    return (($capturedOutput | ForEach-Object { $_.ToString() }) -join "`n").Trim()
}

$observedAccount = Invoke-Aws -AwsArguments @(
    "sts", "get-caller-identity", "--query", "Account", "--output", "text"
)
if ($observedAccount -ne $AccountId) {
    throw "Cuenta AWS inesperada. Esperada $AccountId; observada $observedAccount."
}

$lambdaArn = "arn:aws:lambda:${Region}:${AccountId}:function:${LambdaFunction}"
$rdsArn = "arn:aws:rds:${Region}:${AccountId}:db:${RdsIdentifier}"

function Assert-PurposeTag {
    param([Parameter(Mandatory = $true)][ValidateSet("lambda", "rds", "iam")][string]$ResourceKind)

    $observedPurpose = switch ($ResourceKind) {
        "lambda" {
            Invoke-Aws -AwsArguments @(
                "lambda", "list-tags", "--resource", $lambdaArn, "--region", $Region,
                "--query", "Tags.Purpose", "--output", "text"
            )
        }
        "rds" {
            Invoke-Aws -AwsArguments @(
                "rds", "list-tags-for-resource", "--resource-name", $rdsArn, "--region", $Region,
                "--query", "TagList[?Key=='Purpose'].Value | [0]", "--output", "text"
            )
        }
        "iam" {
            Invoke-Aws -AwsArguments @(
                "iam", "list-role-tags", "--role-name", $LambdaRole,
                "--query", "Tags[?Key=='Purpose'].Value | [0]", "--output", "text"
            )
        }
    }
    if ($observedPurpose -ne $PurposeTag) {
        throw "El recurso $ResourceKind no tiene Purpose=$PurposeTag; limpieza detenida."
    }
}

if ($Command -eq "status") {
    $lambdaState = Invoke-Aws -AwsArguments @(
        "lambda", "get-function", "--function-name", $LambdaFunction, "--region", $Region,
        "--query", "Configuration.State", "--output", "text"
    )
    $rdsState = Invoke-Aws -AwsArguments @(
        "rds", "describe-db-instances", "--db-instance-identifier", $RdsIdentifier, "--region", $Region,
        "--query", "DBInstances[0].DBInstanceStatus", "--output", "text"
    )
    $roleState = Invoke-Aws -AwsArguments @(
        "iam", "get-role", "--role-name", $LambdaRole,
        "--query", "Role.RoleName", "--output", "text"
    )

    [ordered]@{
        account_verified = $true
        lambda = $lambdaState
        rds = $rdsState
        iam_role = $roleState
        bedrock_persistent_resources = 0
        data_class = "synthetic-only"
    } | ConvertTo-Json
    exit 0
}

Assert-PurposeTag -ResourceKind "lambda"
Assert-PurposeTag -ResourceKind "rds"
Assert-PurposeTag -ResourceKind "iam"

Invoke-Aws -AwsArguments @(
    "lambda", "delete-function", "--function-name", $LambdaFunction, "--region", $Region
) | Out-Null

$rdsDeletionState = Invoke-Aws -AwsArguments @(
    "rds", "delete-db-instance", "--db-instance-identifier", $RdsIdentifier, "--region", $Region,
    "--skip-final-snapshot", "--delete-automated-backups",
    "--query", "DBInstance.DBInstanceStatus", "--output", "text"
)

Invoke-Aws -AwsArguments @(
    "iam", "detach-role-policy", "--role-name", $LambdaRole,
    "--policy-arn", $LambdaBasicPolicyArn
) | Out-Null
Invoke-Aws -AwsArguments @(
    "iam", "delete-role", "--role-name", $LambdaRole
) | Out-Null

[ordered]@{
    account_verified = $true
    lambda = "deleted"
    rds = $rdsDeletionState
    iam_role = "deleted"
    bedrock_persistent_resources = 0
} | ConvertTo-Json
