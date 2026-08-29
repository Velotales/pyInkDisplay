"""
MIT License

Copyright (c) 2026 Velotales

Unit tests for aspect-preserving panel fitting in pyInkDisplay.
"""

from PIL import Image

from pyinkdisplay.pyInkDisplay import fitImageToPanel

W, H = 800, 480
RED = (255, 0, 0)
BLACK = (0, 0, 0)


def _red(w, h):
    return Image.new("RGB", (w, h), RED)


def test_exact_panel_size_is_left_alone():
    """An 800x480 dashboard capture must pass through untouched."""
    fitted = fitImageToPanel(_red(W, H), W, H)
    assert fitted.size == (W, H)
    assert fitted.convert("RGB").getpixel((0, 0)) == RED


def test_mild_mismatch_crops_to_fill_the_panel():
    """4:3 is within tolerance, so fill the glass rather than showing bars."""
    fitted = fitImageToPanel(_red(1024, 768), W, H).convert("RGB")
    assert fitted.size == (W, H)
    # every corner is image, not background
    for xy in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        assert fitted.getpixel(xy) == RED


def test_severe_mismatch_letterboxes_instead_of_cropping():
    """A 3:4 portrait would lose its subject to a crop, so bar it instead."""
    fitted = fitImageToPanel(_red(768, 1024), W, H).convert("RGB")
    assert fitted.size == (W, H)
    assert fitted.getpixel((0, H // 2)) == BLACK  # left bar
    assert fitted.getpixel((W - 1, H // 2)) == BLACK  # right bar
    assert fitted.getpixel((W // 2, H // 2)) == RED  # image in the middle


def test_letterboxed_image_keeps_its_aspect_ratio():
    """A 1:2 source scaled to fit 480 tall must be exactly 240 wide, centred."""
    fitted = fitImageToPanel(_red(480, 960), W, H).convert("RGB")
    left_bar = (W - 240) // 2  # 280
    assert fitted.getpixel((left_bar - 1, H // 2)) == BLACK
    assert fitted.getpixel((left_bar + 1, H // 2)) == RED
    assert fitted.getpixel((W - left_bar + 1, H // 2)) == BLACK


def test_extreme_panorama_is_letterboxed_top_and_bottom():
    """A very wide source keeps its full width rather than losing the ends."""
    fitted = fitImageToPanel(_red(2000, 500), W, H).convert("RGB")
    assert fitted.size == (W, H)
    assert fitted.getpixel((W // 2, 0)) == BLACK
    assert fitted.getpixel((W // 2, H // 2)) == RED


def test_displayImage_letterboxes_instead_of_squashing():
    """The panel must receive a fitted image, not a distorted one."""
    from unittest.mock import MagicMock

    from pyinkdisplay.pyInkDisplay import PyInkDisplay

    epd = MagicMock()
    epd.width, epd.height = W, H
    manager = PyInkDisplay()
    manager.epd = epd

    manager.displayImage(_red(768, 1024))

    sent = epd.display.call_args[0][0].convert("RGB")
    assert sent.size == (W, H)
    assert sent.getpixel((0, H // 2)) == BLACK  # would be RED if squashed
    assert sent.getpixel((W // 2, H // 2)) == RED
