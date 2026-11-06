# Decision: launch channels for Voice Anywhere

Date: 2026-11-06
Decided by: Steve Marks

Submitted after Vera's final gate (PASS on v0.2.2, the HVE Core files and the outbound texts):

| Channel | Where | Status |
|---|---|---|
| awesome-copilot (Copilot's built-in marketplace) | github/awesome-copilot#6279, external plugin, v0.2.2 @ 73fb38d | Automated intake passed; `ready-for-review` |
| HVE Core experimental skill | microsoft/hve-core#3336, Skill Request (issue first, per CONTRIBUTING) | `needs-triage`. The PR branch is ready locally and held until maintainers answer the three fit questions |
| EME FDE working group | Teams "EME FDE Chat" | Posted |

- HVE Core commits are authored with Steve's GitHub no-reply address (his choice), so the work email isn't published in Microsoft's repo.
- Not chosen: GitHub Marketplace (Apps and Actions only), Anthropic directory (needs a paid plan), Show HN, LinkedIn, and Avanade/Accenture internal stores. The internal stores matter most for colleagues on managed Claude Code (enterprise allowlist).
