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


## Delta re-check (0.2.1 packaging)
Date: 2026-11-05
Result: DELTA PASS

- (a) Schema: the new `plugins/voice-anywhere/plugin.json` validates against the Agent Plugins 1.0.0 schema (fetched from agent-plugins.org; checked with jsonschema, Draft 2020-12, in a throwaway venv, not Steve's). 0 errors. A negative control (bad name plus an extra property) gave 2 errors, so the check is real. Keys used: `$schema`, `name`, `version`, `description`, `author{name,url}`, `homepage`, `repository`, `license`, `keywords`, all allowed. `name` is `voice-anywhere`, which matches the pattern.
- (b) Version: 0.2.1 in all four places (marketplace.json, `.claude-plugin/plugin.json`, the new `plugin.json`, `__version__`). `--version` prints `voice-anywhere 0.2.1`. Both existing JSON files parse. No stale 0.2.0 is left in product files; only historical review text mentions it.
- (c) README: the change adds the note that other `SKILL.md`-reading tools (Gemini CLI `~/.gemini/skills/`, Cursor, Codex) work by copying, and the managed-laptop paragraph. The enterprise note matches the failure Steve saw. I did not install it in Gemini CLI, Cursor or Codex, so the Gemini path and "works the same way" are unverified; the wording is hedged ("Other tools that read SKILL.md skills"). Info only.
- (d) Nothing else changed: `git diff` is exactly 4 files, 6 lines (the marketplace.json and plugin.json version strings, the `__version__` string, and 2 README lines), plus the new plugin.json. 24/24 unit tests OK on the venv python.
- Steve's instance untouched (PIDs 33816/11404 unchanged). Throwaway venv deleted. No commit and no push.

Verdict: approved for push, covering the working copy as of this delta check.


## Delta re-check (demo GIF + HVE Core skill)
Date: 2026-11-05

### A. voice-anywhere repo (docs/demo.gif + README caption): PASS
- Uncommitted change is exactly `docs/demo.gif` (new) plus 4 README lines (image, caption, blanks). No other file changed.
- Privacy: I sampled all 244 frames (every frame at 1 fps, and every 4th frame in a 64-tile sheet). Every one shows only the demo "Message" window, the dark backdrop with "Hold Right Ctrl and talk", the Trinity knot and the mouse pointer. No taskbar, toast, other app, name or address appears. Source capture was a 1000x640 region (stage.py), not the full desktop. The dictated text is the demo sentence only.
- Caption truth: the GIF is 800x512, 12 fps, 244 frames, 20.33 s. That matches 5 s intro + 40 s at 8x (5 s) + 7.8 s normal + 2.5 s hold = 20.3 s. rec.mkv is 57.3 s and events.txt shows LISTEN at 7.0 s and PASTED at 53.1 s. In the GIF the knot glows during the sped-up part and the text lands about 3.3 s into the final normal-speed segment, which is consistent with a window taken from the end of the recording. "A real recording, not a mock-up... talking part is sped up" is accurate: it is a genuine gdigrab capture of the live app.
- Size 987,323 bytes, under 1 MB (just: about 12 KB of headroom). The README relative link `docs/demo.gif` resolves. Alt text and caption match the content.
- Info: Whisper misheard part of the demo sentence ("holy Trinity knot", "Mass pointer", "close in Flame and water"). It is honest, but visitors will see imperfect output. A cleaner take would look better. Not a defect.
- Reminder: `docs/demo.gif` is untracked, so it must be committed together with the README change, or the image will be broken on GitHub.

### B. HVE Core skill (local branch feat/experimental-voice-anywhere-skill, f679c63): PASS
Checked against voice-anywhere 0.2.1 (0a5562e, which is also origin/main and tag v0.2.1 on the public repo):
- Pinned source: full SHA 0a5562e7597a5c6c6b990a8e3a3a6890533aeead and tag v0.2.1 both exist on origin (`ls-remote` shows `v0.2.1^{}` = that SHA). `__version__ = "0.2.1"` at that commit. LICENSE says "Copyright (c) 2026 Avanade Inc.", matching the "MIT, Copyright Avanade Inc." claims.
- Quick Start: `git show 0a5562e:.../scripts/install.ps1` works, and the commit contains `plugins/voice-anywhere/skills/voice-anywhere/scripts/{install.ps1, overlay.py, requirements.txt, trinity_icon.py, voice-anywhere.ico, voice_anywhere.py}`. clone, checkout, `cd plugins\voice-anywhere\skills\voice-anywhere`, then `install.ps1 -Startup -SelfTest` is a valid sequence (I also confirmed `-Arguments '--vocab "A, B"'` passes its inner quotes when typed in PowerShell).
- Keys and options: Right Ctrl, Ctrl+Alt+R/S/Q, `--key/--model/--language/--vocab/--threads (1-64, half cores, max 8)/--device/--mic/--list-mics/--type/--auto-send/--restore-clipboard` all match the code and the README. "Under 0.4 s is ignored" matches `SAMPLE_RATE * 0.4`.
- Behaviour: text pasted into the window focused at key-press and left on the clipboard; no Enter unless `--auto-send`; auto-send skipped in standalone terminals and not detectable in editor terminals; tray states dim/glow/steady/grey: all accurate.
- Privacy: audio in memory only (self-test clip disclosed), local transcription, one-time HF download, logs lengths/timings only, one `IsPromoted` registry value removed by `-Uninstall`, shared model cache kept: all match the code and the earlier sign-off.
- Installer switches (`-Startup`, `-SelfTest`, `-Arguments`, `-Uninstall`; re-run upgrades in place), the ~300 MB / 145 MB figures and Python 3.12+ match install.ps1, requirements.txt and the README.
- issue.md and pr.md: factual claims agree with the SKILL.md. The commit touches 6 files (SKILL.md, two generated indexes, the new reference page, the vscode-playwright reflow, plugin.json), which matches the PR "Files changed" list. The working tree is clean and nothing was pushed.
- Info (not blocking):
  1. The Security bullet says the hook "acts only on the configured keys and never records or stores which keys are pressed". True, but the upstream README now adds that it also notices other key-downs while the talk key is held (to cancel shortcuts). Consider mirroring that sentence.
  2. The PR draft says "87 skills" and describes generator output. I did not run the HVE Core generators or its lint/Pester checks, so that part is the author's claim.
  3. The skill's "red-teamed and QA-signed-off" wording is true for 0.2.0 and the 0.2.1 packaging delta (see above).

- Steve's instance untouched (PIDs 33816/11404 unchanged). No commits or pushes in either repo. Temp files in vera-rt deleted.

Verdict: A PASS (approved to commit and push, with the GIF committed alongside the README). B PASS (content accurate and installable at the pinned commit).


## Final gate (Win+H comparison, HVE Core contribution, outbound texts)

Vera, 5 Nov 2026 23:xx. Evidence only. No commits, pushes or edits besides this section. Steve's running process and browser untouched. I did NOT run the HVE Quick Start installer: it stops the copy running from %LOCALAPPDATA%\voice-anywhere, which is Steve's live instance. I checked its pieces statically instead (see B).

### A. README "Why not just use Win+H?" (uncommitted): FAIL, 1 required fix + 4 small ones

Verified against the fetched Microsoft pages and the code:
- Win+H: online, "powered by Azure Speech services", internet required: TRUE. Stops on the "Stop listening" command or the mic button: TRUE. Voice commands ("delete that", "select that", press Enter): TRUE. Auto-punctuation is a setting: TRUE. Fluid dictation is Copilot+ only: TRUE (also English only, on-device SLM). 46 languages: TRUE, I counted 46 bullets, but they are locale entries (en-US, en-GB, fr-CA and so on), not 46 distinct languages.
- Voice Access: Windows 11 22H2+, works without an internet connection, controls the PC by voice: TRUE.
- Voice Anywhere: push-to-talk, paste after release, no voice-command parser (grep found none), `--vocab` is passed as Whisper `initial_prompt`, `--language` defaults to auto-detect, Agent Skill (SKILL.md present): TRUE. Whisper ~99 languages: the OpenAI README does not state a number, but `tokenizer.py` lists 99 in the standard model, and "quality varies" is stated. Acceptable.

Required fix:
1. README.md:34, Voice Anywhere is not unique on vocabulary and the Voice Access cell is false. The Microsoft page documents "Add to vocabulary" (voice command "Add to vocabulary") for Voice Access.
   Old: `| Built-in vocabulary |`
   New: `| "Add to vocabulary" lets you add your own words |`
   Also, Win+H is not shown as having any custom vocabulary. That is fair, because the page lists none, but the intro sentence of "Use Voice Anywhere if ... your own jargon" must not imply Voice Access cannot do it.

Small fixes (unfair, overclaimed or unverified):
2. README.md:35 overclaim. Old: `already approved by IT`. New: `built in, so usually easier to get approved` (IT approval is not guaranteed).
3. README.md:30 simplification. Voice Access has listening, sleep and mic-off states (Alt+Shift+B and Alt+Shift+C). Old: `Always listening; you control the whole PC by voice`. New: `Listens continuously while on (can be put to sleep or muted); you control the whole PC by voice`.
4. README.md:33. Old: `46 listed by Microsoft`. New: `46 listed by Microsoft (counting regional variants)`. Old: `auto-detected per sentence`. New: `auto-detected for each recording` (the code detects once per transcribe call).
5. README.md:31, "Text appears: Live, as you speak" for Win+H and Voice Access. The Voice Access page documents real-time transcription feedback. The Win+H page I fetched does not say "live" in text, so it is true in practice but not sourced. Either soften or accept. Not blocking.
6. README.md:33, Voice Access language cell: "See Microsoft's list" has no link. Optional: add the link.
7. README.md:209 (existing text, not part of the delta): "The only network access is the one-time model download". See B1, same inaccuracy. Fix together.
8. README.md:214 (existing): the `keyboard` "last release 2021". PyPI shows the last release is 0.13.5 on 23 Mar 2020. Old: `last release 2021`. New: `last release 2020`.

### B. HVE Core contribution (d934bdb, fdda91a): FAIL, content fixes needed (structure and validators PASS)

Validator results (in the clone, re-run now):
- `npm run validate:skills`: PASS (90 skills, 0 errors, 0 warnings).
- `npm run plugin:validate`: PASS (manifest in sync; 87 skills).
- `npm run docs:generate:check`: PASS (0 create, 0 update, 0 remove; 206 unchanged).
- cspell on the 8 changed files: PASS (0 issues).
- Extra: `lint:frontmatter` PASS, `lint:md` PASS (0 issues), `lint:tables` PASS, `lint:artifact-portability` PASS, `lint:asset-docs` PASS (0 errors; 46 warnings, none mentioning voice-anywhere). `docs:test` could not run (jest is not installed in docs/docusaurus in this clone). That is an environment gap, not a finding. The pr.md Testing list does not claim it.

Guide compliance (published skills and ai-artifacts-common pages): PASS.
- Frontmatter: name matches the directory, description is a single sentence with no attribution suffix, valid optional fields, metadata keys are recognised ones.
- Required sections present: H1, Overview, Prerequisites (## with ### Windows and ### macOS and Linux), Quick Start, Troubleshooting.
- XML block `example-install-pinned` is a unique, matching pair on its own lines, with the fence inside. No attribution footer in SKILL.md.
- Paths are skill-root-relative; the portability lint passes. SECURITY.md is required for runtimes and is present. The footer in SECURITY.md is allowed (the rule covers SKILL.md only).
- RFC 2119: SKILL.md:28 "Prefer ..." and the Overview's mixed imperatives are lowercase but acceptable. Optional polish: "Prefer" → "SHOULD prefer".

Factual checks that PASS: tag/commit pin; the v0.2.1 file tree; installer switches `-Startup -SelfTest -Arguments -Uninstall`; the `cd plugins\voice-anywhere\skills\voice-anywhere` path exists at that commit; Python 3.12+ check in `install.ps1`; 0.4 s minimum; Ctrl+Alt+R/S/Q; `--threads` 1–64 and default half the cores capped at 8; `--mic --list-mics --type --auto-send --restore-clipboard`; terminal skip for auto-send; `IsPromoted` under HKCU; single-instance mutex and restart backoff; log with lengths only; audio in memory only; the self-test clip is deleted (`os.remove`); the Win+H and Voice Access statements in SKILL.md:28-32 and issue.md match the Microsoft pages; MIT licence, "Copyright (c) 2026 Avanade Inc."; the anonymous raw LICENSE fetch at the pin returns 200.

Required fixes:
B1. "Only network call is a one-time model download" is false in three ways:
   (a) The installer runs `pip install -r requirements.txt`, which contacts PyPI, and the Quick Start does `git clone` from GitHub.
   (b) `WhisperModel(...)` calls `huggingface_hub.snapshot_download(..., local_files_only=False)` on every start (faster_whisper 1.2.1 utils.py:116), and the script never sets HF_HUB_OFFLINE. So each start sends a metadata/update check to huggingface.co, not only the first. No audio or text is sent.
   Files and lines:
   - SKILL.md:7 (`compatibility`): `the only network call is a one-time speech-model download from Hugging Face` → `at run time the only network access is the speech-model download and Hugging Face's cache/update check when the model loads; install also contacts PyPI and GitHub`.
   - SKILL.md:153-155 (Privacy): `The only network access is the one-time speech-model download from Hugging Face` → `No audio or text is sent anywhere. Network access is limited to: GitHub and PyPI at install time, and Hugging Face for the speech model (downloaded once, with a metadata check each time the model loads)`.
   - SECURITY.md:46 `after the one-time model download, the tool makes no network calls` → `at run time the only network access is Hugging Face model-metadata checks; no audio or text is sent`.
   - SECURITY.md:55 (posture table, Network egress): `One-time faster-whisper model download from Hugging Face over TLS; none afterwards` → `PyPI and GitHub at install; Hugging Face over TLS for the model (download once, update check on each load)`.
   - SECURITY.md:91 (accDescr): `a one-time model download is the only external call` → `model download and update checks are the only external calls at run time`.
   - SECURITY.md:152 and :106 (ADV-b / diagram "one-time download"): change to "download and update check".
   - issue.md Requirements bullet `the only network call is the one-time model download` → same fix. pr.md "one-time model download" mentions (Files-changed SECURITY.md line and the Security Considerations bullet) → "model download".
   - SECURITY.md B4 omits the PyPI dependency chain (8 pinned packages, no hashes). Add a row: `Pinned PyPI dependencies installed without hash checking | Low | Med | Low | Accepted`. Otherwise the supply-chain bucket misleads by leaving out the larger attack surface. The ADV-c row and the `G-*` gap table also need a `G-SUP-2` for this.
   - docs/reference/skills/experimental/voice-anywhere.md, the SKILL.md description and the reference-page overview say "speech-to-text running offline". That is defensible: transcription is local. Leave it, or say "on-device".
B2. `keyboard` "last release 2021" is wrong; PyPI shows 0.13.5 on 23 Mar 2020.
   - SKILL.md:180: `last release 2021` → `last release 2020`.
   - SECURITY.md:297: `last release 2021` → `last release 2020`.
   (The same error exists in upstream README.md:214, fix per A8. Fixing it only in HVE would leave the two out of step, but HVE must be right.)
B3. issue.md Purpose: `speaking is roughly 3x faster than typing` is unsourced. Delete it: `because speaking is roughly 3x faster than typing for rich prompts, and because` → `because dictating long prompts is easier than typing them, and because`.
B4. SECURITY.md:309 and the STRIDE framing. The model is honest that it models the upstream tool; that is fine, and registration in security-model.md is accurate. The "Tampering"/"Repudiation" cells are weak but not false ("cannot attribute content to a user" at :167 is a non-sequitur; consider deleting it). Not blocking.
B5. Not blocking, but Steve should decide: both commits carry the author email `s.marks@avanade.com`, which will be public in the PR. All text files are clean otherwise. No `s.marks`, `C:\Users`, `scab1`, local paths, `.squad` paths, client names, or Accenture/EME/FDE references. `Avanade` appears only as the copyright holder and in the example vocabulary string (reference page and SKILL.md), which is fine. If he wants a neutral email, rewrite the author before pushing.
B6. Quick Start works as written, statically verified: pin and path exist, the switches exist, and Steve's own `copilot plugin install` of the same tag works. It was not executed (would stop his live instance). Caveat: the pinned `requirements.txt` was tested on Python 3.14 per its header; SKILL.md says 3.12+. The installer enforces ≥3.12, but it was tested on 3.14 only. Add `(tested on 3.14)` to the Prerequisites bullet, or soften.

### C. Outbound texts (sections 1 and 4): PASS

- SHA: `refs/tags/v0.2.1` on origin is an annotated tag object a35331f; its peeled commit is `0a5562e7597a5c6c6b990a8e3a3a6890533aeead`. Matches section 1. Origin `main` is 0dd14f9 (the local HEAD), so the tag and plugin path are reachable.
- Section 1: the plugin path `plugins/voice-anywhere`, version 0.2.1, MIT, author, homepage and keywords match plugin.json at the pin. The "reports are in .squad/reviews/" claim is TRUE at the pin. "Copilot CLI marketplace install verified" is TRUE (see below). "vally lint passes": NOT verifiable here (no vally on this machine). Either run it before sending or drop that clause. Also, "nothing leaves the machine" matches plugin.json wording, but see B1: model update checks are made. It is true for audio and text, so add "your voice and text" if you want to be strict.
- Section 4: `copilot plugin marketplace add stevemarksava/voice-anywhere` returned "already registered" (idempotent; this is the expected message when it is already added). `copilot plugin install voice-anywhere@voice-anywhere` returned "installed successfully. Installed 1 skill." Both work as written. "Defender may flag it (keyboard hook)" is consistent with the README. "Claude Code's enterprise policy blocks outside marketplaces" is an environment claim I cannot verify from public evidence; it is Steve's own statement, so I did not rule on it.

### Verdict
- A: FAIL until fix 1 (Voice Access vocabulary cell) is applied. Fixes 2-4 and 8 strongly recommended.
- B: FAIL until B1 (network claims) and B2 (keyboard year) are applied. B3 required (unsourced figure). Validators all PASS; structure and guide compliance PASS.
- C: PASS. Optional: run vally or drop the clause.


## Delta (0.2.2 offline-first)

Vera, 6 Nov 2026. I ran everything independently in separate python processes using the existing venv. I did not touch Steve's running instance or his browser. I did not commit or push. The scratch folder `.vera-tmp` is deleted; `git status` shows only the 8 expected modified files.

### (a) Zero-network claim: reproduced, with one wording caveat
- Spy: patched `socket.getaddrinfo`, `gethostbyname(_ex)`, `socket.socket.connect` and `connect_ex`. Then I imported every runtime dependency (`sounddevice, pystray, win32api, win32clipboard, win32event, pyperclip, keyboard, PIL, numpy, huggingface_hub, ctranslate2, faster_whisper`), plus `voice_anywhere` 0.2.2. Then I ran the real `load_model()` (base, cached) and one VAD transcription of silence.
  - After imports: `[]`. After load and transcribe: `network lookups: []`. Zero DNS lookups and zero non-loopback connects.
- Positive control (proves the spy catches it): the 0.2.1 behaviour (`WhisperModel("base")` without `local_files_only`) produced `lookups: ['huggingface.co']`. So B1 was real and 0.2.2 fixes it.
- No telemetry from pystray, pywin32, sounddevice, ctranslate2 or huggingface_hub showed up. The spy covers Python sockets for the whole process, including imports. It would not see a raw socket opened inside a native extension. I have no evidence of any, and the dependencies are not known to do this, so I do not rate it a blocker.
- Not covered by the spy: read-aloud (Windows SAPI voices, local). The installer and `git clone` do use the network (PyPI, GitHub).

### (b) Fallback path: works
- Exception raised by `local_files_only=True` on an uncached model (checked with `large-v2`): `huggingface_hub.errors.LocalEntryNotFoundError`, a subclass of `FileNotFoundError` and `OSError`. `except Exception` catches it. No hang, no partial state.
- Real test through `load_model()` with `--model tiny` (not previously cached; it added ~75 MB to Steve's shared HF cache, as agreed):
  - Run 1 (uncached): loaded successfully, lookups to `huggingface.co` as expected (download).
  - Run 2 (now cached): `network lookups: []`.
- Behaviour note, not a defect: the broad `except Exception` also retries the online path after any other offline-load failure (for example a corrupt cache). Any real error (such as CUDA unavailable) re-raises from the second call, so it is not hidden.

### (c) Tests, versions, README
- Tests: venv 25/25 OK; system python 25 tests OK (1 skip). The new test checks the cached case (one offline load) and the uncached case (offline attempt, then one download). Its fake raises `OSError`, which matches the real exception's parent class.
- Version 0.2.2 appears in all four places (`marketplace.json`, both `plugin.json`, `voice_anywhere.py`). No stale 0.2.1 outside .squad and tests.
- Win+H table: all A fixes applied correctly (Add to vocabulary, sleep/mic-off, regional variants, per recording, approval wording). `keyboard` is now "2020" (matches PyPI 23 Mar 2020).
- Nothing else changed beyond the load_model message text ("first run downloads it once" removed from the console print, correct) and the Win+H table, README Privacy, SKILL.md Privacy and tests.

### Required wording fix (README.md:209 and SKILL.md:106)
The claim "Network access happens only during installation ... After that ... no network calls at all" is true for a cached model, but not exact as written: the model downloads on the first run (or at `-SelfTest`), and a different `--model` (for example `small`) needs its own first-time download later. Replace:
- README.md:209, old: `Network access happens only during installation: Python packages from PyPI, and the speech model from Hugging Face (` + "`Systran/faster-whisper-*`" + `) the first time it runs. After that it loads the model from your disk and makes no network calls at all; the squad verified this.`
  new: `The only network access is when you install (Python packages from PyPI) and the first time a speech model is used (it is downloaded once from Hugging Face, ` + "`Systran/faster-whisper-*`" + `; a different --model needs its own download). Once a model is on your disk, the app loads it from there and makes no network calls at all; the squad verified this with a socket-level check.`
- SKILL.md:106, old: `Network access happens only at install time (PyPI packages, and the one-time model download from Hugging Face). After that the model loads from disk with no network calls.`
  new: `Network access happens only at install (PyPI packages) and the first time a model is used (one download per model from Hugging Face). Once the model is on disk it loads offline with no network calls.`

Optional: CONTRIBUTING.md:17 "no cloud calls beyond the one-time model download" is still accurate; leave it.

### Verdict: PASS, conditional on the wording fix above (docs only; no code change needed). After that edit the delta is cleared to commit as v0.2.2.
