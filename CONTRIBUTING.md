# Contributing to Moltbook Observatory

Thanks for contributing.

This project is built around reproducibility and auditability, so contribution quality is measured by clarity, traceability, and deterministic behavior.

## Ground rules

- Use clear, reviewable commits.
- Keep methods interpretable and documented.
- Preserve existing data lineage assumptions unless intentionally changed.
- Never commit secrets, private credentials, or disallowed raw data.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install -e .
```

Optional (for UI coherence checks): Node.js 18+.

## Verify before opening a PR

Run all baseline checks:

```bash
PYTHON_BIN=python scripts/repro_check.sh
```

Or via `make`:

```bash
make verify
```

## Pull request checklist

Before requesting review, ensure:

- [ ] Scope is focused and explained.
- [ ] Tests pass locally.
- [ ] New scripts include usage docs.
- [ ] Any metric or schema change is documented in `reports/audit/` or `reports/analysis_schema.md`.
- [ ] Reproducibility assumptions are updated in `REPRODUCIBILITY.md` if needed.

## Branching and commits

- Branch from `main`.
- Use descriptive commit messages (imperative mood).
- Keep PRs small enough for full review.

Recommended commit style examples:

- `Add temporal contract audit for created_at vs run_time`
- `Fix ontology cooccurrence filter regression`
- `Document reproducibility steps for derived artifacts`

## Reporting bugs and requesting features

Use the issue templates:

- Bug report: include reproduction steps and expected vs observed behavior.
- Feature request: include motivation, use case, and evaluation criteria.

## Questions

Open a GitHub Discussion/Issue or contact the maintainer through channels listed in `README.md` and `site/about.html`.
