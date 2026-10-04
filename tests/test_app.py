import os
import re
import subprocess
import sys

import itsdangerous.timed
import pytest

import main

ADMIN = {"email": "admin@example.com", "password": "admin-password", "name": "Admin"}
READER = {"email": "reader@example.com", "password": "reader-password", "name": "Reader"}
POST = {"title": "A title", "subtitle": "Sub", "img_url": "https://example.com/image.jpg", "body": "<p>Body</p>"}

UNSAFE_COMMENT = (
    "<p onclick=\"alert(1)\">Nice <strong>post</strong></p>"
    "<script>alert(document.cookie)</script>"
    "<img src=\"/delete/1\">"
    "<a href=\"javascript:alert(1)\">bad link</a>"
    "<a href=\"https://example.com\">good link</a>"
)


def register(client, user):
    return client.post("/register", data=user)


def create_admin(app, password=ADMIN["password"]):
    return app.test_cli_runner().invoke(
        args=["create-admin", "--name", ADMIN["name"]], input=f"{password}\n{password}\n"
    )


def log_in_as_admin(app, client):
    assert create_admin(app).exit_code == 0
    client.post("/login", data={"email": ADMIN["email"], "password": ADMIN["password"]})


def post_count():
    return main.BlogPost.query.count()


# --- Startup configuration ---

def import_main_in_subprocess(code, **env_changes):
    env = dict(os.environ, DATABASE_URL="sqlite://")
    for key, value in env_changes.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-c", f"import main; {code}"],
        cwd=os.path.dirname(main.__file__),
        env=env,
        capture_output=True,
        text=True,
    )


def test_missing_secret_key_stops_startup():
    result = import_main_in_subprocess("", SECRET_KEY=None)
    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def test_blank_admin_email_means_no_admin_and_logs_a_warning():
    result = import_main_in_subprocess("print(main.ADMIN_EMAIL)", ADMIN_EMAIL="   ")
    assert result.returncode == 0
    assert result.stdout.strip() == "None"
    assert "ADMIN_EMAIL is not set" in result.stderr


# --- Who counts as admin ---

def test_logged_out_visitors_get_403_on_admin_pages(client, post_id):
    assert client.get("/new-post").status_code == 403
    assert client.get(f"/edit-post/{post_id}").status_code == 403
    assert client.post(f"/delete/{post_id}").status_code == 403
    assert post_count() == 1


def test_first_registered_user_is_not_admin(client):
    register(client, READER)
    assert main.User.query.filter_by(email=READER["email"]).one().id == 1
    assert client.get("/new-post").status_code == 403


def test_create_admin_command_creates_the_admin(app, client):
    result = create_admin(app)
    assert result.exit_code == 0
    assert "Created the admin account for admin@example.com." in result.output
    admin = main.User.query.filter_by(email=ADMIN["email"]).one()
    assert admin.name == ADMIN["name"]
    assert admin.password.startswith("pbkdf2:sha256:")
    client.post("/login", data={"email": ADMIN["email"], "password": ADMIN["password"]})
    assert client.get("/new-post").status_code == 200


def test_register_page_refuses_the_admin_email(client):
    response = register(client, ADMIN)
    assert response.status_code == 200
    assert "That email can&#39;t be used to register." in response.get_data(as_text=True)
    assert main.User.query.count() == 0
    assert client.get("/new-post").status_code == 403


@pytest.mark.parametrize("field", ["email", "name"])
def test_overlong_register_fields_are_rejected(client, field):
    # The columns are 100 characters; Postgres would reject a longer value with a 500.
    response = register(client, dict(READER, **{field: "a" * 101}))
    assert response.status_code == 200
    assert "Field cannot be longer than 100 characters." in response.get_data(as_text=True)
    assert main.User.query.count() == 0


def test_create_admin_command_refuses_existing_account(app):
    assert create_admin(app).exit_code == 0
    result = create_admin(app, password="another-password")
    assert result.exit_code != 0
    assert "already exists" in result.output
    assert main.User.query.count() == 1


def test_create_admin_command_needs_admin_email(app, monkeypatch):
    monkeypatch.setattr(main, "ADMIN_EMAIL", None)
    result = create_admin(app)
    assert result.exit_code != 0
    assert "Set the ADMIN_EMAIL environment variable first." in result.output
    assert main.User.query.count() == 0


def test_admin_email_must_match_exactly(client):
    register(client, dict(ADMIN, email="ADMIN@example.com"))
    assert client.get("/new-post").status_code == 403


def test_nobody_is_admin_when_admin_email_is_unset(client, monkeypatch):
    monkeypatch.setattr(main, "ADMIN_EMAIL", None)
    register(client, ADMIN)
    assert client.get("/new-post").status_code == 403


