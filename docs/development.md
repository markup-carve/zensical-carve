# Development

## Setup and maintenance

```bash
pip install -e ".[dev]"
pytest -q
python tests/e2e_build.py
```

That install resolves the Carve engine the way a user's install does: anywhere in
the declared range, which today means whatever `carve-lang` PyPI serves as newest.
To reproduce what CI measured instead, install under the same constraints file CI
uses:

```bash
pip install -e ".[dev]" -c constraints-ci.txt
```

Only the engine is pinned there, and only for test runs: a pinned engine is what
makes a green run stay green and lets a run state which engine produced its
result. The declared dependency in `pyproject.toml` stays a range, because that
is what a consumer needs. The two move for different reasons and not together -
`constraints-ci.txt` says how, and `tests/test_engine_floor.py` is what reports
the case the floor was set for.

Pinning every run would mean no run ever meets a new engine release, so the
daily `Scheduled suite` workflow installs unconstrained. That is where engine
drift is noticed: a day after a release, rather than in whoever's pull request
happens to be next.
