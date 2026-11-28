# git-skills

A skills marketplace for Git, merge-request, and code-writing workflows. Works with **Claude Code** (plugin marketplace) and **OpenCode** (skills folder), against **GitHub** (`gh`) and **GitLab** (`glab`).

## Skills

| Skill | What it does | Calls |
|-------|--------------|-------|
| `git-branch` | Creates `<type>/<ticket>-<slug>` from the latest base branch | — |
| `git-commit` | Commits with a Conventional Commits header built from parameters (`type`, `service`, `package`, `message`) | — |
| `mr-create` | Creates an MR/PR from a description file filled into the repo's template | `git-branch`, `git-commit` (title format) |
| `mr-comment-addresser` | Triages review threads, fixes valid items, replies, and resolves addressed threads | `mr-create` (forge), `git-commit`, `test-write` |
| `mr-babysit` | Watches the pipeline, fixes failures and warnings, pushes, repeats until green | `mr-create` (forge), `git-commit`, `test-write` |
| `test-write` | Writes unit, integration and other tests following the language reference, then runs them | `git-commit` (when asked) |
| `go-code` | Writes canonical Go: idiomatic naming, contract comments, wrapped errors, small interfaces, and table-driven tests | `test-write` (Go test mechanics) |
| `rust-code` | Writes safe Rust: exhaustive matching, explicit errors, clear naming, and tests in separate files | `test-write` (Rust test mechanics) |
| `mr-review` | Reviews a PR/MR: establishes intent from linked issues and description, then checks logic, performance, security, and repo and language conventions. Reports only; posts nothing | `mr-create` (provider data), `test-write` (language, optional tests) |

Every skill keeps its output short: state the issue, the action needed, or what was done.

Each skill documents only the commands it owns. When a skill needs another skill's command, it points to that skill's `SKILL.md` instead of repeating it.

## Requirements

- `python3` 3.9 or newer (standard library only)
- `git`
- `gh` authenticated (`gh auth login`) for GitHub repos
- `glab` authenticated (`glab auth login`) for GitLab repos

## Install

Install all nine skills together. Skills call each other through sibling paths (`../git-commit/scripts/commit.py`), so a partial install breaks the calls.

### Claude Code

```
/plugin marketplace add <your-github-user>/skills
/plugin install mr-workflow@git-skills
```

For a local checkout:

```
/plugin marketplace add <path-to-your-checkout>
/plugin install mr-workflow@git-skills
```

### OpenCode

OpenCode reads `~/.config/opencode/skills/`, `.opencode/skills/`, and also `~/.claude/skills/` and `.claude/skills/`.

```
scripts/install.sh --opencode                 # global for OpenCode
scripts/install.sh --claude                   # global, read by Claude Code and OpenCode
scripts/install.sh --dir ./.opencode/skills   # one project only
```

Restart OpenCode after installing.

## Script ownership

Each script has exactly one home. Other skills call it by sibling path.

| Script | Owner | Used by |
|--------|-------|---------|
| `git-branch/scripts/branch.py` | `git-branch` | user, `mr-create` |
| `git-commit/scripts/commit.py` | `git-commit` | `mr-comment-addresser`, `mr-babysit`, `test-write` |
| `mr-create/scripts/forge.py` | `mr-create` | `mr-comment-addresser`, `mr-babysit` |
| `test-write/scripts/test_runner.py` | `test-write` | `mr-comment-addresser`, `mr-babysit`, `mr-review` |
| `mr-review/scripts/review_tools.py` | `mr-review` | user |

## Input validation and exit codes

Every script validates its parameters before doing anything, and reports all problems at once.

| Exit code | Meaning | What the agent does |
|-----------|---------|---------------------|
| `0` | success | continue |
| `2` | invalid input; output has `problems` | fix the listed parameters and rerun |
| `1` | git, provider, or runner failure | report the message |

Key limits:

| Input | Limit |
|-------|-------|
| commit `--message` | 50 chars, lowercase start, no trailing period |
| commit header (`type(service/package): message`) | 72 chars |
| commit `--service` / `--package` | lowercase slug, max 20 chars each |
| branch `--summary` | 80 chars (slug capped at 50) |
| MR `--title` | 72 chars, one line |
| MR `--body-file` | 60,000 chars |
| review reply `--body-file` | 1,000 chars |
| test `--timeout` | 1 to 3600 seconds |
| `--target`, `--add` paths | relative, inside the repo, no `..` |

## Repository layout

```
skills/
├── .claude-plugin/marketplace.json            # Claude Code marketplace manifest
├── .githooks/pre-commit                       # native Git hook (core.hooksPath)
├── .pre-commit-config.yaml                    # pre-commit framework config
├── .github/workflows/tests.yml                # CI: pipeline on push and pull request
├── plugins/mr-workflow/
│   ├── .claude-plugin/plugin.json             # Claude Code plugin manifest
│   └── skills/
│       ├── git-branch/            SKILL.md, references/conventions.md, scripts/branch.py
│       ├── git-commit/            SKILL.md, references/conventions.md, scripts/commit.py
│       ├── mr-create/             SKILL.md, references/{github,gitlab,description-guide}.md, scripts/forge.py
│       ├── mr-comment-addresser/  SKILL.md, references/{github,gitlab,triage}.md
│       ├── mr-babysit/            SKILL.md, references/{github,gitlab,failure-triage}.md
│       ├── mr-review/             SKILL.md, references/{intent,review-areas,github,gitlab,rust,go}.md, scripts/review_tools.py
│       ├── test-write/            SKILL.md, references/{test-types,rust,go}.md, scripts/test_runner.py
│       ├── go-code/               SKILL.md, references/conventions.md
│       ├── rust-code/             SKILL.md, references/conventions.md
├── scripts/                                   # pipeline_check.py, verify_hook.sh, install_hooks.sh, audit.py, install.sh
├── tests/                                     # unit and integration tests
└── README.md
```

## How skills load references

Skills read only the file for the option in use:

| Skill | Option | File read |
|-------|--------|-----------|
| `mr-create`, `mr-comment-addresser`, `mr-babysit` | `provider` from `forge.py context` | `references/github.md` **or** `references/gitlab.md` |
| `test-write` | `language` from `test_runner.py detect` | `references/rust.md` **or** `references/go.md` |
| `test-write` | always | `references/test-types.md` |
| `go-code`, `rust-code` | always | `references/conventions.md` |

Reference rules:

- Pointers are relative to the skill folder (`references/<file>.md`) or to a sibling skill (`../<skill>/SKILL.md`). Never point outside the plugin.
- Each option has its own file. A SKILL.md never names two option files for the same choice.

## Development

### Tests and hooks

The pipeline compiles every script, then runs the full suite in `tests/`:

```
python3 scripts/pipeline_check.py
```

A commit that stages a Python file runs the pipeline; a commit that only changes
docs, README or `SKILL.md` skips it. A failing pipeline rejects the commit.

Two canonical hook setups are supported. Use one per clone:

```
scripts/install_hooks.sh     # native Git hook via core.hooksPath=.githooks
pre-commit install           # pre-commit framework via .pre-commit-config.yaml
```

Prove the native hook end to end (pass, skip and block cases):

```
bash scripts/verify_hook.sh
```

Audit the repository for secrets, personal paths, hook setup and pipeline health:

```
python3 scripts/audit.py
```

Keep sibling paths valid: if you rename a skill folder, update every `../<name>/` pointer.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `FORGE_PROVIDER` | detected from remote | force `github` or `gitlab` (self-hosted hosts) |
| `GH_HOST` / `GITLAB_HOST` | set from the remote | host for `gh` / `glab` |

## License

MIT
