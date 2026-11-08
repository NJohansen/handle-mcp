# 0008: Install the latest release

The install commands in README and docs say `uvx handle-mcp@latest`, not a fixed version.

## Why

- With a pin, every user stays on the version they installed. Store fixes (a changed API, a new queue page) never reach them unless they edit their config by hand.
- uvx checks PyPI at each start with `@latest` and runs the newest release.
- A push to `main` still never reaches anyone. Only a tag on `main` makes a release, and the `pypi` environment needs the maintainer's approval before PyPI gets it (Trusted Publishing, no upload token).

## Cost

- A bad release reaches everyone at their next start. The fix is a new patch release, which reaches them the same way.
- A stolen maintainer GitHub account could push a tag and approve the deploy. A pin would not save users who update anyway; 2FA on GitHub and PyPI is the guard. There is no PyPI upload token to steal.
- Users who want to choose when to update pin a version themselves, e.g. `handle-mcp@1.5.2`. `docs/security.md` says how.

`tests/test_registry.py` fails if an install command in README or `docs/` uses anything but `@latest`.
