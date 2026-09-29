import pytest

from wordgame import create_app, rules
from wordgame.db import get_db

PASSWORD = "Play$123"


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "DATABASE": str(tmp_path / "test.sqlite"),
        "CSRF_ENABLED": False,
        "ADMIN_USERNAME": "Admin",
        "ADMIN_PASSWORD": "Admin$123",
    })
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def day(monkeypatch):
    """Pin 'today' so date-based rules are deterministic."""
    state = {"value": "2026-09-29"}
    monkeypatch.setattr(rules, "today", lambda: state["value"])
    return state


def register(client, username="Player", password=PASSWORD):
    return client.post("/register", data={"username": username, "password": password})


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def logout(client):
    return client.post("/logout")


def start_game(client):
    resp = client.post("/play/new")
    assert resp.status_code == 302
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def answer_for(app, game_id):
    with app.app_context():
        return get_db().execute(
            "SELECT words.word FROM games JOIN words ON words.id = games.word_id WHERE games.id = ?",
            (game_id,),
        ).fetchone()[0]


def guess(client, game_id, word):
    return client.post(f"/api/games/{game_id}/guesses", json={"guess": word})


def wrong_word(answer):
    """A valid 5-letter guess guaranteed not to be the answer."""
    return "QQQQQ" if answer != "QQQQQ" else "ZZZZZ"
