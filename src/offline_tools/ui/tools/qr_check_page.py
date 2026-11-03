"""Check a QR Code: see where a code really goes before you scan it with your phone."""

from functools import partial
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QGuiApplication, QHideEvent, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from offline_tools.core.images import SUPPORTED_INPUT_SUFFIXES
from offline_tools.core.qr_check import QrReport, Severity, Verdict, analyse
from offline_tools.core.qr_decode import decode_qr_codes, decode_qr_file
from offline_tools.ui.camera import CameraScanner
from offline_tools.ui.context import AppContext
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.drop_zone import DropZone
from offline_tools.ui.widgets.pixmaps import qimage_to_pil
from offline_tools.ui.widgets.style import set_style_property
from offline_tools.ui.widgets.tool_page import ToolPage

CAMERA_VIEW_SIZE = (480, 360)
CAMERA_STOP_WAIT_MS = 2000
LONG_VALUE_CHARS = 60
VERDICT_STYLE = {
    Verdict.OK: ("ok", "✓"),
    Verdict.CAUTION: ("caution", "⚠"),
    Verdict.DANGER: ("danger", "✕"),
}
SEVERITY_ICON = {Severity.DANGER: "✕", Severity.CAUTION: "⚠", Severity.INFO: "•"}
DISCLAIMER = (
    "These checks run on this computer, so they can't know about every scam. They look for "
    "common warning signs. If in doubt, don't open it, or check it on ScamShield "
    "(scamshield.gov.sg)."
)


class QrCheckPage(ToolPage):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(
            "Check a QR Code",
            "See where a QR code really goes before you scan it with your phone: fake bank "
            "sites, dangerous downloads and payment codes that pay someone else.",
            parent,
        )
        self._context = context
        self._camera: CameraScanner | None = None
        self.reports: list[QrReport] = []

        self.add_content(self._build_input_card())
        self.add_content(self._build_link_card())
        self.results = QWidget()
        self.results_layout = QVBoxLayout(self.results)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(12)
        self.add_content(self.results)
        disclaimer = QLabel(DISCLAIMER)
        disclaimer.setProperty("role", "muted")
        disclaimer.setWordWrap(True)
        self.add_content(disclaimer)

        paste = QShortcut(QKeySequence.StandardKey.Paste, self, self.paste_from_clipboard)
        paste.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.stop_camera)
        self._busy_widgets = [self.drop_zone, self.paste_button, self.camera_button]

    # ---- building -----------------------------------------------------------------

    def _build_input_card(self) -> Card:
        card = Card("Check a QR code")
        self.drop_zone = DropZone(
            prompt="Drop a photo or screenshot of the QR code", extensions=SUPPORTED_INPUT_SUFFIXES
        )
        self.drop_zone.files_selected.connect(lambda paths: self.check_image_file(paths[0]))
        self.paste_button = QPushButton("Paste screenshot (Ctrl+V)")
        self.paste_button.clicked.connect(self.paste_from_clipboard)
        self.camera_button = QPushButton("Scan with webcam")
        self.camera_button.clicked.connect(self.toggle_camera)
        buttons = QWidget()
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.paste_button)
        row.addWidget(self.camera_button)
        row.addStretch()
        self.camera_view = QLabel()
        self.camera_view.setFixedSize(*CAMERA_VIEW_SIZE)
        self.camera_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_view.setAccessibleName("Webcam view. Hold the QR code up to the camera.")
        self.camera_view.hide()
        self.camera_hint = QLabel("Hold the QR code up to your webcam…")
        self.camera_hint.setProperty("role", "muted")
        self.camera_hint.hide()
        for widget in (self.drop_zone, buttons, self.camera_view, self.camera_hint):
            card.add(widget)
        return card

    def _build_link_card(self) -> Card:
        card = Card("Or check a link")
        self.link_edit = QLineEdit()
        self.link_edit.setPlaceholderText("Paste a link from an SMS, WhatsApp or email")
        self.link_edit.setAccessibleName("Link to check")
        self.link_edit.returnPressed.connect(self.check_link)
        check = QPushButton("Check link")
        check.setProperty("variant", "primary")
        check.clicked.connect(self.check_link)
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.link_edit, stretch=1)
        row.addWidget(check)
        card.add(row_widget)
        return card

    # ---- inputs ---------------------------------------------------------------------

    def check_image_file(self, path: Path) -> None:
        self.stop_camera()
        self.run_task(
            self._context.runner, partial(_decode_file, path), self.show_payloads,
            disable=self._busy_widgets,
        )  # fmt: skip

    def paste_from_clipboard(self) -> None:
        clipboard = QGuiApplication.clipboard()
        image = clipboard.image()
        if image.isNull():
            text = clipboard.text().strip()
            if text:
                self.link_edit.setText(text)
                self.check_link()
            else:
                self.banner.show_error("There's no picture on the clipboard. Take a screenshot "
                                       "first (Windows: Win+Shift+S).")  # fmt: skip
            return
        self.check_qimage(image)

    def check_qimage(self, image: QImage) -> None:
        self.stop_camera()
        pil = qimage_to_pil(image)
        self.run_task(
            self._context.runner, partial(_decode_image, pil), self.show_payloads,
            disable=self._busy_widgets,
        )  # fmt: skip

    def check_link(self) -> None:
        text = self.link_edit.text().strip()
        if text:
            self.banner.clear()
            self.show_payloads([text])

    # ---- camera ---------------------------------------------------------------------

    def toggle_camera(self) -> None:
        if self._camera is not None:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self, scanner: CameraScanner | None = None) -> None:
        self.banner.clear()
        self._camera = scanner or CameraScanner(parent=self)
        self._camera.frame_ready.connect(self._show_frame)
        self._camera.codes_found.connect(self._on_camera_codes)
        self._camera.failed.connect(self._on_camera_failed)
        camera = self._camera
        # A late "finished" from an old camera must not switch off a newer one.
        camera.finished.connect(lambda: self._on_camera_finished(camera))
        self.camera_view.show()
        self.camera_hint.show()
        self.camera_button.setText("Stop webcam")
        self._camera.start()

    def stop_camera(self) -> None:
        camera = self._camera
        if camera is None:
            return
        camera.requestInterruption()
        camera.wait(CAMERA_STOP_WAIT_MS)
        self._on_camera_finished(camera)

    def hideEvent(self, event: QHideEvent) -> None:
        self.stop_camera()  # never leave the webcam on when the page isn't visible
        super().hideEvent(event)

    def _show_frame(self, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image).scaled(
            *CAMERA_VIEW_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )  # fmt: skip
        self.camera_view.setPixmap(pixmap)

    def _on_camera_codes(self, codes: list[str]) -> None:
        self.show_payloads(codes)

    def _on_camera_failed(self, message: str) -> None:
        self.banner.show_error(message)

    def _on_camera_finished(self, camera: CameraScanner) -> None:
        if camera is not self._camera:
            return
        self._camera = None
        camera.deleteLater()
        self.camera_view.hide()
        self.camera_view.clear()
        self.camera_hint.hide()
        self.camera_button.setText("Scan with webcam")

    # ---- results --------------------------------------------------------------------

    def show_payloads(self, payloads: list[str] | tuple[str, ...]) -> None:
        self.reports = [analyse(payload) for payload in payloads]
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        for report in self.reports:
            self.results_layout.addWidget(ReportCard(report))
        if len(self.reports) > 1:
            self.banner.show_success(f"Found {len(self.reports)} QR codes in this picture.")


