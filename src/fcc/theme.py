"""Claude-style design tokens and the Qt stylesheet built from them.

The palette mirrors the Claude product: warm cream paper, ink text and the
signature coral accent. Everything is generated at runtime, so light/dark and
accent changes are a single stylesheet swap.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict

CORAL = "#D97757"

ACCENTS: Dict[str, Dict[str, str]] = {
    "coral": {"name": "Claude coral", "base": "#D97757", "dark": "#E08A6D", "hover": "#C56545", "soft_l": "#F7E7DF", "soft_d": "#3B2A22"},
    "clay": {"name": "Burnt clay", "base": "#C15F3C", "dark": "#D2764F", "hover": "#A94F30", "soft_l": "#F5E3DA", "soft_d": "#3A271E"},
    "ember": {"name": "Ember", "base": "#B4462F", "dark": "#CE5F45", "hover": "#9C3A25", "soft_l": "#F4E0D9", "soft_d": "#38221C"},
    "olive": {"name": "Olive ink", "base": "#7A8450", "dark": "#93A05F", "hover": "#68713F", "soft_l": "#EAEEDD", "soft_d": "#2B2F1F"},
    "slate": {"name": "Slate", "base": "#5C6B7A", "dark": "#7E93A8", "hover": "#4B5967", "soft_l": "#E4EAEE", "soft_d": "#22292F"},
}


@dataclass(frozen=True)
class Palette:
    dark: bool
    bg: str
    bg_grad_top: str
    surface: str
    surface_alt: str
    surface_sunken: str
    sidebar: str
    sidebar_item: str
    sidebar_item_hover: str
    sidebar_item_selected: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str
    text_on_accent: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    accent_border: str
    user_bubble: str
    user_bubble_border: str
    claude_bubble: str
    claude_bubble_border: str
    code_bg: str
    code_border: str
    code_text: str
    selection: str
    success: str
    success_soft: str
    warn: str
    warn_soft: str
    danger: str
    danger_soft: str
    info: str
    info_soft: str
    shadow: str
    scrollbar: str
    scrollbar_hover: str
    scrollbar_bg: str
    overlay: str
    font_size: int = 14

    @property
    def mode(self) -> str:
        return "dark" if self.dark else "light"


def _light(accent_key: str = "coral") -> Palette:
    a = ACCENTS.get(accent_key, ACCENTS["coral"])
    return Palette(
        dark=False,
        bg="#FAF9F5",
        bg_grad_top="#FDFCF9",
        surface="#FFFFFF",
        surface_alt="#F3F1EA",
        surface_sunken="#EDEAE1",
        sidebar="#F0EEE6",
        sidebar_item="#F0EEE6",
        sidebar_item_hover="#E7E4DA",
        sidebar_item_selected="#E4DFD3",
        border="#E3E1D8",
        border_strong="#D2CFC4",
        text="#1F1E1B",
        text_muted="#6E6C65",
        text_faint="#9C9A91",
        text_on_accent="#FFFFFF",
        accent=a["base"],
        accent_hover=a["hover"],
        accent_pressed="#A85537",
        accent_soft=a["soft_l"],
        accent_border="#EBC9BB",
        user_bubble="#F0EEE6",
        user_bubble_border="#E0DCD0",
        claude_bubble="#FFFFFF",
        claude_bubble_border="#EAE7DE",
        code_bg="#F5F3EC",
        code_border="#E4E1D7",
        code_text="#33312C",
        selection="#F3D9CE",
        success="#4C8C4A",
        success_soft="#E6F0E3",
        warn="#B4801F",
        warn_soft="#F8EDD6",
        danger="#B3453B",
        danger_soft="#F6E2DF",
        info="#3E6E8E",
        info_soft="#E2EDF3",
        shadow="#1F1E1B",
        scrollbar="#CFCBC0",
        scrollbar_hover="#B4AFA2",
        scrollbar_bg="#F0EEE6",
        overlay="#1F1E1B",
    )


def _dark(accent_key: str = "coral") -> Palette:
    a = ACCENTS.get(accent_key, ACCENTS["coral"])
    return Palette(
        dark=True,
        bg="#1A1917",
        bg_grad_top="#1E1D1A",
        surface="#211F1D",
        surface_alt="#262421",
        surface_sunken="#171614",
        sidebar="#171614",
        sidebar_item="#171614",
        sidebar_item_hover="#221F1D",
        sidebar_item_selected="#2C2825",
        border="#322F2B",
        border_strong="#45423B",
        text="#F0EEE6",
        text_muted="#A8A49A",
        text_faint="#7B776E",
        text_on_accent="#1A1917",
        accent=a["dark"],
        accent_hover="#EFA083",
        accent_pressed="#C4704F",
        accent_soft=a["soft_d"],
        accent_border="#5A3A2C",
        user_bubble="#2A2724",
        user_bubble_border="#3A3733",
        claude_bubble="#211F1D",
        claude_bubble_border="#302D29",
        code_bg="#191817",
        code_border="#302E2A",
        code_text="#E4E1D8",
        selection="#4A3226",
        success="#7FB069",
        success_soft="#23301F",
        warn="#D9A441",
        warn_soft="#322A18",
        danger="#E0796B",
        danger_soft="#362220",
        info="#7FA9C6",
        info_soft="#1E2830",
        shadow="#000000",
        scrollbar="#3D3A35",
        scrollbar_hover="#524E47",
        scrollbar_bg="#1A1917",
        overlay="#000000",
    )


def palette_for(mode: str, accent: str = "coral") -> Palette:
    if mode == "dark":
        return _dark(accent)
    if mode == "light":
        return _light(accent)
    return _dark(accent) if system_is_dark() else _light(accent)


def system_is_dark() -> bool:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication

        hints = QGuiApplication.styleHints()
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    return False


def with_accent(palette: Palette, accent_key: str) -> Palette:
    base = palette_for(palette.mode, accent_key)
    return replace(palette, **{f: getattr(base, f) for f in ("accent", "accent_hover", "accent_pressed", "accent_soft", "accent_border")})


def with_font_size(palette: Palette, font_size: int) -> Palette:
    return replace(palette, font_size=int(font_size))


# --------------------------------------------------------------------------- #
# Stylesheet
# --------------------------------------------------------------------------- #

FONT_UI = "Inter, 'Segoe UI Variable Text', 'Segoe UI', 'Noto Sans Arabic', 'Vazirmatn', 'Noto Sans', Ubuntu, Cantarell, sans-serif"
FONT_MONO = "'Cascadia Mono', 'JetBrains Mono', 'Fira Code', Consolas, 'SF Mono', Menlo, monospace"


def _radius(scale: float = 1.0) -> Dict[str, int]:
    return {
        "xs": int(6 * scale),
        "sm": int(10 * scale),
        "md": int(14 * scale),
        "lg": int(18 * scale),
        "xl": int(26 * scale),
        "pill": 999,
    }


def build_qss(p: Palette, font_size: int = 14, radius_scale: float = 1.0) -> str:
    r = _radius(radius_scale)
    fs = font_size
    small = max(10, fs - 2)
    tiny = max(9, fs - 3)
    big = fs + 2

    return f"""
