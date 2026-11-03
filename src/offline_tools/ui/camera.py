"""Webcam QR scanning on a background thread. Frames never leave this computer."""

import logging
import sys
from collections.abc import Callable
from typing import Any, Protocol

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from offline_tools.core.qr_decode import find_qr_codes

logger = logging.getLogger(__name__)

FRAME_INTERVAL_MS = 40  # ~25 fps preview
DECODE_EVERY_N_FRAMES = 3  # decoding is slower than showing frames
CAMERA_ERROR = (
    "Couldn't open a camera. Check one is connected and that this app may use it "
    "(Windows: Settings → Privacy & security → Camera. Mac: System Settings → "
    "Privacy & Security → Camera)."
)
CAMERA_LOST = "The camera stopped sending pictures."


class FrameSource(Protocol):
    def isOpened(self) -> bool: ...
    def read(self) -> tuple[bool, Any]: ...
    def release(self) -> None: ...


def open_default_camera() -> FrameSource:
    # DirectShow opens much faster than Media Foundation on many Windows webcams.
    backend = {"win32": cv2.CAP_DSHOW, "darwin": cv2.CAP_AVFOUNDATION}.get(
        sys.platform, cv2.CAP_ANY
    )
    capture: FrameSource = cv2.VideoCapture(0, backend)
    return capture


class CameraScanner(QThread):
    frame_ready = Signal(QImage)
    codes_found = Signal(list)  # list[str]
    failed = Signal(str)

    def __init__(
        self,
        open_source: Callable[[], FrameSource] = open_default_camera,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._open_source = open_source

    def run(self) -> None:
        try:
            source = self._open_source()
        except (cv2.error, OSError) as exc:
            logger.warning("Camera failed to open: %r", exc)
            self.failed.emit(CAMERA_ERROR)
            return
        try:
            if not source.isOpened():
                self.failed.emit(CAMERA_ERROR)
                return
            self._scan(source)
        finally:
            source.release()

    def _scan(self, source: FrameSource) -> None:
        frame_index = 0
        while not self.isInterruptionRequested():
            ok, frame = source.read()
            if not ok or frame is None:
                self.failed.emit(CAMERA_LOST)
                return
            rgb: NDArray[np.uint8] = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.frame_ready.emit(_to_qimage(rgb))
            frame_index += 1
            if frame_index % DECODE_EVERY_N_FRAMES == 0:
                codes = find_qr_codes(Image.fromarray(rgb))
                if codes:
                    self.codes_found.emit(list(codes))
                    return
            self.msleep(FRAME_INTERVAL_MS)


def _to_qimage(rgb: NDArray[np.uint8]) -> QImage:
    height, width = rgb.shape[:2]
    contiguous = np.ascontiguousarray(rgb)
    # copy(): QImage would otherwise point at numpy memory that is about to be freed.
    return QImage(contiguous.data, width, height, 3 * width, QImage.Format.Format_RGB888).copy()
