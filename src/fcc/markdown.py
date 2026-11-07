"""A small, streaming-safe Markdown → HTML renderer for the chat view.

QTextBrowser understands a useful subset of HTML 4 + CSS, so the output is kept
deliberately simple: escaped text, inline styles from the active palette and
Pygments-highlighted code blocks.
"""

from __future__ import annotations

import html
import re
from typing import List, Optional

try:  # Pygments is optional but recommended
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import TextLexer, get_lexer_by_name
    from pygments.util import ClassNotFound

    _HAS_PYGMENTS = True
except Exception:  # pragma: no cover
    _HAS_PYGMENTS = False

_CODE_CACHE: dict[str, str] = {}
MAX_CODE_CHARS = 60000


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


_INLINE_CODE = re.compile(r"`([^`\n]+?)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+?)\*(?!\*)|(?<!_)_([^_\n]+?)_(?!_)")
_STRIKE = re.compile(r"~~(.+?)~~")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
_AUTO_LINK = re.compile(r"(?<![\(\"\'>=])(https?://[^\s<>\)]+)")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


def _inline(text: str) -> str:
    """Escape then apply inline markdown."""
    placeholders: List[str] = []

    def stash(html_text: str) -> str:
        placeholders.append(html_text)
        return f"\x00{len(placeholders) - 1}\x00"

    def code_repl(match: re.Match) -> str:
        return stash(f'<code class="md-inline">{_esc(match.group(1))}</code>')

    text = _INLINE_CODE.sub(code_repl, text)
    text = _esc(text)

    def link_repl(match: re.Match) -> str:
        label, target, title = match.group(1), match.group(2), match.group(3) or ""
        safe = target.strip()
        if safe.lower().startswith(("javascript:", "data:", "vbscript:")):
            return label
        return stash(
            f'<a href="{html.escape(safe, quote=True)}" title="{html.escape(title, quote=True)}">{label}</a>'
        )

    text = _LINK.sub(link_repl, text)

    def auto_repl(match: re.Match) -> str:
        url = match.group(1).rstrip(".,;:)")
        return stash(f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>')

    text = _AUTO_LINK.sub(auto_repl, text)
    text = _BOLD.sub(lambda m: f"<b>{m.group(1) or m.group(2)}</b>", text)
    text = _ITALIC.sub(lambda m: f"<i>{m.group(1) or m.group(2)}</i>", text)
    text = _STRIKE.sub(lambda m: f"<s>{m.group(1)}</s>", text)

    def unstash(match: re.Match) -> str:
        return placeholders[int(match.group(1))]

    return re.sub(r"\x00(\d+)\x00", unstash, text)


def _highlight(code: str, language: str) -> str:
    if not _HAS_PYGMENTS:
        return f'<pre class="md-code"><code>{_esc(code)}</code></pre>'
    key = f"{language}\x00{hash(code)}"
    cached = _CODE_CACHE.get(key)
    if cached:
        return cached
    truncated = False
    if len(code) > MAX_CODE_CHARS:
        code = code[:MAX_CODE_CHARS]
        truncated = True
    try:
        lexer = get_lexer_by_name(language, stripall=False) if language else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()
    formatter = HtmlFormatter(nowrap=False, cssclass="md-code", noclasses=False, lineseparator="<br>")
    body = highlight(code, lexer, formatter)
    body = body.replace('<div class="md-code">', '<pre class="md-code"><code>', 1)
    body = re.sub(r"</div>\s*$", "</code></pre>", body)
    if truncated:
        body = body.replace("</code></pre>", "\n… truncated …</code></pre>")
    _CODE_CACHE.clear() if len(_CODE_CACHE) > 240 else None
    _CODE_CACHE[key] = body
    return body


_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^\s*(```+|~~~+)\s*([\w+\-.#]*)\s*$")
_UL = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_OL = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_HR = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
_TASK = re.compile(r"^\[([ xX])\]\s+(.*)$")


def _split_row(line: str) -> List[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells, current, escaped = [], "", False
    for char in line:
        if escaped:
            current += char
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append(current.strip())
            current = ""
        else:
            current += char
    cells.append(current.strip())
    return cells


def to_html(markdown_text: str, streaming: bool = False) -> str:
    """Convert markdown to the HTML subset QTextBrowser renders well."""
    if not markdown_text:
        return ""
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: List[str] = []
    index = 0
    total = len(lines)
    list_stack: List[tuple] = []
    paragraph: List[str] = []

    def flush_paragraph() -> None:
        if not paragraph:
            return
        text = " ".join(paragraph).strip()
        paragraph.clear()
        if not text:
            return
        out.append(f"<p>{_inline(text)}</p>")

    def close_lists(depth: int = 0) -> None:
        while len(list_stack) > depth:
            kind = list_stack.pop()[0]
            out.append(f"</{kind}>")

    while index < total:
        line = lines[index]

        fence = _FENCE.match(line)
        if fence:
            flush_paragraph()
            close_lists()
            marker, language = fence.group(1), (fence.group(2) or "").lower()
            buffer: List[str] = []
            index += 1
            closed = False
            while index < total:
                candidate = lines[index]
                if candidate.strip().startswith(marker[:3]) and _FENCE.match(candidate):
                    closed = True
                    index += 1
                    break
                buffer.append(candidate)
                index += 1
            code = "\n".join(buffer)
            if not closed and streaming:
                code = code  # unterminated fence while streaming: render what we have
            title = language or "code"
            out.append(
                f'<div class="md-codeblock"><div class="md-codelang">{_esc(title)}</div>'
                + _highlight(code, language)
                + "</div>"
            )
            continue

        if _HR.match(line) and line.strip():
            flush_paragraph()
            close_lists()
            out.append('<hr class="md-hr">')
            index += 1
            continue

        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            close_lists()
            level = min(len(heading.group(1)) + 1, 6)
            out.append(f"<h{level}>{_inline(heading.group(2).strip())}</h{level}>")
            index += 1
            continue

        if "|" in line and index + 1 < total and _TABLE_SEP.match(lines[index + 1] or ""):
            flush_paragraph()
            close_lists()
            header = _split_row(line)
            index += 2
            rows = []
            while index < total and "|" in lines[index] and lines[index].strip():
                rows.append(_split_row(lines[index]))
                index += 1
            out.append('<table class="md-table"><thead><tr>')
            for cell in header:
                out.append(f"<th>{_inline(cell)}</th>")
            out.append("</tr></thead><tbody>")
            for row in rows:
                out.append("<tr>")
                for position in range(len(header)):
                    value = row[position] if position < len(row) else ""
                    out.append(f"<td>{_inline(value)}</td>")
                out.append("</tr>")
            out.append("</tbody></table>")
            continue

        quote = _QUOTE.match(line)
        if quote:
            flush_paragraph()
            close_lists()
            buffer = [quote.group(1)]
            index += 1
            while index < total:
                nxt = _QUOTE.match(lines[index])
                if not nxt:
                    break
                buffer.append(nxt.group(1))
                index += 1
            out.append(f'<blockquote class="md-quote">{to_html(chr(10).join(buffer), streaming)}</blockquote>')
            continue

        ul = _UL.match(line)
        ol = _OL.match(line)
        if ul or ol:
            flush_paragraph()
            match = ul or ol
            indent = len(match.group(1).replace("\t", "    "))
            depth = indent // 2 + 1
            kind = "ul" if ul else "ol"
            content = match.group(3)
            while len(list_stack) < depth:
                list_stack.append((kind, len(list_stack) + 1))
                out.append(f'<{kind} class="md-list">')
            while len(list_stack) > depth:
                out.append(f"</{list_stack.pop()[0]}>")
            task = _TASK.match(content)
            if task:
                checked = task.group(1).lower() == "x"
                box = "☑" if checked else "☐"
                state = "done" if checked else "todo"
                out.append(f'<li class="md-task {state}"><span class="md-box">{box}</span> {_inline(task.group(2))}</li>')
            else:
                out.append(f"<li>{_inline(content)}</li>")
            index += 1
            continue

        if not line.strip():
            flush_paragraph()
            close_lists()
            index += 1
            continue

        close_lists()
        paragraph.append(line.strip())
        index += 1

    flush_paragraph()
    close_lists()
    return "\n".join(out)


def markdown_css(palette, font_size: int = 14) -> str:
    """Stylesheet applied to the chat document (QTextDocument default stylesheet)."""
    p = palette
    small = max(10, font_size - 2)
    return f"""
body {{ color: {p.text}; font-size: {font_size}px; line-height: 1.62; }}
p {{ margin: 0 0 9px 0; }}
h2 {{ font-size: {font_size + 6}px; font-weight: 700; margin: 16px 0 8px 0; color: {p.text}; }}
h3 {{ font-size: {font_size + 4}px; font-weight: 700; margin: 14px 0 6px 0; color: {p.text}; }}
h4 {{ font-size: {font_size + 2}px; font-weight: 650; margin: 12px 0 5px 0; color: {p.text}; }}
h5, h6 {{ font-size: {font_size}px; font-weight: 650; margin: 10px 0 4px 0; color: {p.text_muted}; }}
a {{ color: {p.accent}; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
code.md-inline {{
    background-color: {p.code_bg}; color: {p.accent if not p.dark else p.accent};
    border: 1px solid {p.code_border}; border-radius: 4px; padding: 1px 5px;
    font-family: 'Cascadia Mono','JetBrains Mono',Consolas,monospace; font-size: {small}px;
}}
div.md-codeblock {{ margin: 10px 0 12px 0; }}
div.md-codelang {{
    background-color: {p.surface_sunken}; color: {p.text_faint};
    border: 1px solid {p.code_border}; border-bottom: none;
    border-top-left-radius: 8px; border-top-right-radius: 8px;
    padding: 4px 10px; font-size: {max(9, font_size - 4)}px; font-weight: 700;
    letter-spacing: 0.6px; text-transform: lowercase;
}}
pre.md-code {{
    background-color: {p.code_bg}; color: {p.code_text};
    border: 1px solid {p.code_border}; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;
    padding: 10px 12px; margin: 0;
    font-family: 'Cascadia Mono','JetBrains Mono',Consolas,monospace; font-size: {small}px;
    white-space: pre-wrap;
}}
pre.md-code code {{ background: transparent; border: none; padding: 0; color: {p.code_text}; }}
blockquote.md-quote {{
    border-left: 3px solid {p.accent}; background-color: {p.surface_alt};
    margin: 10px 0; padding: 8px 14px; color: {p.text_muted}; border-radius: 0 8px 8px 0;
}}
ul.md-list, ol.md-list {{ margin: 6px 0 10px 0; padding-left: 22px; }}
ul.md-list li, ol.md-list li {{ margin: 3px 0; }}
li.md-task {{ list-style: none; margin-left: -18px; }}
span.md-box {{ color: {p.accent}; font-weight: 700; margin-right: 4px; }}
li.md-task.done span.md-box {{ color: {p.success}; }}
hr.md-hr {{ border: none; border-top: 1px solid {p.border}; margin: 14px 0; }}
table.md-table {{ border-collapse: collapse; margin: 10px 0; width: 100%; }}
table.md-table th {{
    background-color: {p.surface_alt}; color: {p.text_muted}; text-align: left;
    padding: 6px 10px; border: 1px solid {p.border}; font-weight: 700; font-size: {small}px;
}}
table.md-table td {{ padding: 6px 10px; border: 1px solid {p.border}; }}
/* Pygments token colours tuned for the Claude palette */
.md-code .hll {{ background-color: {p.selection}; }}
.md-code .k, .md-code .kd, .md-code .kn, .md-code .kr, .md-code .kt {{ color: {p.accent}; font-weight: 600; }}
.md-code .s, .md-code .s1, .md-code .s2, .md-code .sb, .md-code .sc, .md-code .sd, .md-code .se, .md-code .sh, .md-code .si, .md-code .sx {{ color: {p.success}; }}
.md-code .c, .md-code .c1, .md-code .cm, .md-code .cp, .md-code .cs {{ color: {p.text_faint}; font-style: italic; }}
.md-code .n, .md-code .na, .md-code .nb, .md-code .nc, .md-code .nd, .md-code .ne, .md-code .nf, .md-code .nn, .md-code .no, .md-code .nt, .md-code .nv, .md-code .nx {{ color: {p.code_text}; }}
.md-code .mi, .md-code .mf, .md-code .mh, .md-code .mo, .md-code .m {{ color: {p.info}; }}
.md-code .o, .md-code .ow {{ color: {p.text_muted}; }}
.md-code .err {{ color: {p.danger}; }}
"""


def plain_text(markdown_text: str) -> str:
    """Strip markdown for clipboard exports and notifications."""
    text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).strip("`"), markdown_text or "")
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.M)
    text = re.sub(r"^>\s?", "", text, flags=re.M)
    return text.strip()


def first_sentence(text: str, limit: int = 90) -> str:
    clean = plain_text(text).replace("\n", " ")
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rstrip() + "…"
