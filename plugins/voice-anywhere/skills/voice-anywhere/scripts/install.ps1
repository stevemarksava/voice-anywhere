<#
.SYNOPSIS
  Installs Voice Anywhere for the current user (no admin rights needed).

.DESCRIPTION
  Creates a private Python environment in %LOCALAPPDATA%\voice-anywhere, installs the
  dependencies, copies the script there and writes a "Start Voice Anywhere.cmd" launcher.
  Nothing is installed system-wide. Uninstall by deleting that folder (and the shortcuts).

.PARAMETER Shortcut
  Also put a "Voice Anywhere" shortcut on the desktop.

.PARAMETER Startup
  Always on: start hidden (no window) every time you sign in, and start it now.
  Runs with --background: one instance only, restarts itself after errors, logs to
  %LOCALAPPDATA%\voice-anywhere\voice-anywhere.log.

.PARAMETER Arguments
  Default options baked into the launcher, for example '--key f9 --language en --vocab "Avanade, Copilot"'.

.PARAMETER SelfTest
  Run the microphone-free self-test after installing (downloads the speech model).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install.ps1 -Startup -SelfTest
#>
[CmdletBinding()]
param(
    [switch]$Shortcut,
    [switch]$Startup,
    [string]$Arguments = "",
    [switch]$SelfTest
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$home_ = Join-Path $env:LOCALAPPDATA "voice-anywhere"
$venv = Join-Path $home_ ".venv"
$py = Join-Path $venv "Scripts\python.exe"

function Find-Python {
    foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
        try {
            $exe = $cand[0]; $rest = @($cand | Select-Object -Skip 1)
            $v = & $exe @rest -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v -and [version]$v -ge [version]"3.9") { return , $cand }
        } catch { }
    }
    throw "Python 3.9 or later not found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and run this again."
}

Write-Host "Installing Voice Anywhere to $home_" -ForegroundColor Cyan
New-Item -ItemType Directory -Force $home_ | Out-Null

if (-not (Test-Path $py)) {
    $cmd = Find-Python
    $exe = $cmd[0]; $rest = @($cmd | Select-Object -Skip 1)
    Write-Host "Creating Python environment..."
    & $exe @rest -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
}

Write-Host "Installing dependencies (a minute or two the first time)..."
& $py -m pip install --disable-pip-version-check -q --upgrade -r (Join-Path $here "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency install failed. See the pip output above." }

Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'voice_anywhere\.py' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }  # replace a running copy
foreach ($f in "voice_anywhere.py", "trinity_icon.py", "voice-anywhere.ico") { Copy-Item (Join-Path $here $f) $home_ -Force }
$ico = Join-Path $home_ "voice-anywhere.ico"
$launcher = Join-Path $home_ "Start Voice Anywhere.cmd"
@(
    "@echo off",
    "title Voice Anywhere",
    "set HF_HUB_DISABLE_SYMLINKS_WARNING=1",
    "`"$py`" `"$(Join-Path $home_ 'voice_anywhere.py')`" $Arguments %*",
    "pause"
) | Set-Content -Path $launcher -Encoding ascii

$shell = New-Object -ComObject WScript.Shell
function New-Link($path) {
    $l = $shell.CreateShortcut($path)
    $l.TargetPath = $launcher
    $l.WorkingDirectory = $home_
    $l.Description = "Hold a key, speak, release: text appears where your cursor is"
    $l.IconLocation = "$ico,0"
    $l.Save()
    Write-Host "Shortcut: $path"
}
if ($Shortcut) { New-Link (Join-Path ([Environment]::GetFolderPath("Desktop")) "Voice Anywhere.lnk") }

$pyw = Join-Path $venv "Scripts\pythonw.exe"
$bgArgs = "`"$(Join-Path $home_ 'voice_anywhere.py')`" --background $Arguments".Trim()
if ($Startup) {
    # Always-on: starts hidden (no window) every time you sign in.
    $path = Join-Path ([Environment]::GetFolderPath("Startup")) "Voice Anywhere.lnk"
    $l = $shell.CreateShortcut($path)
    $l.TargetPath = $pyw
    $l.Arguments = $bgArgs
    $l.WorkingDirectory = $home_
    $l.WindowStyle = 7
    $l.Description = "Voice Anywhere (always on)"
    $l.IconLocation = "$ico,0"
    $l.Save()
    Write-Host "Starts automatically at sign-in: $path"
}

if ($SelfTest) {
    Write-Host "Running self-test..."
    $env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
    & cmd /c "`"`"$py`" `"$(Join-Path $home_ 'voice_anywhere.py')`" --self-test $Arguments`""
    if ($LASTEXITCODE -ne 0) { throw "Self-test failed." }
}

Write-Host ""
if ($Startup) {
    Start-Process -FilePath $pyw -ArgumentList $bgArgs -WorkingDirectory $home_ -WindowStyle Hidden
    Write-Host "Voice Anywhere is now running in the background (listen for a double beep when it's ready)." -ForegroundColor Green
    Write-Host "It will start by itself every time you sign in. Log: $(Join-Path $home_ 'voice-anywhere.log')"
} else {
    Write-Host "Done. Start it with:" -ForegroundColor Green
    Write-Host "  `"$launcher`""
}
Write-Host "Click into any text box, hold RIGHT CTRL, speak, and let go."
