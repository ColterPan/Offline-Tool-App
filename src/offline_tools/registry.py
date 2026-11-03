"""The list of tools the app offers. Sidebar, home screen and search are all built from it."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from offline_tools.ui.context import AppContext


class Category(StrEnum):
    """Sidebar sections, shown in this order."""

    PRIVACY = "Privacy & safety"
    PDF = "PDF"
    IMAGES = "Images"
    DATA = "Data"
    EVERYDAY = "Everyday"


type PageFactory = Callable[[AppContext], QWidget]


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    summary: str
    category: Category
    page_factory: PageFactory
    keywords: tuple[str, ...] = ()

    def matches(self, query: str) -> bool:
        """True if every word of the query appears in the name, summary, category or keywords."""
        words = query.lower().split()
        haystack = " ".join((self.name, self.summary, self.category.value, *self.keywords)).lower()
        return all(word in haystack for word in words)


class ToolRegistry:
    """Read-only collection of tools, in registration order."""

    def __init__(self, tools: Iterable[Tool]) -> None:
        self._tools = tuple(tools)
        ids = [tool.id for tool in self._tools]
        duplicates = sorted({tool_id for tool_id in ids if ids.count(tool_id) > 1})
        if duplicates:
            raise ValueError(f"Duplicate tool ids: {duplicates}")
        self._by_id = {tool.id: tool for tool in self._tools}

    def __len__(self) -> int:
        return len(self._tools)

    def all(self) -> tuple[Tool, ...]:
        return self._tools

    def get(self, tool_id: str) -> Tool:
        return self._by_id[tool_id]

    def search(self, query: str) -> tuple[Tool, ...]:
        return tuple(tool for tool in self._tools if tool.matches(query))

    def by_category(self) -> dict[Category, tuple[Tool, ...]]:
        """Tools grouped by category, in Category order, skipping empty categories."""
        grouped = {cat: tuple(t for t in self._tools if t.category is cat) for cat in Category}
        return {cat: tools for cat, tools in grouped.items() if tools}