/* ===== base ===== */
* {{
    font-family: {FONT_UI};
    font-size: {fs}px;
    outline: none;
}}
QMainWindow, QDialog {{ background-color: {p.bg}; color: {p.text}; }}
QWidget {{ background: transparent; color: {p.text}; selection-background-color: {p.selection};
           selection-color: {p.text}; }}
QLabel {{ background: transparent; color: {p.text}; }}
QLabel[muted="true"] {{ color: {p.text_muted}; }}
QLabel[faint="true"] {{ color: {p.text_faint}; font-size: {small}px; }}
QLabel[accent="true"] {{ color: {p.accent}; font-weight: 600; }}
QLabel[h1="true"] {{ font-size: {fs + 10}px; font-weight: 700; letter-spacing: -0.2px; }}
QLabel[h2="true"] {{ font-size: {fs + 5}px; font-weight: 700; }}
QLabel[h3="true"] {{ font-size: {big}px; font-weight: 650; }}
QLabel[mono="true"] {{ font-family: {FONT_MONO}; font-size: {small}px; }}
QLabel#SectionTitle {{ color: {p.text_faint}; font-size: {tiny}px; font-weight: 700; letter-spacing: 1.1px; }}

/* ===== frames & cards ===== */
QFrame#Card, QFrame[card="true"] {{
    background-color: {p.surface};
    border: 1px solid {p.border};
    border-radius: {r['lg']}px;
}}
QFrame#SunkenCard {{
    background-color: {p.surface_sunken};
    border: 1px solid {p.border};
    border-radius: {r['md']}px;
}}
QFrame#Divider {{ background-color: {p.border}; border: none; max-height: 1px; min-height: 1px; }}
QFrame#Sidebar {{ background-color: {p.sidebar}; border: none; border-right: 1px solid {p.border}; }}
QFrame#TopBar {{ background-color: {p.bg}; border: none; border-bottom: 1px solid {p.border}; }}
QFrame#ComposerBar {{ background-color: {p.bg}; border: none; border-top: 1px solid {p.border}; }}
QFrame#StatusBar {{ background-color: {p.bg}; border: none; border-top: 1px solid {p.border}; }}
QFrame[badge="true"] {{
    background-color: {p.accent_soft};
    border: 1px solid {p.accent_border};
    border-radius: {r['pill']}px;
}}
QLabel[badgeText="true"] {{ color: {p.accent}; font-size: {tiny}px; font-weight: 700; background: transparent; }}

