# Contributing

Contributions are welcome: fixes, features, docs and examples. This project adopts the [Contributor Covenant Code of Conduct](https://avanade.github.io/code-of-conduct/).

## How

1. Branch from `main` and keep each pull request to one change.
2. Sign off every commit (`git commit -s`) to confirm the [Developer Certificate of Origin](https://developercertificate.org/).
3. Run `python -m unittest discover -s tests -v`, and `voice_anywhere.py --self-test` if you touched transcription. Add a test for what you changed.
4. If behaviour changes, update `SKILL.md` and `README.md` in the same pull request.
5. For a release, bump `version` in `.claude-plugin/marketplace.json`, `plugins/voice-anywhere/.claude-plugin/plugin.json` and `__version__` in `voice_anywhere.py`.

Use [semantic commit messages](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`).

## Rules

* Keep it local and private: no telemetry, no cloud calls beyond the one-time model download, and never write audio or transcripts to disk.
* Keep it generic: no client names or project-specific content.
* Bugs and ideas: open an issue.
