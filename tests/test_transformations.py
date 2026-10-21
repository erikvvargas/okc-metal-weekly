
import pandas as pd
import pytest

from generate import (
    truthy,
    filter_week,
    prep_shows,
    prep_releases,
    split_release_pages,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("TRUE", True),
        ("yes", True),
        ("1", True),
        ("x", True),
        ("false", False),
        ("", False),
        (None, False),
    ],
)
def test_truthy(value, expected):
    assert truthy(value) is expected


def test_filter_week():
    # Arrange
    releases = pd.DataFrame(
        [
            {"release_date": "2026-10-16", "artist": "A", "include": True},
            {"release_date": "2026-10-17", "artist": "B", "include": False},
            {"release_date": "2026-10-25", "artist": "C", "include": True},
            {"release_date": "invalid", "artist": "D", "include": True},
        ]
    )

    start = pd.Timestamp("2026-10-16")
    end = pd.Timestamp("2026-10-24")

    # Act
    result = filter_week(releases, "release_date", start, end)

    # Assert
    assert result["artist"].tolist() == ["A"]


def test_prep_shows_with_notation():
    shows = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-10-16"),
                "venue": "89th Street",
                "bands": "Band A|Band B|Band C",
                "Notations": "TONIGHT!",
            }
        ]
    )

    result = prep_shows(shows)

    assert len(result) == 1
    assert result[0]["day"] == "FRI"
    assert result[0]["events"][0]["venue"] == "89th Street"
    assert result[0]["events"][0]["bands_display"] == "Band A • Band B • Band C"
    assert result[0]["events"][0]["notation"] == "TONIGHT!"


def test_prep_releases():
    releases = pd.DataFrame(
        [
            {"artist": "Zulu", "title": "Release Z", "type": "Single"},
            {"artist": "Alpha", "title": "Release A", "type": "Album"},
            {"artist": "Beta", "title": "Release B", "type": "EP"},
        ]
    )

    result = prep_releases(releases, ["Album", "EP"])

    assert result == [
        {"artist": "Alpha", "title": "Release A"},
        {"artist": "Beta", "title": "Release B"},
    ]


@pytest.mark.parametrize(
    "count, expected_sizes",
    [
        (0, [0]),
        (20, [20]),
        (26, [26]),
        (27, [14, 13]),
        (34, [17, 17]),
        (53, [18, 18, 17]),
    ],
)
def test_split_release_pages(count, expected_sizes):
    items = list(range(count))

    pages = split_release_pages(items)

    assert [len(page) for page in pages] == expected_sizes
    assert [item for page in pages for item in page] == items
    assert all(len(page) <= 26 for page in pages)
