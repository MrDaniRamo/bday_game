# Starts Birthday Trivia for the party, on Windows.
# Run it by double-clicking start-party.bat in the main folder.
#
# What it does:
#   1. Asks for tonight's host password (and whether to start a new game)
#   2. Starts the game server on this laptop (port 8000)
#   3. Starts a free Cloudflare "quick tunnel", which gives the game a public
#      https://....trycloudflare.com address that works on any phone network
#   4. Opens a page with every link and QR code (links.html), and the TV page
#   5. Waits. Press Enter in this window to stop everything at the end.

$ErrorActionPreference = "Continue"
Set-Location (Split-Path $PSScriptRoot -Parent)      # the main bday_game folder
$root = (Get-Location).Path

function Say($text, $color = "White") { Write-Host $text -ForegroundColor $color }
function Stop-WithProblem($text) {
    Say ""; Say "PROBLEM: $text" Red; Say ""
    Read-Host "Press Enter to close this window"
    exit 1
}
function Test-Command($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

# Stops anything left over from an earlier run (for example if this window was
# closed with the X instead of pressing Enter): an old game server or tunnel.
function Stop-Leftovers {
    $old = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $old) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

# The laptop's address on the local Wi-Fi, for the backup links.
function Get-WifiAddress {
    # the network adapter that has a router (default gateway), so not a VPN or virtual one
    $config = Get-NetIPConfiguration -ErrorAction SilentlyContinue |
        Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } |
        Select-Object -First 1
    if ($config) { return $config.IPv4Address.IPAddress | Select-Object -First 1 }
    return $null
}

Say "Birthday Trivia: starting the party" Yellow

# ------------------------------------------------------------ checks ---
$venvPython = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython) -or -not (Test-Path "frontend\dist\index.html")) {
    Stop-WithProblem "The game is not set up yet. Double-click setup.bat first."
}
$haveTunnel = Test-Command "cloudflared"
if (-not $haveTunnel) {
    Say "cloudflared is not installed, so there will be no public link." Yellow
    Say "Phones must then join the laptop's Wi-Fi. (setup.bat can install cloudflared.)" Yellow
}

# ------------------------------------------------------------ questions ---
Say ""
do {
    $password = Read-Host "Choose tonight's HOST PASSWORD (you type it on the host page)"
} while ([string]::IsNullOrWhiteSpace($password))
$env:HOST_PASSWORD = $password.Trim()

if (Test-Path "backend\state.json") {
    Say ""
    Say "A saved game was found (teams, scores, bingo ticks)."
    $fresh = Read-Host "Type NEW and press Enter to start a brand-new game, or just press Enter to continue it"
    if ($fresh -match '^\s*new\s*$') {
        Remove-Item "backend\state.json"
        Say "Starting a brand-new game." Green
    } else {
        Say "Continuing the saved game." Green
    }
}

# ------------------------------------------------------------ server ---
Say ""
Say "Starting the game server..."
Stop-Leftovers
New-Item -ItemType Directory -Force logs | Out-Null
$server = Start-Process -FilePath $venvPython `
    -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory (Join-Path $root "backend") -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput "logs\server-out.log" -RedirectStandardError "logs\server.log"

$up = $false
for ($i = 0; $i -lt 30 -and -not $up; $i++) {
    Start-Sleep -Seconds 1
    try { $up = (Invoke-WebRequest "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { }
    if ($server.HasExited) { break }
}
if (-not $up) {
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    Stop-WithProblem "The game server did not start. The details are in logs\server.log."
}
Say "Game server is running." Green
Say "(If Windows asks whether to allow Python on networks, click Allow. It is only needed for the Wi-Fi backup.)"

# ------------------------------------------------------------ tunnel ---
$publicUrl = $null
$tunnel = $null
if ($haveTunnel) {
    Say ""
    Say "Opening the public link (this takes a few seconds)..."
    Remove-Item "logs\tunnel.log" -ErrorAction SilentlyContinue
    $tunnel = Start-Process -FilePath "cloudflared" `
        -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://localhost:8000" `
        -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "logs\tunnel-out.log" -RedirectStandardError "logs\tunnel.log"
    for ($i = 0; $i -lt 60 -and -not $publicUrl; $i++) {
        Start-Sleep -Seconds 1
        $log = Get-Content "logs\tunnel.log" -Raw -ErrorAction SilentlyContinue
        if ($log -match 'https://[a-z0-9-]+\.trycloudflare\.com') { $publicUrl = $Matches[0] }
        if ($tunnel.HasExited) { break }
    }
    if ($publicUrl) {
        # The link exists right away, but can take a few more seconds to work everywhere.
        Start-Sleep -Seconds 5
        Say "Public link is ready." Green
    } else {
        Say "Could not open the public link (details in logs\tunnel.log)." Yellow
        Say "The game still works for phones on the laptop's Wi-Fi." Yellow
    }
}