def test_admin_controls_hidden_from_user_1_when_not_admin(client, make_post):
    # User id 1 was the hard-coded admin before ADMIN_EMAIL.
    register(client, READER)
    assert main.User.query.filter_by(email=READER["email"]).one().id == 1
    post_id = make_post()
    home = client.get("/").get_data(as_text=True)
    assert "Create New Post" not in home
    assert "Delete post" not in home
    assert f"/edit-post/{post_id}" not in client.get(f"/post/{post_id}").get_data(as_text=True)


def test_admin_sees_admin_controls(app, client, post_id):
    log_in_as_admin(app, client)
    home = client.get("/").get_data(as_text=True)
    assert "Create New Post" in home
    assert "Delete post" in home
    assert f"/edit-post/{post_id}" in client.get(f"/post/{post_id}").get_data(as_text=True)


# --- Missing posts ---

def test_missing_post_returns_404(client):
    assert client.get("/post/999").status_code == 404


def test_admin_gets_404_for_missing_post(app, client):
    log_in_as_admin(app, client)
    assert client.get("/edit-post/999").status_code == 404
    assert client.post("/delete/999").status_code == 404


# --- Creating and editing posts ---

def test_duplicate_title_gets_a_form_error(app, client):
    log_in_as_admin(app, client)
    assert client.post("/new-post", data=POST).status_code == 302
    response = client.post("/new-post", data=POST)
    assert response.status_code == 200
    assert "A post with that title already exists." in response.get_data(as_text=True)
    assert post_count() == 1


def test_editing_to_an_existing_title_gets_a_form_error(app, client, post_id):
    log_in_as_admin(app, client)
    assert client.post("/new-post", data=POST).status_code == 302
    response = client.post(f"/edit-post/{post_id}", data=POST)
    assert response.status_code == 200
    assert "A post with that title already exists." in response.get_data(as_text=True)
    assert main.BlogPost.query.get(post_id).title == "First post"


def test_editing_a_post_can_keep_its_own_title(app, client, post_id):
    log_in_as_admin(app, client)
    response = client.post(f"/edit-post/{post_id}", data=dict(POST, title="First post", subtitle="Changed"))
    assert response.status_code == 302
    assert main.BlogPost.query.get(post_id).subtitle == "Changed"


@pytest.mark.parametrize("field", ["title", "subtitle", "img_url"])
def test_overlong_post_fields_are_rejected(app, client, field):
    # The columns are 250 characters; Postgres would reject a longer value with a 500.
    log_in_as_admin(app, client)
    value = "https://example.com/" + "a" * 250 if field == "img_url" else "a" * 251
    response = client.post("/new-post", data=dict(POST, **{field: value}))
    assert response.status_code == 200
    assert "Field cannot be longer than 250 characters." in response.get_data(as_text=True)
    assert post_count() == 0


def test_home_page_shows_newest_post_first(app, client, post_id):
    log_in_as_admin(app, client)
    assert client.post("/new-post", data=dict(POST, title="Second post")).status_code == 302
    home = client.get("/").get_data(as_text=True)
    assert home.index("Second post") < home.index("First post")


# --- Deleting posts ---

def test_delete_does_not_accept_get(app, client, post_id):
    log_in_as_admin(app, client)
    assert client.get(f"/delete/{post_id}").status_code == 405
    assert post_count() == 1


def test_delete_without_csrf_token_is_rejected(app, client, post_id):
    log_in_as_admin(app, client)
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post(f"/delete/{post_id}").status_code == 400
    assert post_count() == 1


def test_admin_can_delete_with_button_on_home_page(app, client, post_id):
    log_in_as_admin(app, client)
    app.config["WTF_CSRF_ENABLED"] = True
    page = client.get("/").get_data(as_text=True)
    assert f'<button type="submit" form="delete-post-{post_id}"' in page
    form = re.search(rf'<form id="delete-post-{post_id}" action="([^"]+)" method="post".*?name="csrf_token" value="([^"]+)"', page, re.S)
    assert form.group(1) == f"/delete/{post_id}"
    response = client.post(form.group(1), data={"csrf_token": form.group(2)})
    assert response.status_code == 302
    assert post_count() == 0


def test_form_left_open_for_hours_still_submits(app, client, post_id, monkeypatch):
    log_in_as_admin(app, client)
    app.config["WTF_CSRF_ENABLED"] = True
    token = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/").get_data(as_text=True)).group(1)
    opened_at = itsdangerous.timed.time.time()
    monkeypatch.setattr(itsdangerous.timed.time, "time", lambda: opened_at + 3 * 60 * 60)
    assert client.post(f"/delete/{post_id}", data={"csrf_token": token}).status_code == 302
    assert post_count() == 0


