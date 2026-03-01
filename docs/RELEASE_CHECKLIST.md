# Release Checklist

Run through this checklist before every tagged release.

## Pre-Release Gates

- [ ] `./scripts/verify.sh` — full local verification (sanitation + lint + unit + E2E)
- [ ] `./scripts/verify.sh --ci` — CI-mode verification (no Docker)
- [ ] All unit tests pass (`pytest tests/ -v`)
- [ ] Ruff lint clean (`ruff check .`)
- [ ] E2E contract: all 3 cases PASS (requires Docker + Neo4j)
- [ ] CI green on latest commit (check GitHub Actions)
- [ ] No secrets in `.env.example`, `docs/`, `src/`, or `scripts/`
- [ ] `CHANGELOG.md` updated with release notes
- [ ] `docs/HYBRID_CONTRACT.md` still accurate

## Release

- [ ] Tag: `git tag -a v<VERSION> -m "Release v<VERSION>"`
- [ ] Push tag: `git push origin v<VERSION>`
- [ ] Verify CI passes on tagged commit

## Verification Matrix

| Gate | CI (`--ci`) | Local (full) | Required for Release |
|------|:-----------:|:------------:|:--------------------:|
| Secrets sanitation | ✅ | ✅ | Yes |
| Lint (ruff) | ✅ | ✅ | Yes |
| Unit tests (pytest) | ✅ | ✅ | Yes |
| E2E hybrid contract | ⏭ skipped | ✅ | Yes (local) |
| Playwright | ⏭ skipped | Optional | No |

> **Note:** CI validates sanitation, lint, and unit tests on every push.
> Full E2E is required locally before release and enforced by `./scripts/verify.sh` (without `--ci`).
