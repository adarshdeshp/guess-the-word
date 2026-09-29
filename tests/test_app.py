from wordgame.db import get_db

from .conftest import (
    PASSWORD, answer_for, guess, login, logout, register, start_game, wrong_word,
)


# ---------- setup ----------

def test_starter_data_is_seeded(app):
    with app.app_context():
        db = get_db()
        words = [r[0] for r in db.execute("SELECT word FROM words")]
        assert len(words) == 20
        assert all(len(w) == 5 and w.isupper() for w in words)
        assert db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0] == 1


def test_restart_does_not_duplicate_seed_data(app):
    from wordgame.db import init_db
    with app.app_context():
        init_db()
        init_db()
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 20
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


# ---------- registration and login ----------

def test_register_creates_player_and_logs_in(client, app):
    resp = register(client, "Adarsh")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/play")
    with app.app_context():
        role = get_db().execute("SELECT role FROM users WHERE username = 'Adarsh'").fetchone()[0]
    assert role == "player"


def test_register_rejects_bad_username_and_password(client):
    assert register(client, "adarsh").status_code == 400            # no upper case
    assert register(client, "Adar").status_code == 400              # too short
    assert register(client, "Adarsh", "abcde").status_code == 400   # weak password


def test_register_rejects_duplicate_username_case_insensitive(client):
    register(client, "Adarsh")
    logout(client)
    resp = register(client, "ADARsh")
    assert resp.status_code == 400
    assert b"is taken" in resp.data


def test_password_is_hashed(client, app):
    register(client, "Adarsh")
    with app.app_context():
        stored = get_db().execute("SELECT password_hash FROM users WHERE username = 'Adarsh'").fetchone()[0]
    assert stored != PASSWORD and PASSWORD not in stored


def test_login_success_and_failure(client):
    register(client, "Adarsh")
    logout(client)
    assert login(client, "Adarsh", "Wrong$123").status_code == 401
    resp = login(client, "Adarsh", PASSWORD)
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/play")


def test_login_ignores_external_next(client):
    register(client, "Adarsh")
    logout(client)
    resp = client.post("/login?next=https://evil.example", data={"username": "Adarsh", "password": PASSWORD})
    assert resp.headers["Location"].endswith("/play")


def test_admin_login_goes_to_reports(client):
    resp = login(client, "Admin", "Admin$123")
    assert resp.headers["Location"].endswith("/admin/")


# ---------- access control ----------

def test_pages_require_login(client):
    for path in ("/play", "/admin/", "/admin/players", "/admin/words"):
        resp = client.get(path)
        assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_player_cannot_open_admin(client):
    register(client, "Adarsh")
    assert client.get("/admin/").status_code == 403
    assert client.get("/admin/words").status_code == 403


def test_admin_cannot_play(client):
    login(client, "Admin", "Admin$123")
    assert client.get("/play").status_code == 403


def test_player_cannot_touch_another_players_game(client, day):
    register(client, "Alpha")
    game_id = start_game(client)
    logout(client)
    register(client, "Bravo")
    assert client.get(f"/play/{game_id}").status_code == 404
    assert guess(client, game_id, "TOWER").status_code == 404


# ---------- playing ----------

def test_win_on_first_guess(client, app, day):
    register(client, "Adarsh")
    game_id = start_game(client)
    answer = answer_for(app, game_id)

    data = guess(client, game_id, answer).get_json()
    assert data["status"] == "won"
    assert data["result"] == ["correct"] * 5
    assert data["answer"] == answer

    # A finished game refuses more guesses.
    assert guess(client, game_id, answer).status_code == 409


def test_lose_after_five_wrong_guesses(client, app, day):
    register(client, "Adarsh")
    game_id = start_game(client)
    miss = wrong_word(answer_for(app, game_id))

    for n in range(1, 5):
        data = guess(client, game_id, miss).get_json()
        assert data["status"] == "in_progress"
        assert data["remaining"] == 5 - n
        assert data["answer"] is None          # answer stays hidden mid-game

    data = guess(client, game_id, miss).get_json()
    assert data["status"] == "lost"
    assert data["answer"] == answer_for(app, game_id)
    assert guess(client, game_id, miss).status_code == 409


def test_win_on_last_guess_counts_as_win(client, app, day):
    register(client, "Adarsh")
    game_id = start_game(client)
    answer = answer_for(app, game_id)
    for _ in range(4):
        guess(client, game_id, wrong_word(answer))
    assert guess(client, game_id, answer).get_json()["status"] == "won"


def test_guess_must_be_five_uppercase_letters(client, day):
    register(client, "Adarsh")
    game_id = start_game(client)
    for bad in ("tower", "Tower", "TOWE", "TOWERS", "TOW3R", "", None):
        assert guess(client, game_id, bad).status_code == 422
    # Rejected guesses don't use up a try.
    with client.application.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM guesses").fetchone()[0] == 0


def test_guesses_are_saved_in_order_with_date(client, app, day):
    register(client, "Adarsh")
    game_id = start_game(client)
    answer = answer_for(app, game_id)
    guess(client, game_id, "QQQQQ" if answer != "QQQQQ" else "ZZZZZ")
    guess(client, game_id, answer)

    with app.app_context():
        db = get_db()
        game = db.execute("SELECT played_on, status, finished_at FROM games WHERE id = ?", (game_id,)).fetchone()
        rows = db.execute(
            "SELECT attempt_no, guess, guessed_at FROM guesses WHERE game_id = ? ORDER BY attempt_no", (game_id,)
        ).fetchall()
    assert game["played_on"] == "2026-09-29"
    assert game["status"] == "won" and game["finished_at"]
    assert [r["attempt_no"] for r in rows] == [1, 2]
    assert rows[1]["guess"] == answer
    assert all(r["guessed_at"] for r in rows)


