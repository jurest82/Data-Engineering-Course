# Contributing

Thanks for considering a contribution to this project!

## Getting started

See [README.md](README.md#setup) for how to get each subproject's devcontainer
running (`backend`, `infrastructure`, `frontend`). All formatting, linting and
tests run **inside that container**, not on your host machine.

## Before opening a pull request

Each check below also runs automatically in CI on every push/PR (see the
badges at the top of the README), but running them locally first saves you a
red build:

- **`backend`**, inside its devcontainer:
  - `npm run format:check` (Prettier for everything, `yapf` for Python)
  - `pylint src/ database/ tests/ --rcfile=pyproject.toml`
  - `pytest` (runs against local MongoDB/PostgreSQL containers, no real AWS
    or cloud credentials needed)
- **`infrastructure`** / **`frontend`**, inside their own devcontainer:
  - `npm run format:check` (Prettier)

If a formatting check fails, `npm run format` (instead of `format:check`)
rewrites the files in place.

## Commit messages

Based on [Conventional Commits](https://www.conventionalcommits.org/):
each line is its own bullet, `* <type>: <description>` (types like
`feat`/`fix`/`refactor`/`chore`/`docs`/`test`), imperative mood, no trailing
period. One bullet per distinct change, even within the same commit:

```text
* feat: add ValidateAndStore Lambda behind a REST API with an API key
* docs: update backend README deployment section for the single-stack layout
```

If your changes are very different in nature, prefer several smaller commits
over one commit with many unrelated bullets.

## Code of Conduct

This project follows a [Code of Conduct](CODE_OF_CONDUCT.md). By
participating, you're expected to uphold it.
