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
async def test_clean_coordinate(test_session_factory, raw, expected):
    """Test clean_coordinate() PL/pgSQL function handles various clean and messy inputs."""
    async with test_session_factory() as session:
        got = await session.scalar(text("SELECT ST_AsText(clean_coordinate(:raw))"), {"raw": raw})
    assert got == expected


@requires_db
async def test_view_invariants(test_session_factory):
    """Verify geometry invariants, CCW winding, area calculations, and rejection tracking."""
    async with test_session_factory() as session:
        row = (
            await session.execute(
                text("""
            SELECT count(*), bool_and(ST_IsValid(geom)), bool_and(ST_IsPolygonCCW(geom)),
                   min(area_m2), max(area_m2),
                   bool_and(ST_Within(geom, ST_MakeEnvelope(66, 6, 98, 38, 4326)))
            FROM processed_farm_geojson""")
            )
        ).one()
        rejected = await session.scalar(text("SELECT count(*) FROM farm_rejections"))

    assert row == (10, True, True, row[3], row[4], True)
    assert row[3] >= 500 and row[4] <= 50_000
    assert rejected == 0
