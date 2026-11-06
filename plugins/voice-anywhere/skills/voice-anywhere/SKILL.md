---
name: voice-anywhere
description: Local, private push-to-talk dictation for Windows that types your words wherever the cursor is (Teams, WhatsApp, Outlook, browsers, AI chats like Copilot, Claude or Scout, terminals, IDEs), plus read-aloud of selected text. Speech-to-text runs offline on the user's machine with faster-whisper; no cloud service, no account, no cost. Use when the user wants voice typing, dictation, speech-to-text, push-to-talk, to "talk instead of type", to talk to an AI assistant by voice, to have replies read aloud, to set up, start, tune or troubleshoot Voice Anywhere, or asks for a private/offline alternative to cloud dictation.
license: MIT
---

# Voice Anywhere

Hold a key, speak, let go: the words appear wherever the cursor is, in any app. Select text and press a hotkey to hear it read aloud. Everything runs on the user's own Windows machine.

## What you (the agent) do with this skill

You help the user **install, start, tune and troubleshoot** the tool. You can't speak into their microphone, so live testing is theirs; use `--self-test` to prove the install works without a mic.

## Requirements

- Windows 10 or 11, a microphone, Python 3.12 or later on PATH (`py -3` or `python`). Dependencies are pinned to the exact versions the squad tested.
- About 300 MB disk for dependencies, plus the speech model (base ≈ 145 MB, small ≈ 470 MB), downloaded once from Hugging Face on first run.
- No admin rights. Nothing is installed system-wide.

## Install