def test_board_page_shows_previous_guesses(client, app, day):
    register(client, "Adarsh")
    game_id = start_game(client)
    guess(client, game_id, wrong_word(answer_for(app, game_id)))
    page = client.get(f"/play/{game_id}").get_data(as_text=True)
    assert 'data-attempts="1"' in page
    assert "4 guesses left" in page


def test_answer_not_leaked_in_page_while_playing(client, app, day):
    register(client, "Adarsh")
    game_id = start_game(client)
    answer = answer_for(app, game_id)
    page = client.get(f"/play/{game_id}").get_data(as_text=True)
    assert answer not in page


def test_start_resumes_unfinished_word(client, day):
    register(client, "Adarsh")
    first = start_game(client)
    assert start_game(client) == first


# ---------- daily limit ----------

def _finish(client, app, game_id):
    guess(client, game_id, answer_for(app, game_id))


def test_three_words_per_day_limit(client, app, day):
    register(client, "Adarsh")
    for _ in range(3):
        _finish(client, app, start_game(client))

    resp = client.post("/play/new", follow_redirects=True)
    assert b"all 3 words for today" in resp.data
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM games").fetchone()[0] == 3

    # Next day, the player can play again.
    day["value"] = "2026-09-30"
    _finish(client, app, start_game(client))
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM games").fetchone()[0] == 4


def test_limit_is_per_player(client, app, day):
    register(client, "Alpha")
    for _ in range(3):
        _finish(client, app, start_game(client))
    logout(client)
    register(client, "Bravo")
    start_game(client)  # would raise if the limit leaked across players


def test_words_are_not_repeated_until_all_used(client, app, day):
    register(client, "Adarsh")
    seen = set()
    for n in range(7):
        day["value"] = f"2026-10-{n + 1:02d}"
        for _ in range(3):
            gid = start_game(client)
            seen.add(answer_for(app, gid))
            _finish(client, app, gid)
    assert len(seen) == 20   # 21 games, 20 words: every word appears before any repeats


# ---------- admin reports ----------

def _play_day(client, app, username, wins, losses):
    register(client, username)
    for _ in range(wins):
        _finish(client, app, start_game(client))
    for _ in range(losses):
        gid = start_game(client)
        for _ in range(5):
            guess(client, gid, wrong_word(answer_for(app, gid)))
    logout(client)


def test_daily_report_counts(client, app, day):
    _play_day(client, app, "Alpha", wins=2, losses=1)
    _play_day(client, app, "Bravo", wins=1, losses=0)
    day["value"] = "2026-09-30"
    login(client, "Alpha", PASSWORD)
    _finish(client, app, start_game(client))
    logout(client)

    login(client, "Admin", "Admin$123")
    page = client.get("/admin/?day=2026-09-29").get_data(as_text=True)
    assert "<strong>2</strong> players" in page
    assert "tried <strong>4</strong> words" in page
    assert "guessed <strong>3</strong> correctly" in page

    other = client.get("/admin/?day=2026-09-30").get_data(as_text=True)
    assert "<strong>1</strong> player" in other

    empty = client.get("/admin/?day=2026-01-01").get_data(as_text=True)
    assert "Nobody played on this day." in empty


def test_player_report_by_date(client, app, day):
    _play_day(client, app, "Alpha", wins=1, losses=1)
    day["value"] = "2026-09-30"
    login(client, "Alpha", PASSWORD)
    _finish(client, app, start_game(client))
    logout(client)

    with app.app_context():
        uid = get_db().execute("SELECT id FROM users WHERE username = 'Alpha'").fetchone()[0]

    login(client, "Admin", "Admin$123")
    page = client.get(f"/admin/players/{uid}").get_data(as_text=True)
    assert "Guessed <strong>2</strong> of <strong>3</strong> words" in page
    assert "2026-09-29" in page and "2026-09-30" in page
    assert client.get("/admin/players/9999").status_code == 404


def test_admin_can_add_and_remove_words(client, app):
    login(client, "Admin", "Admin$123")
    assert client.post("/admin/words", data={"word": "light"}).status_code == 302   # stored upper case
    assert client.post("/admin/words", data={"word": "LIGHT"}).status_code == 422   # duplicate
    assert client.post("/admin/words", data={"word": "LIG"}).status_code == 422
    with app.app_context():
        wid = get_db().execute("SELECT id FROM words WHERE word = 'LIGHT'").fetchone()[0]
    client.post(f"/admin/words/{wid}/delete")
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM words WHERE word = 'LIGHT'").fetchone()[0] == 0


def test_played_word_cannot_be_removed(client, app, day):
    register(client, "Adarsh")
    gid = start_game(client)
    word = answer_for(app, gid)
    logout(client)
    login(client, "Admin", "Admin$123")
    with app.app_context():
        wid = get_db().execute("SELECT id FROM words WHERE word = ?", (word,)).fetchone()[0]
    client.post(f"/admin/words/{wid}/delete")
    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) FROM words WHERE id = ?", (wid,)).fetchone()[0] == 1


# ---------- CSRF ----------

def test_csrf_blocks_forged_posts(tmp_path):
    from wordgame import create_app
    app = create_app({"TESTING": True, "SECRET_KEY": "t", "DATABASE": str(tmp_path / "c.sqlite")})
    client = app.test_client()
    resp = client.post("/register", data={"username": "Adarsh", "password": PASSWORD})
    assert resp.status_code == 400
