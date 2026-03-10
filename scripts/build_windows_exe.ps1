param(
    [string]$PythonVersion = "",
    [string]$VenvDir = ".venv-build",
    [switch]$RecreateVenv,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Invoke-External {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    $process = Start-Process -FilePath $Command -ArgumentList $Arguments -Wait -NoNewWindow -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Command failed: $Command $($Arguments -join ' ')"
    }
}

function Get-PythonLauncher {
    param([string]$RequestedVersion)

    $pyCandidates = @()
    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand) {
        $pyCandidates += $pyCommand.Source
    }
    $pyCandidates += @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Launcher\py.exe"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\py.exe"),
        "C:\Windows\py.exe"
    )

    foreach ($pyPath in $pyCandidates | Select-Object -Unique) {
        if (-not $pyPath) {
            continue
        }
        if (-not (Test-Path $pyPath)) {
            continue
        }

        if ($RequestedVersion) {
            return @{
                Command = $pyPath
                Prefix = @("-$RequestedVersion")
            }
        }

        foreach ($candidate in @("3.14", "3.13", "3.12", "3.11")) {
            & $pyPath "-$candidate" -c "import sys" *> $null
            if ($LASTEXITCODE -eq 0) {
                return @{
                    Command = $pyPath
                    Prefix = @("-$candidate")
                }
            }
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        $launcher = @{
            Command = "python"
            Prefix = @()
        }
        $versionText = & $launcher.Command @($launcher.Prefix + @("-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"))
        if ($LASTEXITCODE -ne 0) {
            throw "python command exists but version check failed."
        }
        if ([version]$versionText -lt [version]"3.11") {
            throw "python command points to Python $versionText. Python 3.11+ is required."
        }
        return $launcher
    }

    throw "Python 3.11+ launcher was not found. Install Python and retry."
}

$launcher = Get-PythonLauncher -RequestedVersion $PythonVersion
$venvPath = Join-Path $RepoRoot $VenvDir
$venvPython = Join-Path $venvPath "Scripts/python.exe"

if ($RecreateVenv -and (Test-Path $venvPath)) {
    Remove-Item $venvPath -Recurse -Force
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating build venv: $venvPath"
    Invoke-External -Command $launcher.Command -Arguments ($launcher.Prefix + @("-m", "venv", $venvPath))
}

Set-Location $RepoRoot

Write-Host "Using Python: $venvPython"
Invoke-External -Command $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")
Invoke-External -Command $venvPython -Arguments @("-m", "pip", "install", "-e", ".[build]")

if (-not $SkipTests) {
    Invoke-External -Command $venvPython -Arguments @("-m", "pytest", "-q")
}

$srcPath = Join-Path $RepoRoot "src"
$cliEntry = Join-Path $RepoRoot "src/pyinstaller_entry_cli.py"
$guiEntry = Join-Path $RepoRoot "src/pyinstaller_entry_gui.py"
$cliWorkPath = Join-Path $RepoRoot "build/pyi-cli"
$guiWorkPath = Join-Path $RepoRoot "build/pyi-gui"
$specPath = Join-Path $RepoRoot "build/spec"
$distPath = Join-Path $RepoRoot "dist"

Invoke-External -Command $venvPython -Arguments @(
    "-m", "PyInstaller",
    "--clean",
    "--noconfirm",
    "--onefile",
    "--console",
    "--workpath", $cliWorkPath,
    "--specpath", $specPath,
    "--distpath", $distPath,
    "--name", "zip-edu-cli",
    "--paths", $srcPath,
    $cliEntry
)

Invoke-External -Command $venvPython -Arguments @(
    "-m", "PyInstaller",
    "--clean",
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--workpath", $guiWorkPath,
    "--specpath", $specPath,
    "--distpath", $distPath,
    "--name", "zip-edu-gui",
    "--paths", $srcPath,
    $guiEntry
)

$cliExe = Join-Path $distPath "zip-edu-cli.exe"
Invoke-External -Command $cliExe -Arguments @("explain-deflate", "--text", "abracadabra")

Write-Host "Build complete:"
Write-Host "  $RepoRoot\dist\zip-edu-cli.exe"
Write-Host "  $RepoRoot\dist\zip-edu-gui.exe"