$wifi = Get-WifiAddress
$wifiUrl = if ($wifi) { "http://${wifi}:8000" } else { $null }
$base = if ($publicUrl) { $publicUrl } elseif ($wifiUrl) { $wifiUrl } else { "http://localhost:8000" }

# ------------------------------------------------------------ links page ---
# links.html: every link with a QR code, for the host to scan with their phone.
# It stays on this laptop (it is not part of the game and is not uploaded).
function Qr($url) { "$base/qr.svg?data=" + [uri]::EscapeDataString($url) }
$rows = @(
    @{ Title = "TV / main screen";   Url = "$base/";      Note = "Open this on the TV. It shows a QR code captains can scan." },
    @{ Title = "Host (you)";          Url = "$base/host";  Note = "Scan with your phone. Password: the one you just typed." },
    @{ Title = "Team captains";       Url = "$base/team";  Note = "Also shown as a QR code on the TV while teams join." },
    @{ Title = "Secret bingo";        Url = "$base/bingo"; Note = "SECRET: send it privately to the 5 bingo players. Never show it on the TV." }
)
$cards = ($rows | ForEach-Object {
    "<section><h2>$($_.Title)</h2><img src=""$(Qr $_.Url)"" alt=""""><p><a href=""$($_.Url)"">$($_.Url)</a></p><p class=note>$($_.Note)</p></section>"
}) -join "`n"
$backup = if ($publicUrl -and $wifiUrl) {
    "<p class=backup>Backup if the public link stops working: phones join the laptop's Wi-Fi and open <b>$wifiUrl/team</b> (or /host, /bingo).</p>"
} else { "" }
$html = @"
<!doctype html><html lang=en><head><meta charset=utf-8><title>Party links</title>
<style>
body{font-family:system-ui,sans-serif;margin:2rem;background:#fff8ec;color:#4a1426}
h1{margin:0 0 .3rem}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:1.2rem}
section{background:#fff;border:3px solid #8a1c3c;border-radius:1rem;padding:1rem;text-align:center}
img{width:12rem;height:12rem}a{word-break:break-all;color:#4a1426;font-weight:700}
.note{opacity:.8}.backup{margin-top:1.5rem}
</style></head><body>
<h1>Party links</h1><p>Started $(Get-Date -Format "dddd d MMMM, HH:mm"). These links work until the start-party window is closed.</p>
<main>
$cards
</main>
$backup
</body></html>
"@
Set-Content -Path "links.html" -Value $html -Encoding UTF8
Start-Process (Join-Path $root "links.html")
Start-Process "$base/"

# ------------------------------------------------------------ running ---
Say ""
Say "=================================================================" Yellow
Say " THE GAME IS RUNNING" Yellow
Say "=================================================================" Yellow
Say " TV / main screen : $base/"
Say " Host (you)       : $base/host"
Say " Team captains    : $base/team"
Say " Secret bingo     : $base/bingo   (send privately!)"
if ($publicUrl -and $wifiUrl) { Say " Wi-Fi backup     : $wifiUrl" }
Say ""
Say " A page with all the links and QR codes has opened (links.html)."
Say " Keep this window OPEN, and keep the laptop awake and plugged in."
Say "=================================================================" Yellow
Say ""
Read-Host "When the party is over, press Enter here to STOP the game"

Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
if ($tunnel) { Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue }
Stop-Leftovers
Say "Stopped. The scores are saved in backend\state.json." Green
Start-Sleep -Seconds 2
