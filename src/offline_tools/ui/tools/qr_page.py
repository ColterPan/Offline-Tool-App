"""QR Code Generator: links/text, Wi-Fi logins and contact cards, with live preview."""

import re
from enum import StrEnum
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from offline_tools.core.errors import ToolError
from offline_tools.core.qr import (
    ContactDetails,
    ErrorCorrection,
    WifiDetails,
    WifiSecurity,
    make_qr,
    make_qr_svg,
    save_png,
    save_svg,
    vcard_payload,
    wifi_payload,
)
from offline_tools.settings import AppSettings, OutputMode
from offline_tools.ui.context import AppContext
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.forms import combo, form
from offline_tools.ui.widgets.pixmaps import pil_to_pixmap
from offline_tools.ui.widgets.tool_page import ToolPage

PREVIEW_PX = 240
PREVIEW_DELAY_MS = 200
TEXT_BOX_HEIGHT = 110
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")


class QrContent(StrEnum):
    TEXT = "text"
    WIFI = "wifi"
    CONTACT = "contact"


CONTENT_OPTIONS = (
    ("Link or text", QrContent.TEXT),
    ("Wi-Fi login (guests scan to join)", QrContent.WIFI),
    ("Contact card", QrContent.CONTACT),
)
SIZE_OPTIONS = (
    ("Small (300 px)", 300),
    ("Medium (600 px)", 600),
    ("Large (1200 px)", 1200),
    ("Print (2000 px)", 2000),
)
ERROR_CORRECTION_OPTIONS = (
    ("Medium (recommended)", ErrorCorrection.MEDIUM),
    ("Low: smallest code", ErrorCorrection.LOW),
    ("Quartile", ErrorCorrection.QUARTILE),
    ("High: still scans if partly covered", ErrorCorrection.HIGH),
)
SECURITY_OPTIONS = (
    ("WPA / WPA2 / WPA3 (most networks)", WifiSecurity.WPA),
    ("WEP (old routers)", WifiSecurity.WEP),
    ("No password", WifiSecurity.NONE),
)


