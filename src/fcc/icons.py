"""Vector icon set rendered on demand with the active palette colours.

Every icon is a 24x24 stroke drawing, so a single code path produces crisp
QIcons at any size and recolouring on theme switch is free.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

ICONS: Dict[str, str] = {
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "folder": '<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4.2l1.8 2h9A1.5 1.5 0 0 1 21 9.5v8A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5z"/>',
    "folder_plus": '<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4.2l1.8 2h9A1.5 1.5 0 0 1 21 9.5v8A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5z"/><path d="M12 11v5M9.5 13.5h5"/>',
    "folder_open": '<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4.2l1.8 2h9A1.5 1.5 0 0 1 21 9.5V11H3z"/><path d="M3 11h18l-2.2 6.4a1.5 1.5 0 0 1-1.4 1.1H4.6a1.5 1.5 0 0 1-1.4-1.1z"/>',
    "chat": '<path d="M20 4H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3v4l4.5-4H20a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z"/>',
    "chats": '<path d="M8 5h11a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-6l-4 3.5V16H8a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/><path d="M4 9v8a2 2 0 0 0 2 2"/>',
    "settings": '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.2 5.2l2.1 2.1M16.7 16.7l2.1 2.1M18.8 5.2l-2.1 2.1M7.3 16.7l-2.1 2.1"/>',
    "activity": '<path d="M2.5 12.5h4l3 7.5 5-16 3 8.5h4"/>',
    "package": '<path d="M12 2.8l8.5 4.7v9L12 21.2l-8.5-4.7v-9z"/><path d="M3.5 7.5L12 12.2l8.5-4.7M12 12.2v9"/>',
    "trash": '<path d="M4 7h16M9.5 7V4.8h5V7M6.5 7l1 13h9l1-13M10 11v6M14 11v6"/>',
    "chevron_down": '<path d="M6 9.5l6 6 6-6"/>',
    "chevron_up": '<path d="M6 14.5l6-6 6 6"/>',
    "chevron_right": '<path d="M9.5 5.5l6.5 6.5-6.5 6.5"/>',
    "chevron_left": '<path d="M14.5 5.5L8 12l6.5 6.5"/>',
    "send": '<path d="M12 20V4.5M5.5 11L12 4.5 18.5 11"/>',
    "stop": '<rect x="6.5" y="6.5" width="11" height="11" rx="2.4"/>',
    "copy": '<rect x="8.5" y="8.5" width="12" height="12" rx="2.2"/><path d="M5.5 15.5H4.8a1.3 1.3 0 0 1-1.3-1.3V4.8a1.3 1.3 0 0 1 1.3-1.3h9.4a1.3 1.3 0 0 1 1.3 1.3v.7"/>',
    "check": '<path d="M4.5 12.5l5 5L19.5 6.5"/>',
    "check_circle": '<circle cx="12" cy="12" r="9"/><path d="M8 12.3l2.8 2.8L16.2 9.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "x_circle": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "terminal": '<rect x="2.8" y="4" width="18.4" height="16" rx="2.4"/><path d="M6.8 9.2l3 2.8-3 2.8M12.8 15h4.4"/>',
    "file": '<path d="M14 3H7.2A2.2 2.2 0 0 0 5 5.2v13.6A2.2 2.2 0 0 0 7.2 21h9.6a2.2 2.2 0 0 0 2.2-2.2V8z"/><path d="M13.8 3v5.2H19"/>',
    "file_text": '<path d="M14 3H7.2A2.2 2.2 0 0 0 5 5.2v13.6A2.2 2.2 0 0 0 7.2 21h9.6a2.2 2.2 0 0 0 2.2-2.2V8z"/><path d="M13.8 3v5.2H19M8.5 13h7M8.5 16.5h5"/>',
    "pencil": '<path d="M4 20.2h4.1L19 9.3a2.2 2.2 0 0 0 0-3.1l-1.2-1.2a2.2 2.2 0 0 0-3.1 0L3.8 16z"/><path d="M13.6 6.4l4 4"/>',
    "search": '<circle cx="10.8" cy="10.8" r="6.4"/><path d="M15.6 15.6L21 21"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3.2 12h17.6M12 3c2.9 3.6 2.9 14.4 0 18M12 3c-2.9 3.6-2.9 14.4 0 18"/>',
    "agent": '<rect x="3.5" y="7.5" width="17" height="12.5" rx="3.4"/><path d="M12 3.2v4.3"/><circle cx="9" cy="13.4" r="1.2"/><circle cx="15" cy="13.4" r="1.2"/><path d="M9.6 17.2h4.8"/>',
    "list": '<path d="M8.5 6.2h12M8.5 12h12M8.5 17.8h12"/><path d="M3.6 5.4l1.3 1.3 2.2-2.4M3.6 11.2l1.3 1.3 2.2-2.4M3.6 17l1.3 1.3 2.2-2.4"/>',
    "shield": '<path d="M12 2.8l8.2 3.1v6.3c0 5-3.5 8.2-8.2 9.2-4.7-1-8.2-4.2-8.2-9.2V5.9z"/><path d="M8.8 12.2l2.3 2.3 4.1-4.4"/>',
    "shield_alert": '<path d="M12 2.8l8.2 3.1v6.3c0 5-3.5 8.2-8.2 9.2-4.7-1-8.2-4.2-8.2-9.2V5.9z"/><path d="M12 8v4.4M12 15.6h.01"/>',
    "lock": '<rect x="4.6" y="10.6" width="14.8" height="9.8" rx="2.4"/><path d="M8.2 10.6V7.8a3.8 3.8 0 0 1 7.6 0v2.8"/>',
    "unlock": '<rect x="4.6" y="10.6" width="14.8" height="9.8" rx="2.4"/><path d="M8.2 10.6V7.8a3.8 3.8 0 0 1 7.3-1.4"/>',
    "key": '<circle cx="8.4" cy="15.6" r="4.4"/><path d="M11.8 12.4L20 4.2M17.2 7l2.2 2.2"/>',
    "refresh": '<path d="M20.4 12a8.4 8.4 0 1 1-2.6-6.1"/><path d="M20.6 4v4.6H16"/>',
    "moon": '<path d="M20.5 14.6A8.6 8.6 0 0 1 9.4 3.5a8.6 8.6 0 1 0 11.1 11.1z"/>',
    "sun": '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.4v2.4M12 19.2v2.4M2.4 12h2.4M19.2 12h2.4M5.1 5.1l1.7 1.7M17.2 17.2l1.7 1.7M18.9 5.1l-1.7 1.7M6.8 17.2l-1.7 1.7"/>',
    "warning": '<path d="M12 3.6l9.2 16.2H2.8z"/><path d="M12 9.6v4.4M12 17.2h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11.2v6M12 7.8h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 6.8V12l3.4 2.1"/>',
    "download": '<path d="M12 3.4v11.8M7.2 10.6L12 15.4l4.8-4.8M4.2 20.6h15.6"/>',
    "upload": '<path d="M12 15.6V3.8M7.2 8.6L12 3.8l4.8 4.8M4.2 20.6h15.6"/>',
    "external": '<path d="M14 3.8h6.2V10M20.2 3.8L11.4 12.6"/><path d="M18 14.2v5A1.8 1.8 0 0 1 16.2 21H4.8A1.8 1.8 0 0 1 3 19.2V7.8A1.8 1.8 0 0 1 4.8 6h5"/>',
    "play": '<path d="M7.2 4.4l12 7.6-12 7.6z"/>',
    "git_branch": '<circle cx="6.8" cy="5.6" r="2.6"/><circle cx="6.8" cy="18.4" r="2.6"/><circle cx="17.4" cy="9.4" r="2.6"/><path d="M6.8 8.2v7.6M17.4 12c0 3-2.8 3.8-5.6 4.4"/>',
    "image": '<rect x="3.2" y="4.6" width="17.6" height="14.8" rx="2.4"/><circle cx="8.6" cy="10" r="1.7"/><path d="M4 17.4l4.6-4.4 3.6 3.4 3-2.4 4.8 4.4"/>',
    "clip": '<path d="M20.4 11.2l-8.2 8.2a4.8 4.8 0 0 1-6.8-6.8l8.6-8.6a3.2 3.2 0 0 1 4.6 4.6l-8.6 8.6a1.7 1.7 0 0 1-2.4-2.4l7.9-7.9"/>',
    "sparkles": '<path d="M11.4 3.2l1.9 4.9 4.9 1.9-4.9 1.9-1.9 4.9-1.9-4.9-4.9-1.9 4.9-1.9z"/><path d="M18.2 15.4l.9 2.2 2.2.9-2.2.9-.9 2.2-.9-2.2-2.2-.9 2.2-.9z"/>',
    "brain": '<path d="M9.4 3.8A3 3 0 0 0 6.4 7a3 3 0 0 0-1.4 5.4A3.2 3.2 0 0 0 8 18.2a3 3 0 0 0 4 .4V6.2a3 3 0 0 0-2.6-2.4z"/><path d="M14.6 3.8A3 3 0 0 1 17.6 7a3 3 0 0 1 1.4 5.4 3.2 3.2 0 0 1-3 5.8 3 3 0 0 1-4 .4"/>',
    "wrench": '<path d="M20.6 6.4a5.2 5.2 0 0 1-6.9 6.9L6.3 20.7a2.2 2.2 0 0 1-3.1-3.1l7.4-7.4a5.2 5.2 0 0 1 6.9-6.9l-3 3 2.4 2.4z"/>',
    "diff": '<path d="M7 3.6v9.8M3.6 7h6.8"/><path d="M17 11.6v9.8M13.6 20h6.8"/>',
    "eye": '<path d="M2.4 12S6.2 5.8 12 5.8 21.6 12 21.6 12 17.8 18.2 12 18.2 2.4 12 2.4 12z"/><circle cx="12" cy="12" r="3.1"/>',
    "layers": '<path d="M12 3.2l9 4.8-9 4.8-9-4.8z"/><path d="M3.4 12.6L12 17.2l8.6-4.6M3.4 16.9L12 21.5l8.6-4.6"/>',
    "home": '<path d="M3.8 11.2L12 4l8.2 7.2v8a1.6 1.6 0 0 1-1.6 1.6h-3.8v-6.4H9.2v6.4H5.4a1.6 1.6 0 0 1-1.6-1.6z"/>',
    "more": '<circle cx="5.6" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="18.4" cy="12" r="1.7"/>',
    "bell": '<path d="M6.2 9.6a5.8 5.8 0 1 1 11.6 0c0 4.6 1.9 5.7 1.9 5.7H4.3s1.9-1.1 1.9-5.7z"/><path d="M10.2 19.2a2 2 0 0 0 3.6 0"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4.4 20.8c0-3.9 3.4-6 7.6-6s7.6 2.1 7.6 6"/>',
    "zap": '<path d="M13.4 2.4L4.8 14.2h5.6l-1 7.4 8.8-12h-5.8z"/>',
    "cube": '<path d="M12 2.6l8.8 4.8v9.2L12 21.4 3.2 16.6V7.4z"/><path d="M3.4 7.5L12 12.2l8.6-4.7M12 12.2v9.2"/>',
    "book": '<path d="M4.4 4.6A1.8 1.8 0 0 1 6.2 3H20v15.4H6.2a1.8 1.8 0 0 0-1.8 1.8z"/><path d="M4.4 18.4A1.8 1.8 0 0 0 6.2 21H20"/><path d="M8.6 7.4h7.2M8.6 11h5"/>',
    "database": '<ellipse cx="12" cy="5.8" rx="8" ry="3"/><path d="M4 5.8v12.4c0 1.7 3.6 3 8 3s8-1.3 8-3V5.8"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "cpu": '<rect x="6.4" y="6.4" width="11.2" height="11.2" rx="2"/><rect x="9.8" y="9.8" width="4.4" height="4.4" rx="1"/><path d="M9.4 3v3.4M14.6 3v3.4M9.4 17.6V21M14.6 17.6V21M3 9.4h3.4M3 14.6h3.4M17.6 9.4H21M17.6 14.6H21"/>',
    "compass": '<circle cx="12" cy="12" r="9"/><path d="M15.6 8.4l-2 5.2-5.2 2 2-5.2z"/>',
    "sliders": '<path d="M4 7h10M18 7h2M4 17h4M12 17h8"/><circle cx="16" cy="7" r="2.2"/><circle cx="10" cy="17" r="2.2"/>',
    "sidebar": '<rect x="3" y="4.4" width="18" height="15.2" rx="2.4"/><path d="M9.4 4.4v15.2"/>',
    "expand": '<path d="M9 3.6H3.6V9M15 20.4h5.4V15M20.4 9V3.6H15M3.6 15v5.4H9"/>',
    "minimize": '<path d="M4 14h6v6M20 10h-6V4M14 10l6-6M10 14l-6 6"/>',
    "filter": '<path d="M3.6 5.4h16.8l-6.6 7.6v6l-3.6 1.8v-7.8z"/>',
    "log": '<path d="M5 3.6h9.4L19 8.2v12.2H5z"/><path d="M14 3.6v5h5M8 13h8M8 16.6h5"/>',
    "link": '<path d="M10.2 13.8a4 4 0 0 0 5.7 0l2.8-2.8a4 4 0 1 0-5.7-5.7l-1.4 1.4"/><path d="M13.8 10.2a4 4 0 0 0-5.7 0l-2.8 2.8a4 4 0 1 0 5.7 5.7l1.4-1.4"/>',
    "target": '<circle cx="12" cy="12" r="8.6"/><circle cx="12" cy="12" r="4.6"/><circle cx="12" cy="12" r="1"/>',
}


def spark_svg(color: str, rays: int = 12, outer: float = 10.4, inner: float = 2.5, width: float = 2.35) -> str:
    """The Claude-style sunburst mark, generated as a rounded stroke path."""
    points = []
    for i in range(rays):
        angle = math.radians(i * (360.0 / rays) - 90.0)
        points.append((12 + outer * math.cos(angle), 12 + outer * math.sin(angle)))
        mid = math.radians((i + 0.5) * (360.0 / rays) - 90.0)
        points.append((12 + inner * math.cos(mid), 12 + inner * math.sin(mid)))
    d = "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in points) + " Z"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


def _svg_for(name: str, color: str, stroke_width: float = 1.85) -> str:
    if name in ("spark", "claude", "logo"):
        return spark_svg(color)
    body = ICONS.get(name, ICONS["info"])
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )


_CACHE: Dict[tuple, object] = {}


def svg_text(name: str, color: str) -> str:
    return _svg_for(name, color)


def icon(name: str, color: str, size: int = 20, stroke_width: float = 1.85):
    """Return a cached QIcon rendered from the SVG set."""
    from PySide6.QtCore import QByteArray, QSize, Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    key = (name, color, size, stroke_width)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    svg = _svg_for(name, color, stroke_width)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    icon_obj = QIcon()
    for scale in (1, 2):
        pix_size = size * scale
        pixmap = QPixmap(QSize(pix_size, pix_size))
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        renderer.render(painter)
        painter.end()
        icon_obj.addPixmap(pixmap)
    _CACHE[key] = icon_obj
    return icon_obj


def pixmap(name: str, color: str, size: int = 20, stroke_width: float = 1.85):
    from PySide6.QtCore import QByteArray, QSize, Qt
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    svg = _svg_for(name, color, stroke_width)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return pixmap


def clear_cache() -> None:
    _CACHE.clear()


def app_logo_icon(color: str = "#D97757", size: int = 64):
    return icon("spark", color, size=size, stroke_width=2.2)


def tool_icon_name(tool: str) -> str:
    """Map a Claude Code tool name to an icon from the set."""
    t = (tool or "").lower()
    table = {
        "bash": "terminal",
        "shell": "terminal",
        "powershell": "terminal",
        "write": "pencil",
        "edit": "diff",
        "multiedit": "diff",
        "notebookedit": "diff",
        "read": "file_text",
        "view": "file_text",
        "glob": "search",
        "grep": "filter",
        "search": "search",
        "toolsearch": "search",
        "webfetch": "globe",
        "websearch": "globe",
        "task": "agent",
        "agent": "agent",
        "todowrite": "list",
        "todoread": "list",
        "exitplanmode": "compass",
        "enterplanmode": "compass",
        "workflow": "layers",
        "skill": "sparkles",
        "sendmessage": "chat",
        "askuserquestion": "chat",
        "reportfindings": "warning",
        "monitor": "activity",
        "enterworktree": "git_branch",
        "exitworktree": "git_branch",
        "taskcreate": "cube",
        "taskupdate": "cube",
        "tasklist": "cube",
        "taskget": "cube",
        "taskstop": "stop",
        "croncreate": "clock",
        "cronlist": "clock",
        "crondelete": "clock",
        "schedulewakeup": "clock",
        "designsync": "image",
        "listagents": "agent",
        "listmcpresources": "database",
        "readmcpresource": "database",
        "mcp": "database",
    }
    if t in table:
        return table[t]
    if t.startswith("mcp__"):
        return "cube"
    return "wrench"


def optional(name: str, color: str, size: int = 20) -> Optional[object]:
    try:
        return icon(name, color, size)
    except Exception:
        return None