def test_deleting_a_post_deletes_its_comments(app, client, post_id):
    log_in_as_admin(app, client)
    client.post(f"/post/{post_id}", data={"comment_text": "<p>Hi</p>"})
    assert main.Comment.query.count() == 1
    assert client.post(f"/delete/{post_id}").status_code == 302
    assert main.Comment.query.count() == 0


# --- Comments ---

def test_comment_html_is_sanitized_when_saved(client, post_id):
    register(client, READER)
    response = client.post(f"/post/{post_id}", data={"comment_text": UNSAFE_COMMENT})
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/post/{post_id}")
    saved = main.Comment.query.one().text
    assert "<strong>post</strong>" in saved
    assert '<a href="https://example.com" rel="noopener noreferrer">good link</a>' in saved
    for unsafe in ("<script", "onclick", "<img", "javascript:"):
        assert unsafe not in saved


@pytest.mark.parametrize("comment", [
    "<script>alert(1)</script>",
    # What CKEditor sends for an image-only, script-only or blank comment.
    '<p><img src="https://example.com/x.png"></p>\n',
    "<p><script>alert(1)</script></p>\n",
    "<p>&nbsp;</p>\n",
    "<p><br></p>\n",
])
def test_comment_with_no_text_left_after_sanitizing_is_not_saved(client, post_id, comment):
    register(client, READER)
    response = client.post(f"/post/{post_id}", data={"comment_text": comment})
    assert response.status_code == 200
    assert "Your comment needs some text." in response.get_data(as_text=True)
    assert main.Comment.query.count() == 0


def test_overlong_comment_is_rejected_before_sanitizing(client, post_id):
    register(client, READER)
    response = client.post(f"/post/{post_id}", data={"comment_text": "<ul><li>" * 2000})
    assert response.status_code == 200
    assert "Field cannot be longer than 10000 characters." in response.get_data(as_text=True)
    assert main.Comment.query.count() == 0


def test_comment_editor_formatting_is_kept():
    comment = (
        "<p><del>old</del> <ins>new</ins> <q>quote</q> <kbd>Ctrl</kbd></p>"
        '<table border="1" cellpadding="1" cellspacing="1"><caption>Scores</caption>'
        '<thead><tr><th scope="col">Name</th></tr></thead><tbody><tr><td>Ann</td></tr></tbody></table>'
    )
    assert main.clean_comment_html(comment) == comment


def test_comments_saved_before_the_fix_are_sanitized_when_shown(client, post_id):
    reader = main.User(email=READER["email"], name=READER["name"], password="unused")
    main.db.session.add(main.Comment(text=UNSAFE_COMMENT, comment_author=reader, post_id=post_id))
    main.db.session.commit()
    page = client.get(f"/post/{post_id}").get_data(as_text=True)
    assert "<strong>post</strong>" in page
    for unsafe in ("alert(document.cookie)", "onclick", 'src="/delete/1"', "javascript:"):
        assert unsafe not in page


def test_logged_out_visitor_cannot_comment(client, post_id):
    response = client.post(f"/post/{post_id}", data={"comment_text": "<p>Hi</p>"})
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert main.Comment.query.count() == 0


def test_comment_avatars_use_https(client, post_id):
    register(client, READER)
    client.post(f"/post/{post_id}", data={"comment_text": "<p>Hi</p>"})
    page = client.get(f"/post/{post_id}").get_data(as_text=True)
    assert "https://secure.gravatar.com/avatar/" in page
    assert "http://www.gravatar.com" not in page


def test_comments_show_in_posting_order(client, post_id):
    register(client, READER)
    for text in ("first", "second", "third"):
        client.post(f"/post/{post_id}", data={"comment_text": f"<p>{text}</p>"})
    page = client.get(f"/post/{post_id}").get_data(as_text=True)
    assert page.index("<p>first</p>") < page.index("<p>second</p>") < page.index("<p>third</p>")


def test_logged_out_visitor_sees_login_link_instead_of_comment_editor(client, post_id):
    page = client.get(f"/post/{post_id}").get_data(as_text=True)
    assert 'name="comment_text"' not in page
    assert "ckeditor" not in page
    assert "to leave a comment" in page
    assert 'href="/login"' in page


def test_logged_in_user_sees_comment_editor(client, post_id):
    register(client, READER)
    page = client.get(f"/post/{post_id}").get_data(as_text=True)
    assert 'name="comment_text"' in page
    assert "to leave a comment" not in page


# --- Contact page ---

def test_contact_page_shows_configured_email(client):
    page = client.get("/contact").get_data(as_text=True)
    assert 'href="mailto:hello@example.com"' in page
    assert "<form" not in page


def test_contact_page_without_email(client, monkeypatch):
    monkeypatch.setattr(main, "CONTACT_EMAIL", None)
    page = client.get("/contact").get_data(as_text=True)
    assert "mailto:" not in page