/* ===== buttons ===== */
QPushButton {{
    background-color: {p.surface};
    border: 1px solid {p.border_strong};
    border-radius: {r['md']}px;
    padding: 8px 16px;
    color: {p.text};
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {p.surface_alt}; border-color: {p.text_faint}; }}
QPushButton:pressed {{ background-color: {p.surface_sunken}; }}
QPushButton:disabled {{ color: {p.text_faint}; border-color: {p.border}; background-color: {p.surface_alt}; }}
QPushButton:focus {{ border-color: {p.accent}; }}

QPushButton#Primary, QPushButton[primary="true"] {{
    background-color: {p.accent};
    border: 1px solid {p.accent};
    color: {p.text_on_accent};
    padding: 9px 20px;
    font-weight: 650;
}}
QPushButton#Primary:hover, QPushButton[primary="true"]:hover {{ background-color: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton#Primary:pressed, QPushButton[primary="true"]:pressed {{ background-color: {p.accent_pressed}; }}
QPushButton#Primary:disabled, QPushButton[primary="true"]:disabled {{
    background-color: {p.surface_alt}; border-color: {p.border}; color: {p.text_faint}; }}

QPushButton#Ghost, QPushButton[ghost="true"] {{
    background: transparent; border: 1px solid transparent; color: {p.text_muted}; font-weight: 600;
}}
QPushButton#Ghost:hover, QPushButton[ghost="true"]:hover {{ background-color: {p.surface_alt}; color: {p.text}; }}
QPushButton#Ghost:pressed, QPushButton[ghost="true"]:pressed {{ background-color: {p.surface_sunken}; }}

QPushButton#Icon, QToolButton#Icon, QPushButton[icon="true"], QToolButton[icon="true"] {{
    background: transparent; border: none; border-radius: {r['sm']}px;
    padding: 6px; color: {p.text_muted};
}}
QPushButton#Icon:hover, QToolButton#Icon:hover, QPushButton[icon="true"]:hover, QToolButton[icon="true"]:hover {{
    background-color: {p.surface_alt}; color: {p.text};
}}
QPushButton#Icon:pressed, QToolButton#Icon:pressed {{ background-color: {p.surface_sunken}; }}
QPushButton#Icon:checked, QToolButton#Icon:checked {{ background-color: {p.accent_soft}; color: {p.accent}; }}

QPushButton#Danger, QPushButton[danger="true"] {{
    background-color: {p.danger_soft}; border: 1px solid {p.danger}; color: {p.danger}; font-weight: 650;
}}
QPushButton#Danger:hover, QPushButton[danger="true"]:hover {{ background-color: {p.danger}; color: #FFFFFF; }}

QPushButton#Success, QPushButton[success="true"] {{
    background-color: {p.success}; border: 1px solid {p.success}; color: #FFFFFF; font-weight: 650;
}}
QPushButton#Success:hover {{ background-color: {p.success_soft}; color: {p.success}; }}

