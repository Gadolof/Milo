import pytest

from milo.text import find_number, normalize
from milo.vocabulary import build_grammar, fix_constrained, french_number


@pytest.mark.parametrize("n, text", [
    (0, "zéro"), (17, "dix-sept"), (21, "vingt et un"), (22, "vingt-deux"),
    (70, "soixante-dix"), (71, "soixante et onze"), (77, "soixante-dix-sept"),
    (80, "quatre-vingts"), (81, "quatre-vingt-un"), (97, "quatre-vingt-dix-sept"), (100, "cent"),
])
def test_french_number(n, text):
    assert french_number(n) == text


def test_every_spelled_number_reads_back():
    for n in range(101):
        assert find_number(normalize(french_number(n))) == n


@pytest.mark.parametrize("raw, fixed", [
    ("niveau deux batterie", "niveau de batterie"),
    ("baisse le son deux vingt", "baisse le son de vingt"),
    ("volume à deux", "volume à deux"),
    ("monte le son de deux crans", "monte le son de deux crans"),
])
def test_fix_constrained(raw, fixed):
    assert fix_constrained(raw) == fixed


def test_grammar():
    grammar = build_grammar(["Explorateur de fichiers", "Google Chrome"])
    assert grammar[-1] == "[unk]"
    for word in ("google", "chrome", "explorateur", "l'explorateur", "l'écran", "quatre-vingt-dix", "milo"):
        assert word in grammar
    for homophone in ("sons", "aux", "quels"):
        assert homophone not in grammar
