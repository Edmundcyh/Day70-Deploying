import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# main.py reads its configuration when it is imported, so set it up first.
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["CONTACT_EMAIL"] = "hello@example.com"

import main  # noqa: E402


@pytest.fixture
def app():
    main.app.config["TESTING"] = True
    main.app.config["WTF_CSRF_ENABLED"] = False
    with main.app.app_context():
        main.db.drop_all()
        main.db.create_all()
        yield main.app
        main.db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_post(app):
    def make_post():
        author = main.User(email="author@example.com", name="Author", password="unused")
        post = main.BlogPost(
            title="First post",
            subtitle="Hello",
            date="January 01, 2021",
            body="<p>Body</p>",
            img_url="https://example.com/image.jpg",
            author=author,
        )
        main.db.session.add(post)
        main.db.session.commit()
        return post.id
    return make_post


@pytest.fixture
def post_id(make_post):
    return make_post()
