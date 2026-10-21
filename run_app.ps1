Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$appName = "Streamlit Dashboard App (uv)"
$logDir = Join-Path $PSScriptRoot "logs"
$lastStep = "Initialization"
$lastExitCode = 0

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir ("run_app_{0}.log" -f $timestamp)

@(
    "========================================"
    "$appName launcher log"
    "Started: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")"
    "Working dir: $PWD"
    "========================================"
    ""
) | Set-Content -Path $logFile -Encoding ASCII

function Write-Info {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host $Message
    Add-Content -Path $script:logFile -Value $Message -Encoding ASCII
}

function Resolve-UvCommand {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) { return $uv.Source }

    $fallbacks = @(
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\uv.exe"),
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe")
    )

    foreach ($path in $fallbacks) {
        if (Test-Path $path) { return $path }
    }

    return $null
}

function Format-CmdArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    if ($Value -eq "") { return '""' }
    if ($Value -match '[\s"&|<>()^]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

function Invoke-LoggedNative {
    param(
        [Parameter(Mandatory = $true)][string]$Step,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [switch]$AutoOpenLocalUrl
    )

    $script:lastStep = $Step
    Write-Info $Step

    $quotedFile = '"' + ($FilePath -replace '"', '\"') + '"'
    $quotedArgs = ($Arguments | ForEach-Object { Format-CmdArgument -Value $_ }) -join " "
    $commandLine = if ([string]::IsNullOrWhiteSpace($quotedArgs)) {
        "$quotedFile 2>&1"
    }
    else {
        "$quotedFile $quotedArgs 2>&1"
    }

    $browserOpened = $false
    cmd.exe /d /c $commandLine | ForEach-Object {
        $line = [string]$_
        Write-Host $line
        Add-Content -Path $script:logFile -Value $line -Encoding ASCII

        if ($AutoOpenLocalUrl -and -not $browserOpened -and $line -match "Local URL:\s*(https?://\S+)") {
            $url = $Matches[1]
            Write-Host "Opening browser: $url"
            Add-Content -Path $script:logFile -Value ("Opening browser: {0}" -f $url) -Encoding ASCII
            Start-Process $url -ErrorAction SilentlyContinue
            $browserOpened = $true
        }
    }

    if ($AutoOpenLocalUrl -and -not $browserOpened) {
        $fallbackUrl = "http://localhost:8501"
        Write-Host "Opening browser: $fallbackUrl"
        Add-Content -Path $script:logFile -Value ("Opening browser: {0}" -f $fallbackUrl) -Encoding ASCII
        Start-Process $fallbackUrl -ErrorAction SilentlyContinue
    }

    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    $script:lastExitCode = $exitCode

    if ($exitCode -ne 0) {
        throw "Command failed with exit code $exitCode"
    }
}

function Clear-OldLogs {
    param(
        [Parameter(Mandatory = $true)][string]$Directory,
        [int]$Keep = 5
    )

    Get-ChildItem -Path $Directory -Filter "*.log" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $Keep |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

try {
    Write-Host ""
    Write-Host "========================================"
    Write-Host " $appName"
    Write-Host "========================================"
    Write-Host ""
    Write-Host "Log file: `"$logFile`""
    Write-Host ""

    Clear-OldLogs -Directory $logDir -Keep 5

    $lastStep = "Detecting uv"
    $uvCommand = Resolve-UvCommand
    if (-not $uvCommand) {
        Write-Info "[1/4] uv not found on PATH. Attempting installation..."

        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Invoke-LoggedNative -Step "- Trying WinGet installer..." -FilePath "winget" -Arguments @("install", "--id=astral-sh.uv", "-e", "--silent")
            $uvCommand = Resolve-UvCommand
        }

        if (-not $uvCommand) {
            $lastStep = "Installing uv via PowerShell installer"
            Write-Info "- Trying PowerShell installer..."
            Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression 2>&1 | ForEach-Object {
                $line = [string]$_
                Write-Host $line
                Add-Content -Path $logFile -Value $line -Encoding ASCII
            }
            $uvCommand = Resolve-UvCommand
        }

        if (-not $uvCommand) {
            throw "uv is still unavailable. Open a new terminal and run again."
        }
    }

    Write-Info "[OK] uv detected: $uvCommand"

    Invoke-LoggedNative -Step "[2/4] Ensuring Python 3.11 is installed..." -FilePath $uvCommand -Arguments @("python", "install", "3.11")
    Invoke-LoggedNative -Step "[3/4] Syncing project environment..." -FilePath $uvCommand -Arguments @("sync")

    Write-Info "[4/4] Launching Streamlit..."
    Invoke-LoggedNative -Step "Running app server..." -FilePath $uvCommand -Arguments @("run", "--", "streamlit", "run", "app/app.py") -AutoOpenLocalUrl

    Write-Info ""
    Write-Info "App exited normally."
    Write-Info "Log: `"$logFile`""
    exit 0
}
catch {
    $rc = if ($lastExitCode -ne 0) { $lastExitCode } else { 1 }

    Write-Host ""
    Write-Host "========================================"
    Write-Host "FAILED during: $lastStep"
    Write-Host "Exit code: $rc"
    Write-Host "Log file: `"$logFile`""
    Write-Host "Reason: $($_.Exception.Message)"
    Write-Host "========================================"
    Write-Host ""

    Add-Content -Path $logFile -Encoding ASCII -Value ""
    Add-Content -Path $logFile -Encoding ASCII -Value ("FAILED during: {0}" -f $lastStep)
    Add-Content -Path $logFile -Encoding ASCII -Value ("Exit code: {0}" -f $rc)
    Add-Content -Path $logFile -Encoding ASCII -Value ("Reason: {0}" -f $_.Exception.Message)

    exit $rc
}