class QrPage(ToolPage):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(
            "QR Code Generator",
            "Turn a link, some text, a Wi-Fi login or a contact card into a QR code that phone "
            "cameras can scan. Nothing you type leaves this computer.",
            parent,
        )
        self._settings = context.settings
        self.image: Image.Image | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(PREVIEW_DELAY_MS)
        self._timer.timeout.connect(self.refresh_preview)

        columns = QWidget()
        row = QHBoxLayout(columns)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        left = QVBoxLayout()
        left.addWidget(self._build_content_card())
        left.addWidget(self._build_options_card())
        left.addStretch()
        row.addLayout(left, stretch=3)
        row.addWidget(self._build_preview_card(), stretch=2, alignment=Qt.AlignmentFlag.AlignTop)
        self.add_content(columns)
        self.refresh_preview()

    # ---- building ---------------------------------------------------------------

    def _build_content_card(self) -> Card:
        card = Card("What should it contain?")
        self.content_combo = combo(CONTENT_OPTIONS, accessible_name="QR code content type")
        self.content_combo.currentIndexChanged.connect(self._on_content_changed)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("https://example.com, or any text")
        self.text_edit.setFixedHeight(TEXT_BOX_HEIGHT)
        self.text_edit.setAccessibleName("Link or text")

        self.ssid_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_password = QCheckBox("Show password")
        self.show_password.toggled.connect(
            lambda shown: self.password_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
            )
        )
        self.security_combo = combo(SECURITY_OPTIONS, accessible_name="Security")
        self.hidden_check = QCheckBox("Hidden network")
        wifi_form = form(
            ("Network name:", self.ssid_edit),
            ("Password:", self.password_edit),
            ("", self.show_password),
            ("Security:", self.security_combo),
            ("", self.hidden_check),
        )

        self.name_edit, self.phone_edit, self.email_edit = QLineEdit(), QLineEdit(), QLineEdit()
        self.org_edit, self.website_edit = QLineEdit(), QLineEdit()
        contact_form = form(
            ("Name:", self.name_edit),
            ("Mobile:", self.phone_edit),
            ("Email:", self.email_edit),
            ("Company:", self.org_edit),
            ("Website:", self.website_edit),
        )

        self.forms = QStackedWidget()
        for widget in (self.text_edit, wifi_form, contact_form):
            self.forms.addWidget(widget)

        self.text_edit.textChanged.connect(self._schedule_preview)
        for edit in (self.ssid_edit, self.password_edit, self.name_edit, self.phone_edit,
                     self.email_edit, self.org_edit, self.website_edit):  # fmt: skip
            edit.textChanged.connect(self._schedule_preview)
        self.security_combo.currentIndexChanged.connect(self._schedule_preview)
        self.hidden_check.toggled.connect(self._schedule_preview)

        card.add(self.content_combo)
        card.add(self.forms)
        return card

    def _build_options_card(self) -> Card:
        card = Card("Options")
        self.size_combo = combo(SIZE_OPTIONS, accessible_name="Image size")
        self.size_combo.setCurrentIndex(1)
        self.error_combo = combo(ERROR_CORRECTION_OPTIONS, accessible_name="Error correction")
        self.size_combo.currentIndexChanged.connect(self._schedule_preview)
        self.error_combo.currentIndexChanged.connect(self._schedule_preview)
        card.add(form(("Size:", self.size_combo), ("Error correction:", self.error_combo)))
        return card

    def _build_preview_card(self) -> Card:
        card = Card("Preview")
        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW_PX, PREVIEW_PX)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setAccessibleName("QR code preview")
        self.status_label = QLabel()
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        self.save_png_button = QPushButton("Save PNG…")
        self.save_png_button.setProperty("variant", "primary")
        self.save_svg_button = QPushButton("Save SVG…")
        self.copy_button = QPushButton("Copy image")
        self.save_png_button.clicked.connect(lambda: self._save_with_dialog(".png"))
        self.save_svg_button.clicked.connect(lambda: self._save_with_dialog(".svg"))
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        card.add(self.preview)
        card.add(self.status_label)
        for button in (self.save_png_button, self.save_svg_button, self.copy_button):
            card.add(button)
        return card

    # ---- behaviour ----------------------------------------------------------------

    def payload(self) -> str:
        """The text encoded in the QR code. Raises InvalidInputError if a form is incomplete."""
        content = QrContent(self.content_combo.currentData())
        if content is QrContent.WIFI:
            return wifi_payload(
                WifiDetails(
                    ssid=self.ssid_edit.text(),
                    password=self.password_edit.text(),
                    security=WifiSecurity(self.security_combo.currentData()),
                    hidden=self.hidden_check.isChecked(),
                )
            )
        if content is QrContent.CONTACT:
            return vcard_payload(
                ContactDetails(
                    name=self.name_edit.text(),
                    phone=self.phone_edit.text(),
                    email=self.email_edit.text(),
                    organisation=self.org_edit.text(),
                    website=self.website_edit.text(),
                )
            )
        return self.text_edit.toPlainText()

    def refresh_preview(self) -> None:
        self.banner.clear()
        try:
            self.image = make_qr(
                self.payload(),
                size_px=int(self.size_combo.currentData()),
                error_correction=ErrorCorrection(self.error_combo.currentData()),
            )
        except ToolError as exc:
            self.image = None
            self.preview.clear()
            self.status_label.setText(exc.user_message)
        else:
            pixmap = pil_to_pixmap(self.image).scaled(
                PREVIEW_PX,
                PREVIEW_PX,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,  # keep module edges crisp
            )
            self.preview.setPixmap(pixmap)
            self.status_label.setText(f"{self.image.width} × {self.image.height} px")
        self.refresh_state()

    def refresh_state(self) -> None:
        ready = self.image is not None
        for button in (self.save_png_button, self.save_svg_button, self.copy_button):
            button.setEnabled(ready)

    def save_to(self, path: Path) -> None:
        """Save the current code as PNG or SVG depending on the file extension."""
        if self.image is None:
            return
        try:
            if path.suffix.lower() == ".svg":
                markup = make_qr_svg(
                    self.payload(), error_correction=ErrorCorrection(self.error_combo.currentData())
                )
                save_svg(markup, path)
            else:
                save_png(self.image, path)
        except ToolError as exc:
            self.banner.show_error(exc.user_message)
            return
        self.banner.show_success(f'Saved "{path.name}"', folder=path.parent)

    def copy_to_clipboard(self) -> None:
        if self.image is not None:
            QGuiApplication.clipboard().setPixmap(pil_to_pixmap(self.image))
            self.banner.show_success("Copied. Paste it into a document, chat or email.")

    def _save_with_dialog(self, suffix: str) -> None:
        name_filter = "SVG image (*.svg)" if suffix == ".svg" else "PNG image (*.png)"
        suggested = _default_folder(self._settings) / f"{self._suggested_name()}{suffix}"
        chosen, _ = QFileDialog.getSaveFileName(self, "Save QR code", str(suggested), name_filter)
        if chosen:
            path = Path(chosen)
            self.save_to(path if path.suffix else path.with_suffix(suffix))

    def _suggested_name(self) -> str:
        content = QrContent(self.content_combo.currentData())
        if content is QrContent.WIFI and self.ssid_edit.text().strip():
            return f"wifi-{_UNSAFE_NAME.sub('-', self.ssid_edit.text().strip())}"
        if content is QrContent.CONTACT and self.name_edit.text().strip():
            return f"contact-{_UNSAFE_NAME.sub('-', self.name_edit.text().strip())}"
        return "qr-code"

    def _on_content_changed(self, index: int) -> None:
        self.forms.setCurrentIndex(index)
        self.refresh_preview()

    def _schedule_preview(self) -> None:
        self._timer.start()


def _default_folder(settings: AppSettings) -> Path:
    folder = settings.output_folder
    if settings.output_mode is OutputMode.FOLDER and folder is not None and folder.is_dir():
        return folder
    pictures = Path.home() / "Pictures"
    return pictures if pictures.is_dir() else Path.home()
