# Guess the Word

A five-letter word guessing game with player and admin roles, built with **Python, Flask and SQLite**.
Pre-boarding project for the OpenText India internship program.

## Run it

Needs Python 3.10 or newer.

```bash
git clone <this-repo-url>
cd guess-the-word
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000. The database is created automatically on first start in `instance/wordgame.sqlite`, with 20 starter words and an admin account.

| Account | Username | Password |
|---|---|---|
| Admin (seeded) | `Admin` | `Admin$123` |
| Player | Register on the sign-up page | |

The admin credentials can be changed with the `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables before first start. To wipe all data and start fresh: `flask --app wordgame reset-db`.

## Run the tests

```bash
python -m pytest -q
```

65 tests cover the scoring rules, username and password validation, the 3-words-per-day limit, winning and losing, saved guess history, access control between roles and players, both admin reports, and CSRF protection.

## How the spec maps to the code

| Requirement | Where |
|---|---|
| Two user types: Admin and Player | `users.role`; `role_required()` in `wordgame/auth.py` guards every page |
| Register and log in with username and password | `wordgame/auth.py`. Passwords are stored as salted hashes, never plain text |
| Username: at least 5 letters, both upper and lower case | `username_problems()` in `wordgame/rules.py`. Letters only; usernames are unique regardless of case |
| Password: at least 5 characters, with a letter, a number and one of `$ % * @` | `password_problems()` in `wordgame/rules.py` |
| Twenty 5-letter upper-case words saved in the database | `STARTER_WORDS` in `wordgame/db.py`, seeded on first start |
| Random word per game, at most 3 words a day per user | `start()` in `wordgame/game.py`. Words a player hasn't seen yet are preferred |
| Guesses are 5 upper-case letters, at most 5 per word | Checked on the server in `submit_guess()`; the on-screen and physical keyboard only enter capitals |
| Green = right spot, orange = wrong spot, grey = not in word | `score_guess()` in `wordgame/rules.py`, with correct handling of repeated letters |
| Win: congratulations message, OK ends the game | Result dialog in `static/game.js` |
| 5 misses: "Better luck next time", OK ends the game | Same dialog, shows the answer |
| Earlier guesses shown in order | Board rows are rebuilt from the `guesses` table, so a refresh or return visit keeps them |
| Save words given and words guessed, with dates | `games` table (word given, `played_on`, status) and `guesses` table (each guess, attempt number, timestamp) |
| Admin report for a day: number of users, number of correct guesses | `/admin/`, with a date picker and per-player breakdown |
| Admin report for a user: date, words tried, correct guesses | `/admin/players/<id>`, plus every word given with its guesses in order |

Beyond the brief: admins can add and remove words (words that have been played are kept so reports stay accurate), and an unfinished word is resumed instead of starting a new one.

## Project layout

```
wordgame/
  __init__.py     app factory and config
  db.py           schema, seeding, reset-db command
  rules.py        scoring and validation (no Flask code, easy to test)
  auth.py         register, login, logout, role guards
  game.py         player dashboard, board, guess API
  admin.py        daily report, player report, word list
  security.py     CSRF protection for every form and the guess API
  templates/      Jinja templates
  static/         style.css, game.js, register.js
tests/            pytest suite
run.py            local entry point
```

## Design notes

- **The answer never reaches the browser** while a game is in progress. Every guess is scored on the server, and the word is only sent back once the game ends.
- **Dates:** `played_on` uses the server's local date, which is what the daily limit and daily report count on.
- **Assumption on password symbols:** the brief lists `$, %, * and` with the last character cut off. I read it as `@` and allow `$ % * @`.
