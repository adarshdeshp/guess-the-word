from datetime import datetime

from flask import (
    Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, url_for,
    request,
)

from . import rules
from .auth import home_for, role_required
from .db import get_db

bp = Blueprint("game", __name__)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _load_game(game_id):
    """Fetch a game owned by the current player, with its answer."""
    game = get_db().execute(
        """SELECT games.*, words.word AS answer
             FROM games JOIN words ON words.id = games.word_id
            WHERE games.id = ? AND games.user_id = ?""",
        (game_id, g.user["id"]),
    ).fetchone()
    if game is None:
        abort(404)
    return game


def _scored_guesses(game):
    rows = get_db().execute(
        "SELECT guess FROM guesses WHERE game_id = ? ORDER BY attempt_no", (game["id"],)
    ).fetchall()
    return [
        {"guess": r["guess"], "result": rules.score_guess(game["answer"], r["guess"])}
        for r in rows
    ]


@bp.get("/")
def index():
    if g.user:
        return redirect(home_for(g.user))
    return redirect(url_for("auth.login"))


@bp.get("/play")
@role_required("player")
def dashboard():
    db = get_db()
    day = rules.today()
    limit = current_app.config["DAILY_WORD_LIMIT"]

    todays = db.execute(
        """SELECT games.id, games.status, words.word,
                  (SELECT COUNT(*) FROM guesses WHERE game_id = games.id) AS tries
             FROM games JOIN words ON words.id = games.word_id
            WHERE user_id = ? AND played_on = ?
            ORDER BY games.id""",
        (g.user["id"], day),
    ).fetchall()

    open_game = db.execute(
        "SELECT id FROM games WHERE user_id = ? AND status = 'in_progress' ORDER BY id DESC LIMIT 1",
        (g.user["id"],),
    ).fetchone()

    history = db.execute(
        """SELECT played_on,
                  COUNT(*) AS words_tried,
                  SUM(status = 'won') AS correct
             FROM games
            WHERE user_id = ? AND played_on < ?
            GROUP BY played_on
            ORDER BY played_on DESC
            LIMIT 7""",
        (g.user["id"], day),
    ).fetchall()

    return render_template(
        "game/dashboard.html",
        todays=todays,
        limit=limit,
        open_game=open_game,
        remaining=max(limit - len(todays), 0),
        history=history,
        max_guesses=current_app.config["MAX_GUESSES"],
    )


@bp.post("/play/new")
@role_required("player")
def start():
    db = get_db()
    user_id = g.user["id"]

    # Finish what you started before taking a new word.
    open_game = db.execute(
        "SELECT id FROM games WHERE user_id = ? AND status = 'in_progress' ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if open_game:
        return redirect(url_for("game.board", game_id=open_game["id"]))

    day = rules.today()
    limit = current_app.config["DAILY_WORD_LIMIT"]
    played_today = db.execute(
        "SELECT COUNT(*) FROM games WHERE user_id = ? AND played_on = ?", (user_id, day)
    ).fetchone()[0]
    if played_today >= limit:
        flash(f"You've played all {limit} words for today. New words unlock tomorrow.", "info")
        return redirect(url_for("game.dashboard"))

    # Prefer a word this player hasn't seen yet; fall back to any word once all are used.
    word = db.execute(
        """SELECT id FROM words
            WHERE id NOT IN (SELECT word_id FROM games WHERE user_id = ?)
            ORDER BY RANDOM() LIMIT 1""",
        (user_id,),
    ).fetchone() or db.execute("SELECT id FROM words ORDER BY RANDOM() LIMIT 1").fetchone()

    if word is None:
        flash("There are no words to play yet. Ask an admin to add some.", "error")
        return redirect(url_for("game.dashboard"))

    cur = db.execute(
        "INSERT INTO games (user_id, word_id, played_on, started_at) VALUES (?, ?, ?, ?)",
        (user_id, word["id"], day, _now()),
    )
    db.commit()
    return redirect(url_for("game.board", game_id=cur.lastrowid))


@bp.get("/play/<int:game_id>")
@role_required("player")
def board(game_id):
    game = _load_game(game_id)
    db = get_db()
    word_number = db.execute(
        "SELECT COUNT(*) FROM games WHERE user_id = ? AND played_on = ? AND id <= ?",
        (g.user["id"], game["played_on"], game["id"]),
    ).fetchone()[0]

    return render_template(
        "game/board.html",
        game=game,
        rows=_scored_guesses(game),
        max_guesses=current_app.config["MAX_GUESSES"],
        word_number=word_number,
        limit=current_app.config["DAILY_WORD_LIMIT"],
        answer=game["answer"] if game["status"] != "in_progress" else None,
    )


@bp.post("/api/games/<int:game_id>/guesses")
@role_required("player")
def submit_guess(game_id):
    game = _load_game(game_id)
    max_guesses = current_app.config["MAX_GUESSES"]

    if game["status"] != "in_progress":
        return jsonify(error="This word is finished. Go back and start the next one."), 409

    payload = request.get_json(silent=True) or {}
    guess = str(payload.get("guess", "")).strip()
    if not rules.is_valid_word(guess):
        return jsonify(error="Enter exactly 5 capital letters, A to Z."), 422

    db = get_db()
    attempt = db.execute(
        "SELECT COUNT(*) FROM guesses WHERE game_id = ?", (game_id,)
    ).fetchone()[0] + 1
    if attempt > max_guesses:
        return jsonify(error="No guesses left for this word."), 409

    now = _now()
    db.execute(
        "INSERT INTO guesses (game_id, attempt_no, guess, guessed_at) VALUES (?, ?, ?, ?)",
        (game_id, attempt, guess, now),
    )

    result = rules.score_guess(game["answer"], guess)
    if guess == game["answer"]:
        status = "won"
    elif attempt == max_guesses:
        status = "lost"
    else:
        status = "in_progress"

    if status != "in_progress":
        db.execute(
            "UPDATE games SET status = ?, finished_at = ? WHERE id = ?", (status, now, game_id)
        )
    db.commit()

    return jsonify(
        guess=guess,
        result=result,
        attempt=attempt,
        remaining=max_guesses - attempt,
        status=status,
        answer=game["answer"] if status != "in_progress" else None,
    )
