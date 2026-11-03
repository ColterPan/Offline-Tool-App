"""Home screen: search box plus a card for every tool, grouped by category."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from offline_tools.registry import Tool, ToolRegistry
from offline_tools.ui.widgets.tool_page import ToolPage

COLUMNS = 3
CARD_MIN_WIDTH = 200
CARD_MIN_HEIGHT = 108
UPCOMING_TOOLS = "PDF compress & merge, image convert, HEIC → JPG, Excel ↔ CSV, QR codes"


class ToolCard(QPushButton):
    def __init__(self, tool: Tool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tool = tool
        self.setObjectName("ToolCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(CARD_MIN_WIDTH, CARD_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(tool.name)
        self.setAccessibleDescription(tool.summary)
        self.setToolTip(tool.summary)

        name = QLabel(tool.name)
        name.setProperty("role", "section")
        summary = QLabel(tool.summary)
        summary.setProperty("role", "muted")
        summary.setWordWrap(True)

        layout = QVBoxLayout(self)
        for label in (name, summary):
            # Let clicks fall through to the button underneath.
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(label)
        layout.addStretch()


class _Section:
    def __init__(self, title: str, tools: tuple[Tool, ...]) -> None:
        self.header = QLabel(title)
        self.header.setProperty("role", "section")
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self.cards = [ToolCard(tool) for tool in tools]

    def show_matching(self, query: str) -> int:
        """Re-lay out the cards that match, hide the rest, and return how many are shown."""
        for card in self.cards:
            self.grid.removeWidget(card)
            card.hide()
        visible = [card for card in self.cards if card.tool.matches(query)]
        for index, card in enumerate(visible):
            self.grid.addWidget(card, index // COLUMNS, index % COLUMNS)
            card.show()
        self.header.setVisible(bool(visible))
        self.container.setVisible(bool(visible))
        return len(visible)


class HomePage(ToolPage):
    tool_requested = Signal(str)

    def __init__(self, registry: ToolRegistry, parent: QWidget | None = None) -> None:
        super().__init__(
            "What do you want to do?",
            "Everything runs on this computer. Your files are never uploaded.",
            parent,
        )
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search tools, e.g. pdf, compress, qr")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search tools")
        self.search.textChanged.connect(self.filter)
        self.add_content(self.search)

        self._sections = [
            _Section(category.value, tools) for category, tools in registry.by_category().items()
        ]
        for section in self._sections:
            for card in section.cards:
                card.clicked.connect(lambda _=False, tid=card.tool.id: self.tool_requested.emit(tid))
            self.add_content(section.header)
            self.add_content(section.container)

        self.empty_label = QLabel("No tools match your search yet.")
        self.empty_label.setProperty("role", "muted")
        self.add_content(self.empty_label)

        upcoming = QLabel(f"Coming soon: {UPCOMING_TOOLS}.")
        upcoming.setProperty("role", "muted")
        upcoming.setWordWrap(True)
        self.add_content(upcoming)

        self.filter("")

    def filter(self, query: str) -> None:
        shown = sum(section.show_matching(query) for section in self._sections)
        self.empty_label.setVisible(shown == 0)

    def visible_tool_ids(self) -> list[str]:
        return [
            card.tool.id for section in self._sections for card in section.cards if not card.isHidden()
        ]
