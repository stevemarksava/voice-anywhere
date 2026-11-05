# Decision: retrofit the squad gates to Voice Anywhere

Date: 2026-11-05
Decided by: Steve (request) / Superman (execution)

## Context
Voice Anywhere 0.1.0 was built solo in one Scout session and pushed public in three commits (aef7365, 6427a82, cfa1790) without Kryptonite, Vera or Coach. Steve asked whether the squad had tested it, and the honest answer was no.

## Decision
- Run the full gate retroactively: Kryptonite red team, then Vera fanned out as V1 (static, unit, edge cases) and V2 (clean install from GitHub in a sandbox), then fixes, Vera re-test and sign-off, then Coach game tape.
- Publish every report in `.squad/reviews/` and link them from the README's "Tested by the squad" section, including the admission that 0.1.0 went out unreviewed.
- Ship the fixes as 0.2.0, with dependencies pinned to the versions the squad tested.

## Outcome
- Kryptonite: DO NOT SHIP as configured. K-01 was critical: Right Ctrl also fired on Left Ctrl, so every Ctrl shortcut opened the mic.
- Vera V1 and V2: CONDITIONAL PASS.
- After the fixes, Vera's re-test: PASS, approved for push.
- K-03 (the copyright holder): Steve kept Avanade Inc.; see 2026-11-05-copyright-avanade.md.

## Lesson
A public push is shipping. "It's a small personal tool" does not exempt it from Kryptonite and Vera, and the critical bug was only found by the red team.
