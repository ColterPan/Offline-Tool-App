"""Errors raised by tools. `user_message` is shown in the UI; `detail` goes to the log."""


class ToolError(Exception):
    """A failure the user can understand and usually fix (bad file, no permission, ...)."""

    def __init__(self, user_message: str, detail: str | None = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail or user_message


class InvalidInputError(ToolError):
    """The input file or value cannot be processed."""


class OutputError(ToolError):
    """The result could not be written."""
