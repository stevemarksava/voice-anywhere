VERA — SIGN-OFF REPORT (re-test after fixes)
Feature/Task: Voice Anywhere v0.2.0 (working copy, base cfa1790 + fixes)
Date: 2026-11-05
Result: PASS

Fix verification:
| Finding | Claimed fix | Verified? | Evidence |
|---|---|---|---|
| K-01, V1-D10 | Exact key tracking via key_matches; chord cancels; stop chime only if start chime played | ✓ | Code: on_key_event/key_matches/record_while_held. Empirical test against the working-copy script with a real keyboard hook and synthetic keybd_event: Left Ctrl (0xA2, no ext) -> 0 starts; Right Ctrl (0xA3, ext) -> 1 start; Right Ctrl + F24 -> chorded=True. Steve's live log shows "Talk key used in a shortcut: recording discarded." from the chord run. 2 unit tests pass. |
| K-02 | Focus guard + console auto-send guard | ✓ (code + unit test) | deliver(): compares the foreground hwnd with the one captured at key-press; on mismatch it plays the "blocked" chime, pastes nothing and leaves the text on the clipboard. Auto-send is skipped for ConsoleWindowClass, CASCADIA_HOSTING_WINDOW_CLASS, mintty, VirtualConsoleClass and PuTTY. test_k02 passes. Not functionally exercised (would type into windows). |
| K-03 | Copyright holder is a decision for Steve | n/a | Not a code fix; left with Steve (.squad/decisions). |
| K-04, V1-D2 | No transcripts in any log file | ✓ | log_to_file = bool(log_path). Background passes log_path; --log passes args.log. The only print of transcript text is gated (line 578). The other "Heard:" print is the self-test's synthetic sentence, console only. |
| K-05, V1-D1 | README wording on logging | ✓ | README "Timings and lengths ... never what you said"; matches code. |
| K-06, V1-D9 | Clipboard restored; never speaks old clipboard | ✓ | read_selection: saves the clipboard, sets "", Ctrl+C, reads, restores unconditionally, returns if the text is blank. |
| K-07, K-08 | Pinned deps, no --upgrade | ✓ | requirements.txt has 8 == pins; install.ps1 has no --upgrade; the installer ran in the sandbox on Python 3.14.7 with the pins. |
| K-09, V1-D3 | Backoff, notify, fail fast on bad key | ✓ | retry_delay 5..600 s, reset after 300 s healthy, notify at >=3; `--key notakey` exits 2 with a message; tests pass. |
| V1-D4 | Range validation | ✓ | `--threads 0` -> "must be between 1 and 64, got 0", exit 2. |
| V2-D1, V1-D6, K-12 | Installer kills only its own copy | ✓ | Sandbox install x3 plus uninstall with LOCALAPPDATA overridden; Steve's PIDs 33816/11404 identical before and after (same CreationDate 18:03:30). |
| V1-D5 | Stop before pip | ✓ | Stop-ThisInstall precedes venv/pip in install.ps1. |
| V1-D7 | UTF-8 launcher, chcp 65001, %% escaping | ✓ | Generated .cmd: no BOM, `chcp 65001 >nul`, args line `--vocab 100%% %*`. A second run succeeded (idempotent). |
| K-10, K-11, V2-D2 | -Uninstall + docs | ✓ | Sandbox -Uninstall removed the sandbox folder, both shortcuts and the tray registry key, and exited 0. It did not touch Steve's process or his real install folder. README and SKILL document it. |
| V1-D8 | voice_level non-finite | ✓ | Unit test passes. |
| V1-D11 | Speaker thread resilient | ✓ (code) | speaker(): try/except rebuilds the voice and continues. |
| V1-D12 | One persistent animation thread | ✓ (code) | Steve's live 0.2.0 instance started cleanly. |
| V1-D13 | snake_case readable | ✓ | Regex at line 108; unit test passes. |
| V1-D14 | --list-mics whitespace; +9 tests | ✓ | 23 tests (14 -> 23). |
| K-13 | GDI cleanup | ✓ (code) | overlay.py diff frees the DIB and DC. |
| K-14 | LGPL notice | ✓ | README Credits. |
| K-15 | "Never on disk" qualified | ✓ | README and SKILL. |
| K-16 | EDR warning | ✓ | README and SKILL. |
| K-17 | Speed table labelled | ✓ | README. |
| V2-D4 | Local timestamps | ✓ | Live log header "0.2.0 started 18:03:31" matches the process CreationDate 18:03:30 and the file LastWriteTime 18:04:55 (local, UTC+1; the older 0.1.0 headers show the UTC bug). Unit test passes. |
| V2-D3 | Duplicate background launch exits quietly | ✓ | Code: "Already running; this copy exits." (accepted by design). |
| V2-D5 | Repo topics | not tested | Needs gh/network and is not a code matter. |
| V2-D6 | Harness lapse, no product change | n/a | |

