import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))



def test_parse_sort_by_trailing_direction():
    from pytae.cli_parsing import parse_sort_by
    assert parse_sort_by("val") == (["val"], "asc")
    assert parse_sort_by("val desc") == (["val"], "desc")
    assert parse_sort_by("species,body_mass_g desc") == (["species", "body_mass_g"], "desc")
    assert parse_sort_by("bill length mm desc") == (["bill length mm"], "desc")

