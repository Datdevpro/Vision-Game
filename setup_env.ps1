# Install only into the virtual environment beside this script.
$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$venvDir = Join-Path $projectDir 'venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$cacheDir = Join-Path $venvDir '.cache\pip'
$tempDir = Join-Path $venvDir '.tmp'

# Save process settings so running this script does not change the caller's setup.
$environmentNames = @(
    'PIP_CONFIG_FILE', 'PIP_TARGET', 'PIP_PREFIX', 'PIP_ROOT', 'PIP_USER',
    'PIP_PYTHON', 'PIP_LOG', 'PIP_CACHE_DIR', 'PIP_SRC', 'PIP_ISOLATED',
    'PIP_REQUIRE_VIRTUALENV', 'PIP_REQUIRE_VENV',
    'PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE', 'PYTHONNOUSERSITE',
    'VIRTUAL_ENV', 'TEMP', 'TMP'
)
$savedEnvironment = @{}
foreach ($name in $environmentNames) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$setupExitCode = 0
try {
    Write-Host 'SUBWAY SURFERS AI BODY CONTROLLER - LOCAL VENV SETUP' -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $cacheDir, $tempDir -Force | Out-Null

    # Ignore pip.ini and inherited options that could redirect installation.
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    $env:PIP_CONFIG_FILE = 'nul'
    $env:PIP_USER = 'false'
    $env:PIP_REQUIRE_VIRTUALENV = 'true'
    $env:PIP_CACHE_DIR = $cacheDir
    $env:PIP_SRC = Join-Path $venvDir 'src'
    $env:PYTHONNOUSERSITE = '1'
    $env:VIRTUAL_ENV = $venvDir
    $env:TEMP = $tempDir
    $env:TMP = $tempDir

    Write-Host '[1/4] Preparing the project virtual environment...' -ForegroundColor Yellow
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        $pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if (-not $pythonCommand) {
            throw 'Python was not found in PATH. Install Python 3.11 or 3.12 first.'
        }
        & $pythonCommand.Source -I -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            throw 'Failed to create the project virtual environment.'
        }
    }

    # Refuse a misplaced interpreter, shared system packages, or external paths.
    $validateVenv = @'
from pathlib import Path
import site
import sys
import sysconfig

expected = Path(sys.argv[1]).resolve()
if sys.prefix == sys.base_prefix or Path(sys.prefix).resolve() != expected:
    raise SystemExit('ERROR: Python is not running in the project venv.')
config = (expected / 'pyvenv.cfg').read_text(encoding='utf-8').lower()
if 'include-system-site-packages = false' not in config or site.ENABLE_USER_SITE:
    raise SystemExit('ERROR: The venv must disable system and user site-packages.')
for key in ('purelib', 'platlib', 'scripts', 'data'):
    if not Path(sysconfig.get_path(key)).resolve().is_relative_to(expected):
        raise SystemExit('ERROR: An installation path is outside the project venv.')
print('Python:', sys.executable)
print('Packages:', sysconfig.get_path('purelib'))
'@
    & $venvPython -I -c $validateVenv $venvDir
    if ($LASTEXITCODE -ne 0) {
        throw 'Virtual environment validation failed. No packages were installed.'
    }
    Write-Host "Cache: $cacheDir"
    Write-Host "Temporary files: $tempDir"

    Write-Host '[2/4] Upgrading pip inside the venv...' -ForegroundColor Yellow
    & $venvPython -I -m pip --require-virtualenv install --no-user --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to upgrade pip inside the venv.'
    }

    Write-Host '[3/4] Installing dependencies inside the venv...' -ForegroundColor Yellow
    & $venvPython -I -m pip --require-virtualenv install --no-user -r (Join-Path $projectDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) {
        throw 'Dependency installation failed. Setup stopped.'
    }

    Write-Host '[4/4] Downloading pose models into the project...' -ForegroundColor Yellow
    & $venvPython -I (Join-Path $projectDir 'download_models.py')
    if ($LASTEXITCODE -ne 0) {
        throw 'Model download failed.'
    }
    Write-Host 'SETUP COMPLETE! Run run.bat or .\run.ps1 to play.' -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    $setupExitCode = 1
}
finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
}
exit $setupExitCode
