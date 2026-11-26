# AGENTS.md

Guidance for AI coding agents (GitHub Copilot, Claude Code, Gemini CLI, Codex, etc.)
working in the `midea-cloud` repository. This is the canonical instructions file;
`CLAUDE.md` and `.github/copilot-instructions.md` point here.

`midea-cloud` is a Python library to control Midea M-Smart appliances via the Midea
cloud. Python ≥ 3.12 (CI tests every version in the `.github/workflows/python-build.yml`
matrix).

## Build, test, lint

The dev environment uses [uv](https://docs.astral.sh/uv/). Bootstrap it with
`./scripts/setup.sh` (Linux/macOS/WSL2) or `scripts\setup.ps1` (Windows), which creates a
`.venv`, installs everything (runtime + dev + types) from `pyproject.toml`/`uv.lock`, and
installs the [prek](https://github.com/j178/prek) hooks. Prefix commands with `uv run` to
use that environment.

- Run all tests: `uv run python -m pytest ./tests/`
- Run one test file: `uv run python -m pytest tests/version_test.py`
- Run one test: `uv run python -m pytest tests/version_test.py::test_version_matches_package_metadata -v`
- Coverage (as CI does): `uv run python -m pytest --cov=mideacloud --cov-report xml ./tests/`
- Lint/format/type-check all at once via `prek run --all-files`. Individually:
  `uv run ruff check .`, `uv run ruff format .`, `uv run mypy mideacloud`.

`ruff` uses `lint.select = ["ALL"]` with curated ignores in `ruff.toml`; `mypy` runs in
strict mode (`[tool.mypy]` in `pyproject.toml`). Fix all reported issues before committing — CI runs the full
prek suite in a dedicated lint job and blocks merge on failure.

## Conventions specific to this codebase

- **No magic numbers**: name protocol values as module-level constants. ruff's `PLR2004`
  enforces it outside `tests/`.
- **Tests** mirror the source tree under `tests/`, suffixed `_test.py`
  (e.g. `tests/version_test.py`). `tests/*` has relaxed ruff/mypy rules (asserts, private
  access, etc.).
- **Commits** must follow Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`,
  `refactor:`, `test:`); commitlint/commitizen enforce this and CI validates PR messages.
  Do not commit directly to `main` (prek `no-commit-to-branch`).
- **Small PRs** are recommended. Keep each PR focused and concise; large pull requests are unlikely to be merged.
- Recommended dev environment is **uv + a local `.venv`** (`./scripts/setup.sh` or
  `scripts\setup.ps1`); see `.github/CONTRIBUTING.md`.
