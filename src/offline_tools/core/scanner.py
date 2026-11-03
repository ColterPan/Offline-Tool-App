"""Turn a phone photo of a document into a clean, straight scan (OpenCV).

1. detect_page: find the page's four corners (the user can adjust them in the UI)
2. straighten: perspective-correct the page into a flat rectangle
3. enhance: even out shadows, then black & white / greyscale / brighter colour
"""

import math
from enum import StrEnum
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.geometry import Point, Quad
from offline_tools.core.images import format_for_suffix, save_image, to_rgb, write_pdf

DETECT_MAX_SIDE = 1000  # detection runs on a downscaled copy: faster and less noisy
MIN_PAGE_AREA = 0.15  # the page must fill at least this much of the photo
APPROX_EPSILON = 0.02  # polygon simplification, as a fraction of the outline length
MIN_OUTPUT_SIDE = 20
BACKGROUND_SCALE = 0.25  # shadow estimation runs at quarter size for speed
BLANK_STD = 4.0
MAX_MASK_FILL = 0.97
A4_LONG_SIDE_INCHES = 11.69
SCAN_JPEG_QUALITY = 92
EDGE_TRIM = 0.006  # trim a hair inside the corners so no desk shows at the edges

type Pixels = NDArray[Any]  # OpenCV's stubs return loosely typed arrays


class ScanMode(StrEnum):
    BLACK_WHITE = "bw"
    GREYSCALE = "grey"
    COLOUR = "colour"
    ORIGINAL = "original"


def detect_page(img: Image.Image) -> Quad | None:
    """Normalised page corners (TL, TR, BR, BL), or None if no clear page is found."""
    rgb = np.asarray(to_rgb(img))
    height, width = rgb.shape[:2]
    scale = min(1.0, DETECT_MAX_SIDE / max(height, width))
    small = cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    grey = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_RGB2GRAY), (5, 5), 0)
    if float(grey.std()) < BLANK_STD:  # featureless photo: nothing to find
        return None
    small_h, small_w = grey.shape
    min_area = MIN_PAGE_AREA * small_h * small_w
    for mask in _candidate_masks(grey):
        quad = _largest_quad(mask, min_area)
        if quad is not None:
            return _order_corners(quad / np.array([small_w, small_h], dtype=np.float64))
    return None


def straighten(img: Image.Image, quad: Quad) -> Image.Image:
    rgb = np.asarray(to_rgb(img))
    height, width = rgb.shape[:2]
    corners = np.array([point.clamped().to_pixels(width, height) for point in quad], np.float32)
    tl, tr, br, bl = corners
    out_w = round(max(math.dist(tl, tr), math.dist(bl, br)))
    out_h = round(max(math.dist(tl, bl), math.dist(tr, br)))
    if min(out_w, out_h) < MIN_OUTPUT_SIDE:
        raise InvalidInputError("The corners are too close together. Drag them to the page edges.")
    target = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], np.float32)
    matrix = cv2.getPerspectiveTransform(corners, target)
    flat = cv2.warpPerspective(
        rgb, matrix, (out_w, out_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    trim_x, trim_y = round(out_w * EDGE_TRIM), round(out_h * EDGE_TRIM)
    return Image.fromarray(flat[trim_y : out_h - trim_y, trim_x : out_w - trim_x])


def enhance(img: Image.Image, mode: ScanMode) -> Image.Image:
    rgb = np.asarray(to_rgb(img))
    if mode is ScanMode.ORIGINAL:
        return Image.fromarray(rgb)
    if mode is ScanMode.COLOUR:
        channels = [_flatten_lighting(rgb[:, :, i]) for i in range(3)]
        return Image.fromarray(np.dstack(channels))
    flat = _flatten_lighting(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY))
    if mode is ScanMode.GREYSCALE:
        return Image.fromarray(flat)
    if float(flat.std()) < BLANK_STD:  # a blank page: Otsu would invent noise
        return Image.fromarray(np.full_like(flat, 255))
    _, bw = cv2.threshold(flat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(bw)


def scan_document(img: Image.Image, quad: Quad, mode: ScanMode, out: Path) -> Path:
    """Straighten, enhance and save in one step (what the Save button runs)."""
    return save_scan(enhance(straighten(img, quad), mode), out)


def save_scan(scan: Image.Image, out: Path) -> Path:
    """Save as PDF (page scaled to A4 length) or as an image, by the file extension."""
    if out.suffix.lower() == ".pdf":
        dpi = max(scan.size) / A4_LONG_SIDE_INCHES
        return write_pdf([scan], out, total=1, resolution=dpi)
    return save_image(scan, out, format_for_suffix(out.suffix), quality=SCAN_JPEG_QUALITY)


def _candidate_masks(grey: Pixels) -> list[Pixels]:
    """Two ways to find the page: its edges, and it being brighter than the background."""
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(cv2.Canny(grey, 50, 150), kernel, iterations=2)
    _, bright = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    masks = [edges]
    # A mask that is (almost) all white just traces the photo's own border: not a page.
    if float(bright.mean()) < MAX_MASK_FILL * 255:
        masks.append(bright)
    return masks


def _largest_quad(mask: Pixels, min_area: float) -> NDArray[np.float64] | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        if cv2.contourArea(contour) < min_area:
            return None
        hull = cv2.convexHull(contour)
        approx = cv2.approxPolyDP(hull, APPROX_EPSILON * cv2.arcLength(hull, True), True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return approx.reshape(4, 2).astype(np.float64)
    return None


def _order_corners(points: NDArray[np.float64]) -> Quad:
    sums = points.sum(axis=1)
    diffs = points[:, 1] - points[:, 0]
    tl, br = points[np.argmin(sums)], points[np.argmax(sums)]
    tr, bl = points[np.argmin(diffs)], points[np.argmax(diffs)]
    return (
        Point(float(tl[0]), float(tl[1])),
        Point(float(tr[0]), float(tr[1])),
        Point(float(br[0]), float(br[1])),
        Point(float(bl[0]), float(bl[1])),
    )


def _flatten_lighting(channel: Pixels) -> Pixels:
    """Remove shadows and uneven light: estimate the paper's brightness and divide it out."""
    height, width = channel.shape
    small = cv2.resize(channel, None, fx=BACKGROUND_SCALE, fy=BACKGROUND_SCALE,
                       interpolation=cv2.INTER_AREA)  # fmt: skip
    # Dilate wipes out thin dark text, the median smooths what's left: the paper background.
    background = cv2.medianBlur(cv2.dilate(small, np.ones((7, 7), np.uint8)), 21)
    background = cv2.resize(background, (width, height), interpolation=cv2.INTER_LINEAR)
    diff = 255 - cv2.absdiff(channel, background)
    normalised: Pixels = cv2.normalize(diff, np.zeros_like(diff), 0, 255, cv2.NORM_MINMAX)
    return normalised
