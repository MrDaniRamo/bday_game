# One-time setup for Birthday Trivia on Windows.
# Run it by double-clicking setup.bat in the main folder. It is safe to run again.
#
# What it does:
#   1. Checks for Python, Node.js and cloudflared (and offers to install them)
#   2. Makes a private Python environment in backend\.venv
#   3. Installs the Python packages the game server needs
#   4. Installs the packages the web pages need
#   5. Builds the web pages into frontend\dist

$ErrorActionPreference = "Continue"   # we check each step ourselves
Set-Location (Split-Path $PSScriptRoot -Parent)      # the main bday_game folder

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Good($text) { Write-Host "   OK: $text" -ForegroundColor Green }
function Stop-WithProblem($text) {
    Write-Host ""
    Write-Host "PROBLEM: $text" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to close this window"
    exit 1
}
function Test-Command($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

# Finds a real Python 3.10 or newer. Windows sometimes has a fake "python"
# that only opens the Microsoft Store, so we actually ask for the version.
function Find-Python {
    foreach ($candidate in @(@("py", "-3"), @("python"))) {
        $exe = $candidate[0]
        if (-not (Test-Command $exe)) { continue }
        $extra = @($candidate | Select-Object -Skip 1)
        try { $version = & $exe @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null } catch { continue }
        if ($version -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 10) { return ,$candidate }
    }
    return $null
}

Write-Host "Birthday Trivia: one-time setup" -ForegroundColor Yellow
Write-Host "This can take a few minutes. Keep this window open until it says DONE."

# ---------------------------------------------------------------- step 1 ---
Step "Step 1 of 5: checking the programs the game needs"
$python = Find-Python
$needed = @()
if (-not $python)                  { $needed += @{ Name = "Python 3";    Id = "Python.Python.3.12" } }
if (-not (Test-Command "npm"))     { $needed += @{ Name = "Node.js";     Id = "OpenJS.NodeJS.LTS" } }
if (-not (Test-Command "cloudflared")) { $needed += @{ Name = "cloudflared"; Id = "Cloudflare.cloudflared" } }

if ($needed.Count -gt 0) {
    Write-Host ""
    Write-Host "These programs are missing: $(($needed | ForEach-Object { $_.Name }) -join ', ')" -ForegroundColor Yellow
    if (-not (Test-Command "winget")) {
        Stop-WithProblem "Please install them by hand (see guide\PARTY-DAY.md, step A2), then double-click setup.bat again."
    }
    $answer = Read-Host "Install them now? Type Y and press Enter (Windows may ask for permission)"
    if ($answer -notmatch '^[Yy]') { Stop-WithProblem "Setup needs these programs. Install them, then run setup.bat again." }
    foreach ($program in $needed) {
        Write-Host "Installing $($program.Name)..."
        winget install --id $program.Id -e --accept-source-agreements --accept-package-agreements
    }
    Write-Host ""
    Write-Host "Installed. Windows only notices new programs in a NEW window, so:" -ForegroundColor Green
    Write-Host "close this window and double-click setup.bat once more." -ForegroundColor Green
    Read-Host "Press Enter to close this window"
    exit 0
}
Good "Python, Node.js and cloudflared are installed"

# ---------------------------------------------------------------- step 2 ---
Step "Step 2 of 5: making the Python environment"
$venvPython = "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    $exe = $python[0]; $extra = @($python | Select-Object -Skip 1)
    & $exe @extra -m venv backend\.venv
    if ($LASTEXITCODE -ne 0) { Stop-WithProblem "Could not make the Python environment." }
}
Good "backend\.venv is ready"

# ---------------------------------------------------------------- step 3 ---
Step "Step 3 of 5: installing the game server's packages"
& $venvPython -m pip install --disable-pip-version-check -q -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { Stop-WithProblem "Installing the Python packages failed. Check the internet connection and try again." }
Good "Python packages installed"

# ---------------------------------------------------------------- step 4 ---
Step "Step 4 of 5: installing the web pages' packages"
Push-Location frontend
npm install --no-audit --no-fund
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Stop-WithProblem "npm install failed. Check the internet connection and try again." }
Good "Web packages installed"

# ---------------------------------------------------------------- step 5 ---
Step "Step 5 of 5: building the web pages"
Push-Location frontend
npm run build
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Stop-WithProblem "Building the pages failed." }
Good "Pages built into frontend\dist"

Write-Host ""
Write-Host "DONE. Setup is finished." -ForegroundColor Green
Write-Host "To play, double-click start-party.bat."
Write-Host "(Run setup.bat again only after you download a new version of the game.)"
Read-Host "Press Enter to close this window"
