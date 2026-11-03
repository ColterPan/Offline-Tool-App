from offline_tools.core.geometry import Point, Rect


def test_rect_from_points_sorts_and_clamps() -> None:
    rect = Rect.from_points(Point(0.8, 1.4), Point(-0.2, 0.3))

    assert rect == Rect(0.0, 0.3, 0.8, 1.0)


def test_rect_to_pixels_rounds_outward() -> None:
    # 0.333 * 100 = 33.3 -> 33 on the left; 0.667 * 100 = 66.7 -> 67 on the right.
    assert Rect(0.333, 0.333, 0.667, 0.667).to_pixels(100, 100) == (33, 33, 67, 67)


def test_rect_empty_and_contains() -> None:
    assert Rect(0.5, 0.5, 0.5005, 0.9).is_empty
    rect = Rect(0.1, 0.1, 0.4, 0.4)
    assert not rect.is_empty
    assert rect.contains(Point(0.2, 0.3))
    assert not rect.contains(Point(0.5, 0.3))


def test_point_clamped_and_to_pixels() -> None:
    assert Point(1.5, -1).clamped() == Point(1.0, 0.0)
    assert Point(0.5, 0.25).to_pixels(200, 400) == (100, 100)
