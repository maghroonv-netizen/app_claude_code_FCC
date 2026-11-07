"""Single source of truth for product identity and version."""

APP_NAME = "Claude Code Studio"
APP_SHORT = "FCC"
ORG_NAME = "FCC"
APP_ID = "claude-code-studio"

__version__ = "1.0.0"
__build__ = "release"


def full_version() -> str:
    return f"{__version__}"
