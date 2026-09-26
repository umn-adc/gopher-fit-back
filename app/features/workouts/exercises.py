import re

# Go strings.Fields uses Unicode White_Space, not Python's additional C0 separators.
WHITESPACE = re.compile(r"[\t\n\v\f\r \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+")


def display_name(name: str) -> str:
    return WHITESPACE.sub(" ", name).strip(" ")


def exercise_key(name: str) -> str:
    # Go applies simple lowercase per rune, without contextual sigma or expansions.
    return "".join(char.lower()[0] for char in display_name(name))
