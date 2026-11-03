import pytest
from PySide6.QtWidgets import QLabel, QWidget

from offline_tools.registry import Category, Tool, ToolRegistry
from offline_tools.ui.context import AppContext
from offline_tools.ui.tools import ALL_TOOLS


def _page(_context: AppContext) -> QWidget:
    return QLabel("page")


def _tool(tool_id: str, category: Category = Category.PDF, **kwargs: object) -> Tool:
    return Tool(
        id=tool_id,
        name=str(kwargs.get("name", tool_id.title())),
        summary=str(kwargs.get("summary", "does a thing")),
        category=category,
        page_factory=_page,
        keywords=tuple(kwargs.get("keywords", ())),  # type: ignore[arg-type]
    )


def test_registry_keeps_registration_order() -> None:
    registry = ToolRegistry([_tool("b"), _tool("a")])

    assert [t.id for t in registry.all()] == ["b", "a"]
    assert len(registry) == 2


def test_registry_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="Duplicate tool ids"):
        ToolRegistry([_tool("same"), _tool("same")])


def test_get_unknown_tool_raises_key_error() -> None:
    with pytest.raises(KeyError):
        ToolRegistry([]).get("missing")


def test_by_category_follows_enum_order_and_skips_empty() -> None:
    registry = ToolRegistry([_tool("qr", Category.EVERYDAY), _tool("merge", Category.PDF)])

    grouped = registry.by_category()

    assert list(grouped) == [Category.PDF, Category.EVERYDAY]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ["merge", "qr"]),
        ("PDF", ["merge"]),
        ("code", ["qr"]),
        ("wifi qr", ["qr"]),
        ("wifi pdf", []),
    ],
)
def test_search_matches_name_summary_category_and_keywords(query: str, expected: list[str]) -> None:
    registry = ToolRegistry(
        [
            _tool("merge", Category.PDF, name="Merge PDF"),
            _tool("qr", Category.EVERYDAY, name="QR Code", keywords=("wifi",)),
        ]
    )

    assert [t.id for t in registry.search(query)] == expected


def test_shipped_tools_have_unique_ids_and_summaries() -> None:
    registry = ToolRegistry(ALL_TOOLS)

    assert len(registry) >= 1
    assert all(tool.summary.strip() for tool in registry.all())
