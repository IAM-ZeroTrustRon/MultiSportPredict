<#
.SYNOPSIS
    A PowerShell wrapper to reliably execute the MultiSportPredict Python application.
.DESCRIPTION
    This script ensures that a specified Python script (or predict_match.py by default)
    is executed with the Python interpreter, regardless of Windows file associations.

    If the first argument is a .py file, it will run that script. Otherwise, it
    runs predict_match.py and forwards all arguments to it.
.EXAMPLE
    ./run.ps1 soccer "Liverpool" "Arsenal"
.EXAMPLE
    ./run.ps1 mlb "NYY" "BOS" --markets nrfi
#>
# Get the directory where this script is located.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Determine which Python script to run.
# If the first argument is a .py file, use it. Otherwise, default to predict_match.py.
$PythonScriptName = "predict_match.py"
$ForwardedArgs = $args

if ($args.Count -gt 0 -and $args[0].EndsWith(".py")) {
    $PythonScriptName = $args[0]
    # Remove the script name from the arguments passed to the Python script.
    $ForwardedArgs = $args | Select-Object -Skip 1
}

# Define the path to the Python script.
$PythonScriptPath = Join-Path -Path $ScriptDir -ChildPath $PythonScriptName

if (-not (Test-Path $PythonScriptPath)) {
    Write-Error "Python script not found: $PythonScriptPath"
    exit 1
}

# Find the Python executable (checks for 'python' then 'python3').
$PythonExec = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonExec) {
    $PythonExec = Get-Command python3 -ErrorAction SilentlyContinue
}

if (-not $PythonExec) {
    Write-Error "Python interpreter ('python' or 'python3') not found in your PATH."
    Write-Host "Please ensure Python is installed and its location is added to your system's PATH environment variable."
    exit 1
}

# Execute the Python script with all the forwarded arguments.
Write-Host "▶️  Executing: $($PythonExec.Source) $PythonScriptPath $ForwardedArgs" -ForegroundColor Green
& $PythonExec.Source $PythonScriptPath $ForwardedArgs