From this skill folder, run in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -Startup -SelfTest
```

This creates `%LOCALAPPDATA%\voice-anywhere\` with a private Python environment, the script and `Start Voice Anywhere.cmd`.

- **`-Startup` (recommended)** makes it always on: it starts hidden with `pythonw --background` at every sign-in, and starts it immediately. Background mode runs a single instance, restarts itself after errors, logs to `%LOCALAPPDATA%\voice-anywhere\voice-anywhere.log` and briefly shows the big knot when ready.
- `-Shortcut` adds a desktop shortcut that runs it in a visible console.
- `-Arguments '...'` bakes default options into both.
- `-SelfTest` synthesises a sentence with the Windows voice, transcribes it and must print `SELF-TEST PASSED`.
- `-Uninstall` stops it and removes the install folder, the shortcuts and the tray-icon registry entry. The shared Hugging Face model cache (`%USERPROFILE%\.cache\huggingface\hub\models--Systran--faster-whisper-*`) is kept.

Re-running the installer upgrades in place, and only stops the copy running from its own install folder.

To check it's running, look for `pythonw.exe` with `voice_anywhere.py` in its command line, or read the log.

## Use

**Indicators:**

- **While talking:** a large Trinity knot floats at the bottom-centre of the screen. It glows with the voice, dims in silence, is click-through and never takes focus. A rising chime plays once the mic is actually live (on Bluetooth headsets that's about 0.5–1 s after the key press), and a falling chime plays on release.
- **The rest of the time:** a small knot sits in the taskbar notification area.
  - **Dim colours:** on and waiting.
  - **Glowing and pulsing with the voice:** listening (brighter means louder).
  - **Steady glow:** transcribing.
  - **Grey:** paused or starting.

Right-click it to pause, toggle auto-send, open the log or quit. On Windows 11 it pins itself to the visible taskbar from the second start; otherwise it's under the **^** overflow arrow.

| Action | Default key |
|---|---|
| Dictate: hold, wait for the chime, speak, release. Text is pasted into the window that had focus at key-press and stays on the clipboard | **Right Ctrl** (hold; matched exactly, so Left Ctrl never triggers it) |
| Read selected text aloud (clipboard is restored; nothing selected = nothing read) | **Ctrl + Alt + R** |
| Stop reading | **Ctrl + Alt + S** |
| Quit | **Ctrl + Alt + Q** |

It never presses Enter unless `--auto-send` is set, so the user always reviews before sending, and even then never in a standalone terminal window (where Enter could run a command; terminals embedded in IDEs cannot be detected, so advise against --auto-send there). If the user switches windows while it transcribes, it doesn't paste (low chime) and the text waits on the clipboard. Using the talk key in a shortcut (for example Right Ctrl + C) cancels the recording.

## Options

Pass them on the command line, or bake them in with `install.ps1 -Arguments '...'`. Run `--help` for the full list.

| Option | Use it when |
|---|---|
| `--key "f9"` | Right Ctrl is awkward or clashes. Use one physical key, not a combination. |
| `--model small` | Accuracy matters more than speed (`tiny` < `base` < `small` < `medium` < `large-v3`). |
| `--language en` | Auto-detect picks the wrong language on short phrases. |
| `--vocab "Avanade, Copilot, Fabric"` | Names or jargon get misheard. Keep the list short. |
| `--threads N` | Tuning speed (1–64). Default is half the logical cores, capped at 8. |
| `--device cuda` | There's an NVIDIA GPU with CUDA libraries installed. |
| `--mic 3` | The wrong microphone is used. `--list-mics` shows the options. |
| `--type` | An app blocks paste. |
| `--restore-clipboard` | The user wants their old clipboard back after pasting. |
| `--auto-send` | Hands-free chat: press Enter after pasting (skipped in standalone terminal windows; not detectable in IDE-embedded terminals). |
| `--no-read`, `--no-beep`, `--no-tray` | Turn off read-aloud, chimes or the tray knot. |
| `--overlay cursor` / `off`, `--overlay-size 320` | Move the big knot next to the mouse pointer, turn it off, or resize it. |
| `--chime-volume 0.6` | The chime is too quiet. |

## Troubleshooting

| Symptom | Fix |
|---|---|
| Another app pops up or flickers while the key is held | The talk key clashes with that app's shortcut (e.g. Ctrl+Alt+Space). Choose another `--key`. |
| Nothing is pasted | Click into a text box first. Elevated (admin) windows ignore input from a non-admin process, so run the launcher as admin for those. For apps that block paste, use `--type`. |
| "Too short, ignored" | Hold the key for the whole sentence. Under 0.4 s is ignored. |
| Slow | Try `--model base` or `tiny`. Run `--self-test` with different `--threads`. The first transcription after start is slower. |
| Wrong words | Try `--model small`, `--language xx` and `--vocab "..."`. Use a headset mic. |
| Silence or "Heard nothing" | Check the mic with `--list-mics` and the Windows privacy setting *Let desktop apps access your microphone*. |
| Model download blocked | A proxy or firewall is blocking huggingface.co. Download once on another network, or set `HF_ENDPOINT` to an internal mirror. |
| Antivirus / EDR warning | Expected: a global keyboard hook, clipboard automation and a background Python process look keylogger-like to endpoint security. It acts only on the configured keys and never records or stores keystrokes. On a managed work laptop, check with IT first. |
| No beep when holding the key | It isn't running (no knot in the tray). Check the log, re-run `install.ps1 -Startup`, or use the desktop shortcut to watch it live. |
| "Already running" | A background copy is on. Ctrl+Alt+Q stops it. |
| A message box says it couldn't start | The background copy failed three times in a row (often: no network on the first run, so the model couldn't download). It keeps retrying with growing waits up to 10 minutes; the log has the error. |
| Text didn't paste, low chime | Focus changed while transcribing. Press Ctrl+V where you want it. |

## Privacy

- Microphone audio is recorded only while the key is held, kept in memory and never written to disk. (`--self-test` writes a computer-voice clip to temp and deletes it.)
- Transcription runs locally. Neither audio nor text is sent anywhere.
- Log files (background or `--log`) record timings and lengths only, never what was said.
- It sets one HKCU registry value (`IsPromoted` under `Control Panel\NotifyIconSettings`) to pin the tray icon; `-Uninstall` removes that entry.
- Network access happens only at install (PyPI packages) and the first time a model is used (one download per model from Hugging Face). Once the model is on disk it loads offline with no network calls.
- The transcript goes to the clipboard (and stays there unless `--restore-clipboard` is set), so clipboard history or sync tools may keep it.