class ReportCard(QFrame):
    """One checked code: verdict, what it does, details and the warning signs found."""

    def __init__(self, report: QrReport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.report = report
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        level, icon = VERDICT_STYLE[report.verdict]
        self.verdict_label = QLabel(f"{icon}  {report.verdict.value}")
        set_style_property(self.verdict_label, "verdict", level)
        self.verdict_label.setAccessibleName(f"Result: {report.verdict.value}")
        summary = QLabel(f"{report.kind.value}: {report.summary}")
        summary.setProperty("role", "section")
        summary.setWordWrap(True)
        layout.addWidget(self.verdict_label)
        layout.addWidget(summary)

        if report.details:
            details = QWidget()
            details_form = QFormLayout(details)
            details_form.setContentsMargins(0, 0, 0, 0)
            for label, value in report.details:
                details_form.addRow(f"{label}:", _value_widget(value))
            layout.addWidget(details)

        for finding in report.findings:
            text = finding.message
            prefix = "" if text.startswith("✓") else f"{SEVERITY_ICON[finding.severity]}  "
            line = QLabel(prefix + text)
            line.setWordWrap(True)
            if finding.severity is not Severity.INFO:
                line.setProperty(
                    "severity", "danger" if finding.severity is Severity.DANGER else "caution"
                )
            layout.addWidget(line)

        copy = QPushButton("Copy what the code contains")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(report.payload))
        layout.addWidget(copy, alignment=Qt.AlignmentFlag.AlignLeft)


def _value_widget(value: str) -> QWidget:
    if len(value) > LONG_VALUE_CHARS:
        field = QLineEdit(value)  # scrollable, so long links don't stretch the page
        field.setReadOnly(True)
        field.setCursorPosition(0)
        return field
    label = QLabel(value)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    return label


def _decode_file(path: Path, *, on_progress: object = None) -> tuple[str, ...]:
    return decode_qr_file(path)


def _decode_image(image: Image.Image, *, on_progress: object = None) -> tuple[str, ...]:
    return decode_qr_codes(image)
