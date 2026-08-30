"""cli.py is a caller, not the module — but its bullet-list parser has
real logic worth pinning."""

from cv_writer import Emphasis
from cli import _parse_emphasis_file


def test_plain_bullets_become_points():
    text = "- lead with the platform migration work\n- foreground the team-leadership scope\n"
    assert _parse_emphasis_file(text) == [
        Emphasis(point="lead with the platform migration work"),
        Emphasis(point="foreground the team-leadership scope"),
    ]


def test_quote_line_anchors_the_preceding_point():
    text = (
        "# Emphasis\n\n"
        "- lead with the platform migration work\n"
        "  > own our payments and payouts services\n\n"
        "- foreground the team-leadership scope\n"
    )
    assert _parse_emphasis_file(text) == [
        Emphasis(
            point="lead with the platform migration work",
            quote="own our payments and payouts services",
        ),
        Emphasis(point="foreground the team-leadership scope"),
    ]


def test_tolerates_no_bullet_markers_and_ordered_lists():
    text = "1. first point\nsecond point, no marker\n"
    assert _parse_emphasis_file(text) == [
        Emphasis(point="first point"),
        Emphasis(point="second point, no marker"),
    ]


def test_multiple_quote_lines_join_onto_one_anchor():
    text = "- the point\n  > part one\n  > part two\n"
    assert _parse_emphasis_file(text) == [
        Emphasis(point="the point", quote="part one part two"),
    ]


def test_leading_quote_with_no_point_is_ignored():
    assert _parse_emphasis_file("> orphan quote\n- real point\n") == [
        Emphasis(point="real point"),
    ]
