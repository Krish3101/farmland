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


@requires_db
async def test_missing_farm_id_is_rejected_not_dropped(test_session_factory):
    """A data row with a serial number but no farm id is listed as a rejection."""
    async with test_session_factory() as session:
        # Rolled back below, so the shared raw table is never changed.
        await session.execute(
            text("""
            INSERT INTO raw_farmers_data ("Unnamed: 1", "Unnamed: 3", "Unnamed: 7",
                                          "Unnamed: 8", "Unnamed: 9", "Unnamed: 10")
            VALUES ('9991', NULL, '18.5200,73.8500', '18.5200,73.8510',
                    '18.5210,73.8510', '18.5210,73.8500'),
                   ('9992', '  ', '18.5200,73.8500', '18.5200,73.8510',
                    '18.5210,73.8510', '18.5210,73.8500')""")
        )
        rejections = (
            await session.execute(
                text("""
                SELECT farm_id, reject_reason FROM farm_rejections
                WHERE farm_id IN ('row 9991', 'row 9992') ORDER BY farm_id""")
            )
        ).all()
        in_view = await session.scalar(
            text("SELECT count(*) FROM processed_farm_geojson WHERE farm_id LIKE 'row %'")
        )
        await session.rollback()

    assert rejections == [("row 9991", "missing farm_id"), ("row 9992", "missing farm_id")]
    assert in_view == 0