QPushButton#Chip, QPushButton[chip="true"] {{
    background-color: {p.surface}; border: 1px solid {p.border};
    border-radius: {r['pill']}px; padding: 5px 12px; font-weight: 600; font-size: {small}px; color: {p.text_muted};
}}
QPushButton#Chip:hover, QPushButton[chip="true"]:hover {{ border-color: {p.accent}; color: {p.accent}; background-color: {p.accent_soft}; }}
QPushButton#Chip:checked, QPushButton[chip="true"]:checked {{
    background-color: {p.accent_soft}; border-color: {p.accent}; color: {p.accent};
}}

QToolButton {{ background: transparent; border: none; border-radius: {r['sm']}px; padding: 6px; color: {p.text_muted}; }}
QToolButton:hover {{ background-color: {p.surface_alt}; color: {p.text}; }}
QToolButton:checked {{ background-color: {p.accent_soft}; color: {p.accent}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

/* ===== sidebar list ===== */
QListWidget, QListView {{
    background: transparent; border: none; color: {p.text};
    border-radius: {r['md']}px;
}}
QListWidget::item, QListView::item {{
    padding: 9px 10px; border-radius: {r['sm']}px; margin: 1px 6px 1px 2px;
    border: 1px solid transparent; color: {p.text_muted};
}}
QListWidget::item:hover, QListView::item:hover {{ background-color: {p.sidebar_item_hover}; color: {p.text}; }}
QListWidget::item:selected, QListView::item:selected {{
    background-color: {p.sidebar_item_selected}; color: {p.text}; border: 1px solid {p.border};
}}
QListWidget::item:selected:active {{ background-color: {p.sidebar_item_selected}; }}

/* ===== inputs ===== */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {p.surface};
    border: 1px solid {p.border_strong};
    border-radius: {r['md']}px;
    padding: 8px 11px;
    color: {p.text};
    selection-background-color: {p.selection};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {p.accent};
}}
QLineEdit:disabled, QPlainTextEdit:disabled {{ background-color: {p.surface_alt}; color: {p.text_faint}; }}
QPlainTextEdit#Composer, QTextEdit#Composer {{
    border-radius: {r['lg']}px; padding: 12px 14px; font-size: {fs}px;
    background-color: {p.surface}; border: 1px solid {p.border_strong};
}}
QPlainTextEdit#Composer:focus {{ border: 1px solid {p.accent}; }}
QPlainTextEdit[mono="true"], QTextEdit[mono="true"], QLineEdit[mono="true"] {{
    font-family: {FONT_MONO}; font-size: {small}px;
}}

QComboBox {{
    background-color: {p.surface}; border: 1px solid {p.border_strong};
    border-radius: {r['md']}px; padding: 7px 12px; color: {p.text}; font-weight: 600;
    min-height: 18px;
}}
QComboBox:hover {{ border-color: {p.text_faint}; }}
QComboBox:focus {{ border-color: {p.accent}; }}
QComboBox::drop-down {{ border: none; width: 22px; subcontrol-origin: padding; subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: url(%ARROW%); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background-color: {p.surface}; border: 1px solid {p.border_strong};
    border-radius: {r['md']}px; padding: 5px; selection-background-color: {p.accent_soft};
    selection-color: {p.text}; outline: none;
}}
QComboBox QAbstractItemView::item {{ padding: 7px 10px; border-radius: {r['sm']}px; min-height: 20px; }}
QComboBox QAbstractItemView::item:hover {{ background-color: {p.surface_alt}; }}

QCheckBox, QRadioButton {{ spacing: 9px; color: {p.text}; padding: 3px 0; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px; height: 18px; border: 1.5px solid {p.border_strong};
    background-color: {p.surface};
}}
QCheckBox::indicator {{ border-radius: 5px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {p.accent}; }}
QCheckBox::indicator:checked {{ background-color: {p.accent}; border-color: {p.accent}; image: url(%CHECK%); }}
QRadioButton::indicator:checked {{ background-color: {p.surface}; border: 5px solid {p.accent}; }}

