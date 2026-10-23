# Workflow

## Working conventions

- Every issue must have one owner, a goal/scope, acceptance criteria, and dependencies.
- Work through branches and pull requests; review before merging.
- Use one Project board across sprints with these statuses: `Backlog`, `Todo`, `In Progress`, `Blocked`, `In Review`, and `Done`.
- Do not hardcode assignees, milestones, or labels before they exist.
- Repository-facing content, including documentation, templates, code comments, and UI text, must be written in English.

## Definition of Done

A task is complete only when its scope and acceptance criteria are met, appropriate checks have run, and evidence of the results exists (for example, logs, interface screenshots, command output, or test notes). Related documentation or instructions must be updated when needed.

## Data safety

Do not commit credentials, real Wi-Fi settings, tokens, runtime data, or audio recordings. Use approved example configurations and keep secrets outside Git.

## Tracking

Issues and pull requests must state dependencies or blockers. Scope changes are recorded in sprint documentation and confirmed by the team before implementation.

## Automated checks and AI-assisted review

### Baseline CI

The `CI` workflow runs on pull requests targeting `main` and pushes to
`main`. Its `Repository checks` job performs:

- GitHub Actions workflow validation with actionlint 1.7.12.
- Whitespace checks over the pull request changes or the pushed commit range.
- Telemetry schema and shared-fixture validation with `jsonschema[format]==4.26.0` and `tzdata==2026.5`.

The workflow pins the checkout action to a full commit SHA and verifies
the downloaded actionlint archive with SHA-256. No project secrets or
physical hardware are required.

A green baseline does not mean the application has been built, tested,
or verified on hardware.

The `Simulator and firmware` job additionally installs
`scripts/requirements-dev.txt` and the project backend. It lints producer tools,
tests the simulator and persistence verifier against local test services, and
runs host C++ feature/serializer/acknowledgement tests. It compiles both
`esp32dev_example` and the active `esp32dev_sampling_compile` path using sanitized
configuration, then exercises all simulator scenarios and C++-generated payloads
against the actual FastAPI application with temporary SQLite storage. See
`scripts/README.md`, `firmware/README.md`, and
[producer acceptance](producer-acceptance.md) for matching commands and evidence.
These checks establish software compatibility; the installed board, microphone,
and sampling during actual network faults still require physical validation.

### Local checks

Install Git and actionlint 1.7.12 from its official release:

https://github.com/rhysd/actionlint/releases/tag/v1.7.12

Keep downloaded tools outside the repository. Use `actionlint` on PATH,
or invoke the downloaded executable by its full path.

Run from the repository root:

```shell
actionlint -shellcheck= -pyflakes=
python -m pip install "jsonschema[format]==4.26.0" "tzdata==2026.5"
python scripts/validate_schema.py
git diff --check
git diff --cached --check
```

The first command validates workflow files. The Git commands check
unstaged and staged changes respectively. Untracked files are not
included in these Git diffs; inspect them and check the staged diff
before committing.

After committing, check the branch changes against the fetched main:

```shell
git diff --check origin/main...HEAD
```

ShellCheck and Pyflakes integrations are intentionally disabled in this
baseline so local and CI checks have the same external-tool requirements.

Before accepting a CI change, verify a valid case and an intentionally
invalid local case. Remove or restore all test probes before committing.
Record actual commands, results, and workflow-run links in the PR.

### Extending CI

Add the appropriate checks in the same PR that introduces a component:

- Shared schemas and fixtures: validate accepted and rejected examples.
- Backend and simulator: Python linting and meaningful automated tests.
- Dashboard: lockfile-based installation, linting, type checking, build,
  and appropriate tests.
- Firmware: PlatformIO compilation for the confirmed board, plus tests
  for logic that can run without hardware.

Do not add placeholder success jobs or silently skip missing configuration
for an integrated component. Document the exact local commands when each
component is introduced.

### Review process

Copilot instructions guide reviews; they do not enable automatic reviews.
Request Copilot manually when access is available, and record limitations
if a review cannot be performed.

Self-review the diff and check CI before requesting another team member's
review. AI feedback does not replace human review.

Move the issue to `In Review` when the PR is ready. Move it to `Done` only
after acceptance criteria, validation, documentation, human review, and
integration into `main` are complete.
