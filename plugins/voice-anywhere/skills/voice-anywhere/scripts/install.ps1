<#
.SYNOPSIS
  Installs (or uninstalls) Voice Anywhere for the current user. No admin rights needed.

.DESCRIPTION
  Creates a private Python environment in %LOCALAPPDATA%\voice-anywhere, installs the pinned
  dependencies, copies the scripts there and writes a "Start Voice Anywhere.cmd" launcher.
  Nothing is installed system-wide. Re-running it upgrades in place.

.PARAMETER Startup
  Always on: start hidden (no window) every time you sign in, and start it now.
  Runs with --background: one instance only, restarts itself after errors, logs (without
  transcripts) to %LOCALAPPDATA%\voice-anywhere\voice-anywhere.log.

.PARAMETER Shortcut
  Also put a "Voice Anywhere" desktop shortcut that runs it in a visible console.

.PARAMETER Arguments
  Default options baked into the launchers, for example '--key f9 --language en --vocab "Avanade, Copilot"'.

.PARAMETER SelfTest
  Run the microphone-free self-test after installing (downloads the speech model once).

.PARAMETER Uninstall
  Stop it, remove the install folder, the shortcuts and its tray-icon registry entry.
  The shared speech-model cache in %USERPROFILE%\.cache\huggingface is left alone (other apps may use it).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install.ps1 -Startup -SelfTest

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [switch]$Startup,
    [switch]$Shortcut,
    [string]$Arguments = "",
    [switch]$SelfTest,
    [switch]$Uninstall
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$home_ = Join-Path $env:LOCALAPPDATA "voice-anywhere"
$venv = Join-Path $home_ ".venv"
$py = Join-Path $venv "Scripts\python.exe"
$pyw = Join-Path $venv "Scripts\pythonw.exe"
$script = Join-Path $home_ "voice_anywhere.py"
$startupLink = Join-Path ([Environment]::GetFolderPath("Startup")) "Voice Anywhere.lnk"
$desktopLink = Join-Path ([Environment]::GetFolderPath("Desktop")) "Voice Anywhere.lnk"

function Stop-ThisInstall {
    # Only copies running from THIS install folder; other installs and dev copies are left alone.
    $pattern = [regex]::Escape($script)
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
        Where-Object { $_.CommandLine -match $pattern })
    foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    if ($procs.Count) { Start-Sleep -Milliseconds 800 }  # let file locks go
}

if ($Uninstall) {
    Write-Host "Uninstalling Voice Anywhere from $home_" -ForegroundColor Cyan
    Stop-ThisInstall
    foreach ($l in $startupLink, $desktopLink) { if (Test-Path $l) { Remove-Item $l -Force; Write-Host "Removed $l" } }
    $root = "HKCU:\Control Panel\NotifyIconSettings"
    if (Test-Path $root) {
        Get-ChildItem $root | ForEach-Object {
            $tip = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).InitialTooltip
            if ("$tip" -like "Voice Anywhere*") { Remove-Item $_.PSPath -Recurse -Force; Write-Host "Removed tray-icon registry entry" }
        }
    }
    if (Test-Path $home_) { Remove-Item $home_ -Recurse -Force; Write-Host "Removed $home_" }
    Write-Host ""
    Write-Host "Done. The speech model cache (%USERPROFILE%\.cache\huggingface\hub\models--Systran--faster-whisper-*)" -ForegroundColor Green
    Write-Host "was kept because other apps may share it. Delete those folders to free the space."
    return
}

function Find-Python {
    foreach ($cand in @(@("py", "-3"), @("python"), @("python3"))) {
        try {
            $exe = $cand[0]; $rest = @($cand | Select-Object -Skip 1)
            $v = & $exe @rest -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v -and [version]$v -ge [version]"3.12") { return , $cand }
        } catch { }
    }
    throw "Python 3.12 or later not found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH') and run this again."
}

Write-Host "Installing Voice Anywhere to $home_" -ForegroundColor Cyan
New-Item -ItemType Directory -Force $home_ | Out-Null
Stop-ThisInstall  # before pip, so no files are locked

if (-not (Test-Path $py)) {
    $cmd = Find-Python
    $exe = $cmd[0]; $rest = @($cmd | Select-Object -Skip 1)
    Write-Host "Creating Python environment..."
    & $exe @rest -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
}

Write-Host "Installing pinned dependencies (a minute or two the first time)..."
& $py -m pip install --disable-pip-version-check -q -r (Join-Path $here "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency install failed. See the pip output above." }

foreach ($f in "voice_anywhere.py", "trinity_icon.py", "overlay.py", "voice-anywhere.ico") { Copy-Item (Join-Path $here $f) $home_ -Force }
$ico = Join-Path $home_ "voice-anywhere.ico"

# Launcher: UTF-8 code page so non-ASCII profile paths work; % doubled so cmd doesn't expand it.
$launcher = Join-Path $home_ "Start Voice Anywhere.cmd"
$cmdArgs = $Arguments.Replace('%', '%%')
$lines = @(
    "@echo off",
    "chcp 65001 >nul",
    "title Voice Anywhere",
    "set HF_HUB_DISABLE_SYMLINKS_WARNING=1",
    "`"$py`" `"$script`" $cmdArgs %*",
    "pause"
)
[IO.File]::WriteAllText($launcher, ($lines -join "`r`n") + "`r`n", (New-Object Text.UTF8Encoding($false)))

$shell = New-Object -ComObject WScript.Shell
if ($Shortcut) {
    $l = $shell.CreateShortcut($desktopLink)
    $l.TargetPath = $launcher
    $l.WorkingDirectory = $home_
    $l.Description = "Hold a key, speak, release: text appears where your cursor is"
    $l.IconLocation = "$ico,0"
    $l.Save()
    Write-Host "Shortcut: $desktopLink"
}

$bgArgs = "`"$script`" --background $Arguments".Trim()
if ($Startup) {
    $l = $shell.CreateShortcut($startupLink)
    $l.TargetPath = $pyw
    $l.Arguments = $bgArgs
    $l.WorkingDirectory = $home_
    $l.WindowStyle = 7
    $l.Description = "Voice Anywhere (always on)"
    $l.IconLocation = "$ico,0"
    $l.Save()
    Write-Host "Starts automatically at sign-in: $startupLink"
}

if ($SelfTest) {
    Write-Host "Running self-test..."
    $env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
    & cmd /c "`"`"$py`" `"$script`" --self-test $cmdArgs`""
    if ($LASTEXITCODE -ne 0) { throw "Self-test failed." }
}

Write-Host ""
if ($Startup) {
    Start-Process -FilePath $pyw -ArgumentList $bgArgs -WorkingDirectory $home_ -WindowStyle Hidden
    Write-Host "Voice Anywhere is now running in the background (the Trinity knot appears briefly when it's ready)." -ForegroundColor Green
    Write-Host "It will start by itself every time you sign in. Log (no transcripts): $(Join-Path $home_ 'voice-anywhere.log')"
} else {
    Write-Host "Done. Start it with:" -ForegroundColor Green
    Write-Host "  `"$launcher`""
}
Write-Host "Click into any text box, hold RIGHT CTRL, wait for the chime, speak, and let go."
