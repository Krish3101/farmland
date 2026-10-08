import pytest
from sqlalchemy import text

from tests.conftest import requires_db

CASES = [
    ("18.5228398,74.9514285", "POINT(74.9514285 18.5228398)"),  # clean
    (" 16.4418, 74.1393 ", "POINT(74.1393 16.4418)"),  # outer spaces
    ("17. 504503, 73.988443", "POINT(73.988443 17.504503)"),  # space inside a number
    ("18.52\t,\n73.85", "POINT(73.85 18.52)"),  # tabs/newlines
    ("17.943318, 75237089", "POINT(75.237089 17.943318)"),  # missing decimal, lon
    ("185228398,749514285", "POINT(74.9514285 18.5228398)"),  # missing decimal, both
    ("74.9514285,18.5228398", "POINT(74.9514285 18.5228398)"),  # swapped lat/lon
    ("18.52°, 73.85°", "POINT(73.85 18.52)"),  # degree signs stripped
    ("18.52°N, 73.85°E", None),  # hemisphere letters: rejected
    ("8123456,77123456", None),  # 1-digit lat, no decimal (lat 81 rejected)
    ("100.5,200.5", None),  # out of range
    ("0,0", None),  # null island
    ("12,34", None),  # outside India
    ("-18.52,73.85", None),  # negative
    ("+18.52,+73.85", None),  # plus signs rejected
    ("18.52 73.85", None),  # no comma
    ("18,52,73,85", None),  # decimal commas
    ("18.52,", None),  # trailing comma
    (",73.85", None),  # leading comma
    ("", None),  # empty string
    ("abc,def", None),  # non-numeric
    ("NaN,NaN", None),  # NaN rejected
    ("Infinity,73.85", None),  # Infinity rejected
    ("1.e5,73.85", None),  # exponent rejected
    (None, None),  # null input
]


@requires_db
@pytest.mark.parametrize(("raw", "expected"), CASES)
def test_clean_corner(db, raw, expected):
    """Test clean_corner() PL/pgSQL function handles various clean and messy inputs."""
    got = db.scalar(text("SELECT ST_AsText(clean_corner(:raw))"), {"raw": raw})
    assert got == expected