/* ===== scrollbars ===== */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 11px; margin: 3px 3px 3px 0; border: none;
}}
QScrollBar::handle:vertical {{
    background: {p.scrollbar}; min-height: 34px; border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.scrollbar_hover}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; background: none; border: none; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 0 3px 3px 3px; border: none; }}
QScrollBar::handle:horizontal {{ background: {p.scrollbar}; min-width: 34px; border-radius: 5px; }}
QScrollBar::handle:horizontal:hover {{ background: {p.scrollbar_hover}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; background: none; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

/* ===== tabs, menus, tooltips ===== */
QTabWidget::pane {{ border: 1px solid {p.border}; border-radius: {r['lg']}px; background: {p.surface}; top: -1px; }}
QTabBar::tab {{
    background: transparent; color: {p.text_muted}; padding: 9px 16px;
    border: none; border-bottom: 2px solid transparent; font-weight: 600; margin-right: 4px;
}}
QTabBar::tab:hover {{ color: {p.text}; }}
QTabBar::tab:selected {{ color: {p.accent}; border-bottom: 2px solid {p.accent}; }}

QMenu {{
    background-color: {p.surface}; border: 1px solid {p.border_strong};
    border-radius: {r['md']}px; padding: 6px; color: {p.text};
}}
QMenu::item {{ padding: 8px 22px 8px 12px; border-radius: {r['sm']}px; }}
QFrame#SessionItem {{ background: transparent; border-radius: {r['md']}px; border: 1px solid transparent; }}
QFrame#SessionItem:hover {{ background: {p.sidebar_item_hover}; }}
QFrame#SessionItem[active="true"] {{ background: {p.sidebar_item_selected}; border: 1px solid {p.border}; }}
QFrame#ProjectItem {{ background: transparent; border-radius: {r['md']}px; }}
QFrame#ProjectItem:hover {{ background: {p.sidebar_item_hover}; }}
QFrame#ProjectItem[active="true"] {{ background: {p.sidebar_item_selected}; }}
QMenu::item:selected {{ background-color: {p.accent_soft}; color: {p.accent}; }}
QMenu::item:disabled {{ color: {p.text_faint}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 5px 8px; }}

QToolTip {{
    background-color: {p.surface_sunken}; color: {p.text}; border: 1px solid {p.border_strong};
    border-radius: {r['sm']}px; padding: 6px 9px; font-size: {small}px;
}}

QProgressBar {{
    background-color: {p.surface_alt}; border: none; border-radius: {r['pill']}px;
    height: 7px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background-color: {p.accent}; border-radius: {r['pill']}px; }}
QProgressBar[busy="true"]::chunk {{ background-color: {p.warn}; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 1px; background: {p.border}; }}
QSplitter::handle:vertical {{ height: 1px; background: {p.border}; }}

QGroupBox {{
    border: 1px solid {p.border}; border-radius: {r['lg']}px; margin-top: 14px;
    padding: 14px 12px 12px 12px; font-weight: 650; background-color: {p.surface};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 14px; padding: 0 5px; color: {p.text_muted}; }}

/* ===== chat primitives ===== */
QFrame#UserBubble {{
    background-color: {p.user_bubble}; border: 1px solid {p.user_bubble_border};
    border-radius: {r['lg']}px;
}}
QFrame#ClaudeBubble {{
    background-color: {p.claude_bubble}; border: 1px solid {p.claude_bubble_border};
    border-radius: {r['lg']}px;
}}
QFrame#ToolCard {{
    background-color: {p.surface}; border: 1px solid {p.border};
    border-radius: {r['md']}px;
}}
QFrame#ToolCard[state="running"] {{ border: 1px solid {p.accent_border}; background-color: {p.accent_soft}; }}
QFrame#ToolCard[state="error"] {{ border: 1px solid {p.danger}; background-color: {p.danger_soft}; }}
QFrame#ToolCard[state="denied"] {{ border: 1px solid {p.warn}; background-color: {p.warn_soft}; }}
QFrame#PermissionCard {{
    background-color: {p.warn_soft}; border: 1px solid {p.warn}; border-radius: {r['lg']}px;
}}
QFrame#SystemNote {{
    background-color: {p.surface_alt}; border: 1px dashed {p.border_strong}; border-radius: {r['md']}px;
}}
QTextEdit#Markdown, QTextBrowser#Markdown {{
    background: transparent; border: none; padding: 0; color: {p.text};
    font-size: {fs}px;
}}
QPlainTextEdit#RawLog, QTextBrowser#RawLog {{
    background-color: {p.code_bg}; color: {p.code_text}; border: 1px solid {p.code_border};
    border-radius: {r['md']}px; font-family: {FONT_MONO}; font-size: {tiny + 1}px; padding: 8px;
}}
QLabel#ToolTitle {{ font-weight: 650; color: {p.text}; font-size: {small + 1}px; }}
QLabel#ToolMeta {{ color: {p.text_muted}; font-size: {tiny}px; }}
QLabel#StatusDot {{ color: {p.text_muted}; font-size: {tiny}px; }}
QLabel[status="busy"] {{ color: {p.accent}; }}
QLabel[status="error"] {{ color: {p.danger}; }}
QLabel[status="ok"] {{ color: {p.success}; }}

