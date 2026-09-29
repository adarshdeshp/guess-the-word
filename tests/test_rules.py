import pytest

from wordgame.rules import (
    ABSENT as A, CORRECT as C, PRESENT as P,
    is_valid_word, password_problems, score_guess, username_problems,
)


@pytest.mark.parametrize("answer, guess, expected", [
    ("TOWER", "TOWER", [C, C, C, C, C]),
    ("TOWER", "AUDIO", [A, A, A, A, P]),          # example from the brief
    ("TOWER", "HOMER", [A, C, A, C, C]),
    ("TOWER", "TONER", [C, C, A, C, C]),
    ("CRANE", "SPEED", [A, A, P, A, A]),          # only one E is marked, answer has one E
    ("APPLE", "PAPER", [P, P, C, P, A]),
    ("ROBOT", "OOOOO", [A, C, A, C, A]),          # extra O's beyond the answer are grey
    ("LEVEL", "EEEEE", [A, C, A, C, A]),
    ("ABBEY", "BABES", [P, P, C, C, A]),
])
def test_score_guess(answer, guess, expected):
    assert score_guess(answer, guess) == expected


def test_score_guess_rejects_wrong_length():
    with pytest.raises(ValueError):
        score_guess("TOWER", "TOWERS")


@pytest.mark.parametrize("word, ok", [
    ("TOWER", True), ("tower", False), ("Tower", False),
    ("TOWE", False), ("TOWERS", False), ("TOW3R", False), ("", False), (None, False),
])
def test_is_valid_word(word, ok):
    assert is_valid_word(word) is ok


@pytest.mark.parametrize("name, ok", [
    ("Adarsh", True), ("AbCdE", True),
    ("adarsh", False),       # no upper case
    ("ADARSH", False),       # no lower case
    ("Adar", False),         # too short
    ("Adarsh1", False),      # digit
    ("Ada rsh", False),      # space
    ("Adårsh", False),       # non-ASCII letter
])
def test_username_rules(name, ok):
    assert (username_problems(name) == []) is ok


@pytest.mark.parametrize("pw, ok", [
    ("abc1$", True), ("Play$123", True), ("x9%yz", True), ("a1*bc", True), ("a1@bc", True),
    ("ab1$", False),         # too short
    ("abcd$", False),        # no number
    ("1234$", False),        # no letter
    ("abc12", False),        # no special
    ("abc1#", False),        # special not in the allowed set
])
def test_password_rules(pw, ok):
    assert (password_problems(pw) == []) is ok
