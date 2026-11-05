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

- Windows 10 or 11, a microphone, Python 3.9 or later on PATH (`py -3` or `python`).
- About 300 MB disk for dependencies, plus the speech model (base ≈ 145 MB, small ≈ 470 MB), downloaded once from Hugging Face on first run.
- No admin rights. Nothing is installed system-wide.

## Install

From this skill folder, run in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -Startup -SelfTest
```

This creates `%LOCALAPPDATA%\voice-anywhere\` with a private Python environment, the script and `Start Voice Anywhere.cmd`.

- **`-Startup` (recommended)** makes it always on: it starts hidden with `pythonw --background` at every sign-in, and starts it immediately. Background mode runs a single instance, restarts itself after errors, logs to `%LOCALAPPDATA%\voice-anywhere\voice-anywhere.log` and double-beeps when ready.
- `-Shortcut` adds a desktop shortcut that runs it in a visible console.
- `-Arguments '...'` bakes default options into both.
- `-SelfTest` synthesises a sentence with the Windows voice, transcribes it and must print `SELF-TEST PASSED`.

To check it's running, look for `pythonw.exe` with `voice_anywhere.py` in its command line, or read the log.

## Use

**Indicator:** a Trinity knot in the taskbar notification area.

- **Dim colours:** on and waiting.
- **Glowing and pulsing with the voice:** listening (brighter means louder).
- **Steady glow:** transcribing.
- **Grey:** paused or starting.

Right-click it to pause, toggle auto-send, open the log or quit. On Windows 11 it pins itself to the visible taskbar from the second start; otherwise it's under the **^** overflow arrow.

| Action | Default key |
|---|---|
| Dictate: hold, speak, release. Text is pasted at the cursor and stays on the clipboard | **Right Ctrl** (hold) |
| Read selected text aloud (reads the clipboard if nothing is selected) | **Ctrl + Alt + R** |
| Stop reading | **Ctrl + Alt + S** |
| Quit | **Ctrl + Alt + Q** |

It never presses Enter unless `--auto-send` is set, so the user always reviews before sending.

## Options

Pass them on the command line, or bake them in with `install.ps1 -Arguments '...'`. Run `--help` for the full list.

| Option | Use it when |
|---|---|
| `--key "f9"` | Right Ctrl is awkward or clashes. Use one physical key, not a combination. |
| `--model small` | Accuracy matters more than speed (`tiny` < `base` < `small` < `medium` < `large-v3`). |
| `--language en` | Auto-detect picks the wrong language on short phrases. |
| `--vocab "Avanade, Copilot, Fabric"` | Names or jargon get misheard. Keep the list short. |
| `--threads N` | Tuning speed. Default is half the logical cores, capped at 8. |
| `--device cuda` | There's an NVIDIA GPU with CUDA libraries installed. |
| `--mic 3` | The wrong microphone is used. `--list-mics` shows the options. |
| `--type` | An app blocks paste. |
| `--restore-clipboard` | The user wants their old clipboard back after pasting. |
| `--auto-send` | Hands-free chat: press Enter after pasting. |
| `--no-read`, `--no-beep`, `--no-tray` | Turn off read-aloud, beeps or the tray knot. |

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
| Antivirus warning | It uses a global keyboard hook (the `keyboard` package) to see the talk key. It only reacts to the configured keys and stores nothing. |
| No beep when holding the key | It isn't running (no knot in the tray). Check the log, re-run `install.ps1 -Startup`, or use the desktop shortcut to watch it live. |
| "Already running" | A background copy is on. Ctrl+Alt+Q stops it. |

## Privacy

- Audio is recorded only while the key is held, kept in memory and never written to disk.
- Transcription runs locally. Neither audio nor text is sent anywhere.
- In background mode the log records timings and lengths only, never what was said.
- The only network call is the one-time model download.
- The transcript goes to the clipboard (and stays there unless `--restore-clipboard` is set), so clipboard history or sync tools may keep it.