/* ===== dialogs ===== */
QDialog#Modal {{ background-color: {p.bg}; }}
QFrame#ModalCard {{
    background-color: {p.surface}; border: 1px solid {p.border}; border-radius: {r['xl']}px;
}}
QLabel#ModalTitle {{ font-size: {fs + 7}px; font-weight: 700; }}

QTreeView {{
    background-color: {p.surface}; border: 1px solid {p.border}; border-radius: {r['md']}px;
    alternate-background-color: {p.surface_alt};
}}
QTreeView::item {{ padding: 6px 4px; border: none; }}
QTreeView::item:hover {{ background-color: {p.surface_alt}; }}
QTreeView::item:selected {{ background-color: {p.accent_soft}; color: {p.text}; }}
QHeaderView::section {{
    background-color: {p.surface_alt}; color: {p.text_muted}; border: none;
    border-bottom: 1px solid {p.border}; padding: 8px 10px; font-weight: 650;
}}
QTableWidget {{ background-color: {p.surface}; border: 1px solid {p.border}; gridline-color: {p.border}; }}
"""


# --------------------------------------------------------------------------- #
# Small vector assets rendered to disk so QSS can reference them
# --------------------------------------------------------------------------- #

_SVG_ARROW = """<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">
<path d="M2.5 4.5 L6 8 L9.5 4.5" fill="none" stroke="{color}" stroke-width="1.7"
      stroke-linecap="round" stroke-linejoin="round"/></svg>"""

_SVG_CHECK = """<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">
<path d="M3 7.4 L5.7 10 L11 4.2" fill="none" stroke="{color}" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round"/></svg>"""


def _write_svg_png(svg: str, path) -> bool:
    """Render an SVG string to PNG using Qt (no Pillow needed at runtime)."""
    try:
        from PySide6.QtCore import QByteArray, QSize
        from PySide6.QtGui import QPixmap
        from PySide6.QtSvg import QSvgRenderer

        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        if not renderer.isValid():
            return False
        pixmap = QPixmap(QSize(48, 48))
        pixmap.fill(0)
        from PySide6.QtGui import QPainter

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        path.parent.mkdir(parents=True, exist_ok=True)
        return pixmap.save(str(path), "PNG")
    except Exception:
        return False


def prepare_stylesheet(mode: str, accent: str, font_size: int, radius_scale: float = 1.0) -> tuple[str, Palette]:
    """Return (stylesheet, palette) with image URLs resolved to real files."""
    from fcc import paths

    p = palette_for(mode, accent)
    icon_dir = paths.cache_dir() / "qss" / f"{p.mode}-{accent}-{font_size}"
    arrow = icon_dir / "arrow.png"
    check = icon_dir / "check.png"
    _write_svg_png(_SVG_ARROW.format(color=p.text_muted), arrow)
    _write_svg_png(_SVG_CHECK.format(color=p.text_on_accent), check)
    qss = build_qss(p, font_size=font_size, radius_scale=radius_scale)
    qss = qss.replace("%ARROW%", arrow.as_posix()).replace("%CHECK%", check.as_posix())
    return qss, with_font_size(p, font_size)
