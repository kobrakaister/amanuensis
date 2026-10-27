# AGENTS.md

Entry point for AI agents working in this repository. Read this file first.

## Read before writing code

- [Onboarding](docs/codebase-knowledge/ONBOARDING.md): stack, layout, prerequisites, quick start
- [Architecture](docs/codebase-knowledge/ARCHITECTURE.md)
- [Conventions](docs/codebase-knowledge/CONVENTIONS.md)

## Read when relevant

- [Patterns](docs/codebase-knowledge/PATTERNS.md): before adding a feature
- [Gotchas](docs/codebase-knowledge/GOTCHAS.md): before changing existing code
- [Integrations](docs/codebase-knowledge/INTEGRATIONS.md): before touching external services or
  environment variables
- [Open work](docs/workstreams.md): at the start of a non-trivial task

## Process

- Specs and changes live in `openspec/`. Start a change with `/opsx-propose` and implement it with
  `/opsx-apply`.
- `/kit-doctor` checks that this repository still matches what the kit expects.
- `/kit-extend` adds a rule, procedure or guard for one area of this repository.

## Project instructions

Instructions for the whole repository go here. Instructions for one folder go in an `AGENTS.md`
inside that folder.