Tests Run:
✓ K-01 synthetic-key hook test (Left 0 / Right 1 / chord True)
✓ Unit tests, venv python: 23 run, OK
✓ Unit tests, system python: 23 run, OK (1 skipped)
✓ --self-test (venv, working copy): PASSED, 100% word match
✓ --version -> voice-anywhere 0.2.0 (plugin.json and marketplace.json also 0.2.0)
✓ --threads 0 -> clean argparse error, exit 2
✓ --key notakey -> message, exit 2
✓ install.ps1 -SelfTest in sandbox (fresh venv on 3.14.7, pip, self-test passed)
✓ install.ps1 idempotent second run (exit 0); launcher .cmd contents checked
✓ install.ps1 -Uninstall in sandbox
✓ README relative links: all resolve (the only missing target is this sign-off file, as expected); Python 3.12+ matches install.ps1 and requirements.txt
✓ Live instance log: clean 0.2.0 start, model ready 3.2 s, no errors. The live script is byte-identical to the working copy (fc /b).
✓ Regressions: self-test, startup, tray/overlay construction (the K-01 harness built App with the tray off) and single instance (the live instance holds the mutex) all work. The tray and overlay visuals were not inspected on screen.

New defects found in re-test:
| ID | Severity | Description | Repro | Suggested fix |
|---|---|---|---|---|
| R-1 | Info | If a key-up for the talk key is ever lost (e.g. lock screen or RDP switch while held), talk_down stays True and the next press does not start a recording until a key-up is seen. | Code reading only. | On "down" while talk_down is already True, start anyway if not busy, or reset on a foreground change. |
| R-2 | Info | README/SKILL say it "reacts only to the configured keys". The hook also sees every key-down while the talk key is held (to detect chords). Nothing is stored or logged. | on_key_event, elif branch. | Reword: "other keys are only noticed while the talk key is held, to cancel shortcuts". |
| R-3 | Info | Console list covers classic console, Windows Terminal, mintty and PuTTY. Terminals embedded in IDEs (VS Code, JetBrains) are not detected, so --auto-send could press Enter there. Auto-send is opt-in. | Code reading only. | Document it, or drop auto-send for those host classes. |
| R-4 | Info | -Uninstall under a LOCALAPPDATA override still removed the real Startup/Desktop shortcuts and the tray registry key (GetFolderPath ignores the override). Expected for a real uninstall. | Observed, then restored. | none |
| R-5 | Info | SKILL says -Uninstall removes the registry "value"; the code removes the whole matching NotifyIconSettings key. | | Reword to "entry". |

Steve's live instance: PIDs 33816 and 11404 (pythonw, created 18:03:30) before and after the sandbox installs, uninstall and K-01 test: unchanged. Real %USERPROFILE%\AppData\Local\voice-anywhere still exists. The Startup and Desktop "Voice Anywhere.lnk" files were backed up, removed by the sandbox -Uninstall (R-4) and restored; the startup lnk hash matches its backup. The NotifyIconSettings registry was re-imported from the backup (export size identical, 226,534 bytes before and after). Live log: a single "shortcut discarded" entry caused by my F24 chord; no other disturbance.

Not tested (and why): K-02 focus-change behaviour and --auto-send functionally (would type into real apps; code and unit-test verified only). On-screen tray and overlay visuals, and actual dictation into an app (needs a human voice). Bluetooth chime timing. GitHub repo topics (V2-D5). -Startup and -Shortcut installer paths (they write to the real Startup folder and Desktop). The sandbox run passed `--vocab "100%"` through PowerShell, which dropped the inner quotes; that is a harness artefact, and the %% escaping itself was confirmed. K-03 copyright holder remains Steve's decision.

Sign-off: Every fix-log row was checked against the working-copy code, and the critical K-01 was proven on a real keyboard hook (Left Ctrl starts nothing, Right Ctrl starts one recording, and a chord cancels it). The installer no longer disturbs other installs, the launcher is correct, uninstall and re-install behave, 23/23 tests pass on both interpreters, and the docs match the code. The remaining items are Info-level only. Approved for push to the public repo.


## Delta re-check (R-items)
Date: 2026-11-05 (after the R-1/R-2/R-3/R-5 changes)
Result: DELTA PASS

- R-1 (code): `if not self.talk_down or not self.busy.locked():` is False for auto-repeat while recording, because talk() holds `busy` from just after the thread starts until the recording ends. So a repeat can't start a second recording, and it can't reset `chorded` mid-recording. A repeat that lands in the microseconds before talk() takes the lock can start a second thread, but that thread fails `busy.acquire(blocking=False)` and exits. `chorded` is only reset before recording begins. Chord case: once another key goes down, the OS repeats that key, not Right Ctrl, so the chord isn't re-triggered. A press with a stale `talk_down=True` and nothing recording now starts a new recording (the lost-release case).
- Tests: 24/24 OK on the venv python; 24 run with 1 skip on system python. `test_r1_lost_release_does_not_block_next_press` is included.
- Docs: README Privacy hook wording (R-2), IDE-terminal note (R-3) and registry "entry" wording (R-5) match the code. SKILL.md R-3 and R-5 match too.
- Info (not blocking; wording only, optional to fix before push):
  - README options list says `--auto-send ... (never in terminal windows)`, which overstates the R-3 note on line 186. Suggest "(skipped in standalone terminal windows)".
  - SKILL.md Troubleshooting (EDR row) still says "It only reacts to the configured keys and stores no keystrokes", which is looser than the README's R-2 wording. Suggest "other keys are only noticed while the talk key is held, to cancel shortcuts; none are stored".
- Steve's instance, shortcuts and registry untouched in this check (read-only plus unit tests). No commit and no push.

Verdict: approved for push, covering the working copy as of this delta check.
