# Day 70 – Deploying a Flask blog

A Flask blog with user accounts, comments and an admin who writes the posts. It runs on SQLite locally and on Postgres when deployed.

## Configuration

The app reads its settings from environment variables:

| Variable | Required | What it does |
| --- | --- | --- |
| `SECRET_KEY` | Yes | Signs login sessions and form tokens. Use a long random value, for example from `python -c "import secrets; print(secrets.token_hex(32))"`. The app won't start without it. |
| `ADMIN_EMAIL` | To manage posts | The account with exactly this email can create, edit and delete posts. If it's unset, nobody can. The register page refuses this email, so create the account with `flask create-admin` (below). |
| `DATABASE_URL` | No | Database connection string. Defaults to a local SQLite file, `blog.db`. |
| `CONTACT_EMAIL` | No | Shown as an email link on the Contact page. |

## Running locally

```bash
pip install -r requirements.txt
export SECRET_KEY=dev-only-secret ADMIN_EMAIL=you@example.com
FLASK_APP=main flask create-admin
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

## Creating the admin account

The register page won't accept `ADMIN_EMAIL`, so nobody else can sign up with it before you do. Create the account from a shell where the app's environment variables are set. On your host that's a one-off shell, for example `heroku run bash`:

```bash
FLASK_APP=main flask create-admin
```

It asks for a display name and a password. If an account with `ADMIN_EMAIL` already exists, for example one you registered before this change, you don't need to do anything.
