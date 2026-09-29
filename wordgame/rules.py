"""Game rules and input validation. No Flask or database code here, so it is easy to test."""
import re
from collections import Counter
from datetime import date

WORD_LENGTH = 5
WORD_PATTERN = re.compile(r"^[A-Z]{5}$")
PASSWORD_SPECIALS = "$%*@"

CORRECT = "correct"   # right letter, right spot  -> green
PRESENT = "present"   # right letter, wrong spot  -> orange
ABSENT = "absent"     # letter not in the word    -> grey


def today():
    """Today's date as YYYY-MM-DD. Kept as a function so tests can pin the date."""
    return date.today().isoformat()


def is_valid_word(text):
    return bool(WORD_PATTERN.match(text or ""))


def score_guess(answer, guess):
    """Return one of CORRECT / PRESENT / ABSENT for each letter of the guess.

    Repeated letters are handled the way players expect: exact matches are
    claimed first, and a letter is only marked PRESENT while unclaimed copies
    of it remain in the answer. Guessing SPEED against CRANE marks only the
    first E, not both.
    """
    if len(answer) != WORD_LENGTH or len(guess) != WORD_LENGTH:
        raise ValueError("answer and guess must both be 5 letters")

    result = [ABSENT] * WORD_LENGTH
    unclaimed = Counter()

    for i, (a, g) in enumerate(zip(answer, guess)):
        if a == g:
            result[i] = CORRECT
        else:
            unclaimed[a] += 1

    for i, g in enumerate(guess):
        if result[i] != CORRECT and unclaimed[g] > 0:
            result[i] = PRESENT
            unclaimed[g] -= 1

    return result


def username_problems(username):
    """List what is wrong with a username. An empty list means it is valid."""
    username = username or ""
    problems = []
    if not username.isascii() or not username.isalpha():
        problems.append("Use letters only (A to Z), no numbers, spaces or symbols.")
    if len(username) < 5:
        problems.append("Use at least 5 letters.")
    if not any(c.isupper() for c in username) or not any(c.islower() for c in username):
        problems.append("Mix upper and lower case letters, for example Adarsh.")
    return problems


def password_problems(password):
    """List what is wrong with a password. An empty list means it is valid."""
    password = password or ""
    problems = []
    if len(password) < 5:
        problems.append("Use at least 5 characters.")
    if not any(c.isalpha() for c in password):
        problems.append("Include at least one letter.")
    if not any(c.isdigit() for c in password):
        problems.append("Include at least one number.")
    if not any(c in PASSWORD_SPECIALS for c in password):
        problems.append("Include one of these symbols: $ % * @")
    return problems
