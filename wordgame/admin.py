import sqlite3
from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import rules
from .auth import role_required
from .db import get_db

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _parse_day(raw):
    try:
        return date.fromisoformat(raw).isoformat()
    except (TypeError, ValueError):
        return rules.today()


@bp.get("/")
@role_required("admin")
def daily_report():
    """Report for one day: how many players played and how many words were guessed."""
    db = get_db()
    day = _parse_day(request.args.get("day"))
    d = date.fromisoformat(day)

    totals = db.execute(
        """SELECT COUNT(DISTINCT user_id)          AS players,
                  COUNT(*)                         AS words_tried,
                  COALESCE(SUM(status = 'won'), 0) AS correct
             FROM games WHERE played_on = ?""",
        (day,),
    ).fetchone()

    by_player = db.execute(
        """SELECT users.id, users.username,
                  COUNT(*)                     AS words_tried,
                  SUM(games.status = 'won')    AS correct,
                  SUM(games.status = 'in_progress') AS unfinished
             FROM games JOIN users ON users.id = games.user_id
            WHERE games.played_on = ?
            GROUP BY users.id
            ORDER BY correct DESC, users.username COLLATE NOCASE""",
        (day,),
    ).fetchall()

    recent_days = db.execute(
        """SELECT played_on, COUNT(DISTINCT user_id) AS players, SUM(status = 'won') AS correct
             FROM games GROUP BY played_on ORDER BY played_on DESC LIMIT 10"""
    ).fetchall()

    return render_template(
        "admin/daily.html",
        day=day,
        day_label=d.strftime("%A, %d %B %Y"),
        prev_day=(d - timedelta(days=1)).isoformat(),
        next_day=(d + timedelta(days=1)).isoformat(),
        is_today=day == rules.today(),
        totals=totals,
        by_player=by_player,
        recent_days=recent_days,
    )


@bp.get("/players")
@role_required("admin")
def players():
    rows = get_db().execute(
        """SELECT users.id, users.username, users.created_at,
                  COUNT(games.id)                        AS words_tried,
                  COALESCE(SUM(games.status = 'won'), 0) AS correct,
                  MAX(games.played_on)                   AS last_played
             FROM users LEFT JOIN games ON games.user_id = users.id
            WHERE users.role = 'player'
            GROUP BY users.id
            ORDER BY users.username COLLATE NOCASE"""
    ).fetchall()
    return render_template("admin/players.html", players=rows)


@bp.get("/players/<int:user_id>")
@role_required("admin")
def player_report(user_id):
    """Report for one player: per date, words tried and correct guesses."""
    db = get_db()
    player = db.execute(
        "SELECT id, username, created_at FROM users WHERE id = ? AND role = 'player'", (user_id,)
    ).fetchone()
    if player is None:
        abort(404)

    days = db.execute(
        """SELECT played_on,
                  COUNT(*)                 AS words_tried,
                  SUM(status = 'won')      AS correct
             FROM games WHERE user_id = ?
            GROUP BY played_on ORDER BY played_on DESC""",
        (user_id,),
    ).fetchall()

    games = db.execute(
        """SELECT games.id, games.played_on, games.status, words.word,
                  (SELECT GROUP_CONCAT(guess, ' ')
                     FROM (SELECT guess FROM guesses
                            WHERE game_id = games.id ORDER BY attempt_no)) AS guesses
             FROM games JOIN words ON words.id = games.word_id
            WHERE games.user_id = ?
            ORDER BY games.id DESC""",
        (user_id,),
    ).fetchall()

    total_tried = sum(d["words_tried"] for d in days)
    total_correct = sum(d["correct"] for d in days)
    return render_template(
        "admin/player.html",
        player=player,
        days=days,
        games=games,
        total_tried=total_tried,
        total_correct=total_correct,
    )


@bp.route("/words", methods=("GET", "POST"))
@role_required("admin")
def words():
    db = get_db()
    error = None
    draft = ""
    if request.method == "POST":
        draft = request.form.get("word", "").strip().upper()
        if not rules.is_valid_word(draft):
            error = "A word needs exactly 5 letters, A to Z."
        else:
            try:
                db.execute("INSERT INTO words (word) VALUES (?)", (draft,))
                db.commit()
            except sqlite3.IntegrityError:
                error = f"{draft} is already in the list."
            else:
                flash(f"Added {draft}.", "success")
                return redirect(url_for("admin.words"))

    rows = db.execute(
        """SELECT words.id, words.word, COUNT(games.id) AS times_given
             FROM words LEFT JOIN games ON games.word_id = words.id
            GROUP BY words.id ORDER BY words.word"""
    ).fetchall()
    return render_template("admin/words.html", words=rows, error=error, draft=draft), (
        422 if error else 200
    )


@bp.post("/words/<int:word_id>/delete")
@role_required("admin")
def delete_word(word_id):
    db = get_db()
    row = db.execute(
        """SELECT words.word, COUNT(games.id) AS used
             FROM words LEFT JOIN games ON games.word_id = words.id
            WHERE words.id = ? GROUP BY words.id""",
        (word_id,),
    ).fetchone()
    if row is None:
        abort(404)
    if row["used"]:
        flash(f"{row['word']} has been played, so it stays in the list to keep reports accurate.", "error")
    else:
        db.execute("DELETE FROM words WHERE id = ?", (word_id,))
        db.commit()
        flash(f"Removed {row['word']}.", "success")
    return redirect(url_for("admin.words"))
