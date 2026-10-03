# Day 70 – Deploying a Flask blog

A Flask blog with user accounts, comments and an admin who writes the posts. It runs on SQLite locally and on Postgres when deployed.

## Configuration

The app reads its settings from environment variables:

| Variable | Required | What it does |
| --- | --- | --- |
| `SECRET_KEY` | Yes | Signs login sessions and form tokens. Use a long random value, for example from `python -c "import secrets; print(secrets.token_hex(32))"`. The app won't start without it. |
| `ADMIN_EMAIL` | To manage posts | The account registered with exactly this email can create, edit and delete posts. If it's unset, nobody can. Register that account yourself straight after deploying. |
| `DATABASE_URL` | No | Database connection string. Defaults to a local SQLite file, `blog.db`. |
| `CONTACT_EMAIL` | No | Shown as an email link on the Contact page. |

## Running locally

```bash
pip install -r requirements.txt
export SECRET_KEY=dev-only-secret ADMIN_EMAIL=you@example.com
python main.py
```

The Python version is pinned in `.python-version`. `blog.db` is no longer kept in the repository. To get the old sample data back, run `git show 68bf92c:blog.db > blog.db`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Deploying

The `Procfile` starts the app with gunicorn. Set the variables above in your host's settings, and add a Postgres database so that `DATABASE_URL` is set.
