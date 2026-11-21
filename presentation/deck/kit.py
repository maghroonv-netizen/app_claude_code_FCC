"""Drawing kit: RTL-aware helpers on top of python-pptx."""

from __future__ import annotations

import math
import os

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN, MSO_AUTO_SIZE
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Inches, Pt

from . import theme as T

# ------------------------------------------------------------------ QA log
QA: list[dict] = []


def qa_reset():
    QA.clear()


def _inch(v):
    return Inches(v) if isinstance(v, (int, float)) else v


# ------------------------------------------------------------------ text utils
CHARS_EM = 0.505  # conservative average advance for Tahoma Persian


def est_lines(text: str, width_in: float, size_pt: float) -> int:
    if not text:
        return 1
    char_w = size_pt * CHARS_EM / 72.0
    per_line = max(4, int(width_in / char_w))
    lines, cur = 1, 0
    for word in text.split():
        ln = len(word) + 1
        if cur + ln > per_line:
            lines += 1
            cur = ln
        else:
            cur += ln
    return lines


def est_height(text: str, width_in: float, size_pt: float, ls: float = 1.3) -> float:
    return est_lines(text, width_in, size_pt) * size_pt * 1.2 * ls / 72.0


def set_font(run, name=T.FONT, size=None, bold=None, color=None, italic=None):
    f = run.font
    if size is not None:
        f.size = Pt(size)
    if bold is not None:
        f.bold = bold
    if italic is not None:
        f.italic = italic
    if color is not None:
        f.color.rgb = T.hexcolor(color)
    f.name = name
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = parse_xml('<%s %s typeface="%s"/>' % (tag, nsdecls("a"), name))
            rPr.append(el)
        else:
            el.set("typeface", name)
    rPr.set("lang", "fa-IR")


def _prep_par(p, align="r", rtl=True, ls=1.3, sb=0, sa=0, indent=0.0):
    p.alignment = {"r": PP_ALIGN.RIGHT, "l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER,
                   "j": PP_ALIGN.JUSTIFY}[align]
    if ls:
        p.line_spacing = ls
    if sb:
        p.space_before = Pt(sb)
    if sa:
        p.space_after = Pt(sa)
    pPr = p._p.get_or_add_pPr()
    if rtl:
        pPr.set("rtl", "1")
    if indent:
        emu = int(Inches(indent))
        pPr.set("marR", str(emu))
        pPr.set("indent", str(-emu))


def write(tf, items, default=None):
    """items: list of dicts with text/size/bold/color/align/ls/sb/sa/bullet/indent."""
    default = default or {}
    first = True
    for it in items:
        if isinstance(it, str):
            it = {"text": it}
        merged = {**default, **it}
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        marker = merged.get("marker")
        body = merged.get("text", "")
        text = (marker + " " + body) if marker else body
        _prep_par(p, merged.get("align", "r"), merged.get("rtl", True),
                  merged.get("ls", 1.3), merged.get("sb", 0), merged.get("sa", 0),
                  indent=merged.get("indent", 0.0) or (0.26 if marker else 0.0))
        segs = merged.get("segs")
        if segs:
            for seg in segs:
                r = p.add_run()
                r.text = seg["text"]
                set_font(r, seg.get("font", T.FONT), seg.get("size", merged.get("size", T.T_BODY)),
                         seg.get("bold", merged.get("bold", False)),
                         seg.get("color", merged.get("color", T.TEXT)))
        else:
            r = p.add_run()
            r.text = text
            set_font(r, merged.get("font", T.FONT), merged.get("size", T.T_BODY),
                     merged.get("bold", False), merged.get("color", T.TEXT))
    return tf


def txt(slide, x, y, w, h, text="", size=T.T_BODY, color=T.TEXT, bold=False,
        align="r", anchor="t", ls=1.3, margins=(0, 0, 0, 0), items=None,
        font=T.FONT, qa=True, tag=""):
    if isinstance(text, list) and items is None:
        items, text = text, ""
    box = slide.shapes.add_textbox(_inch(x), _inch(y), _inch(w), _inch(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = Inches(margins[0])
    tf.margin_right = Inches(margins[1])
    tf.margin_top = Inches(margins[2])
    tf.margin_bottom = Inches(margins[3])
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    payload = items if items is not None else [{"text": text}]
    write(tf, payload, {"size": size, "color": color, "bold": bold, "align": align,
                        "ls": ls, "font": font})
    if qa:
        inner_w = (_inch(w) - Inches(margins[0]) - Inches(margins[1])) / 914400
        need = 0.0
        for it in payload:
            if isinstance(it, str):
                it = {"text": it}
            m = {**{"size": size, "ls": ls}, **it}
            t = (m.get("marker", "") + " " if m.get("marker") else "") + m.get("text", "")
            need += est_height(t, inner_w - (m.get("indent") or (0.26 if m.get("marker") else 0)),
                               m["size"], m["ls"])
            need += (m.get("sb", 0) + m.get("sa", 0)) / 72.0
        inner_h = (_inch(h) - Inches(margins[2]) - Inches(margins[3])) / 914400
        if need > inner_h + 0.02:
            QA.append({"kind": "overflow", "tag": tag, "text": t[:48], "need": round(need, 2),
                       "have": round(inner_h, 2), "x": x, "y": y, "w": w, "h": h})
    return box


# ------------------------------------------------------------------ shapes
def rect(slide, x, y, w, h, fill=None, line=None, lw=0.75, radius=None,
         shape=MSO_SHAPE.ROUNDED_RECTANGLE, dash=None, transparency=None, line_alpha=None):
    sh = slide.shapes.add_shape(shape, _inch(x), _inch(y), _inch(w), _inch(h))
    sh.shadow.inherit = False
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = T.hexcolor(fill)
        if transparency is not None:
            srgb = sh.fill.fore_color._xFill.find(qn("a:srgbClr"))
            srgb.append(parse_xml('<a:alpha %s val="%d"/>' % (nsdecls("a"), int((1 - transparency) * 100000))))
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = T.hexcolor(line)
        sh.line.width = Pt(lw)
        if line_alpha is not None:
            ln = sh.line._get_or_add_ln()
            srgb = ln.find(qn("a:solidFill")).find(qn("a:srgbClr"))
            srgb.append(parse_xml('<a:alpha %s val="%d"/>' % (nsdecls("a"), int(line_alpha * 100000))))
        if dash:
            sh.line.dash_style = dash
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sh.adjustments[0] = radius
        except Exception:
            pass
    if sh.has_text_frame:
        sh.text_frame.word_wrap = True
    return sh


def shape_text(sh, text, size=T.T_SMALL, color=T.WHITE, bold=False, align="c",
               anchor="m", mat=0.04, ls=1.1):
    tf = sh.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(mat)
    tf.margin_right = Inches(mat)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    tf.paragraphs[0].text = ""
    write(tf, [{"text": text, "size": size, "color": color, "bold": bold, "align": align, "ls": ls}])
    return sh


def hline(slide, x, y, w, color=T.LINE, lw=0.75, dash=None):
    sh = slide.shapes.add_connector(1, _inch(x), _inch(y), _inch(x + w), _inch(y))
    sh.line.color.rgb = T.hexcolor(color)
    sh.line.width = Pt(lw)
    if dash:
        sh.line.dash_style = dash
    return sh


def vline(slide, x, y, h, color=T.LINE, lw=0.75):
    sh = slide.shapes.add_connector(1, _inch(x), _inch(y), _inch(x), _inch(y + h))
    sh.line.color.rgb = T.hexcolor(color)
    sh.line.width = Pt(lw)
    return sh


def arrow(slide, x1, y1, x2, y2, color=T.STEEL_LIGHT, lw=1.5, head="triangle"):
    sh = slide.shapes.add_connector(1, _inch(x1), _inch(y1), _inch(x2), _inch(y2))
    sh.line.color.rgb = T.hexcolor(color)
    sh.line.width = Pt(lw)
    ln = sh.line._get_or_add_ln()
    ln.append(parse_xml('<a:tailEnd %s type="%s" w="med" len="med"/>' % (nsdecls("a"), head)))
    return sh


def bend_arrow(slide, x, y, w, h, color=T.STEEL_LIGHT, lw=1.5):
    """Right-angle connector (elbow) as arrow, from (x,y) to (x+w, y+h)."""
    sh = slide.shapes.add_connector(2, _inch(x), _inch(y), _inch(x + w), _inch(y + h))
    sh.line.color.rgb = T.hexcolor(color)
    sh.line.width = Pt(lw)
    ln = sh.line._get_or_add_ln()
    ln.append(parse_xml('<a:tailEnd %s type="triangle" w="med" len="med"/>' % (nsdecls("a"),)))
    return sh


def chip(slide, x, y, w, h, text, fill=T.BG_TINT, color=T.NAVY, size=10.5, bold=True,
         align="c", line=None, radius=0.5):
    sh = rect(slide, x, y, w, h, fill=fill, line=line, radius=radius)
    shape_text(sh, text, size=size, color=color, bold=bold, align=align, mat=0.05, ls=1.05)
    return sh


def flip_h(sh):
    xfrm = sh._element.spPr.find(qn("a:xfrm"))
    xfrm.set("flipH", "1")
    return sh


def circle_num(slide, x, y, d, text, fill=T.NAVY, color=T.WHITE, size=13, bold=True):
    sh = rect(slide, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    shape_text(sh, text, size=size, color=color, bold=bold, mat=0.0, ls=1.0)
    return sh


# ------------------------------------------------------------------ tables
def _cell_borders(cell, color=T.LINE, w_pt=0.75, edges=("b",), none_color=None):
    tcPr = cell._tc.get_or_add_tcPr()
    tags = {"l": "a:lnL", "r": "a:lnR", "t": "a:lnT", "b": "a:lnB"}
    order = ["a:lnL", "a:lnR", "a:lnT", "a:lnB"]
    made = {}
    for edge, tag in tags.items():
        old = tcPr.find(qn(tag))
        if old is not None:
            tcPr.remove(old)
        if edge in edges:
            xml = ('<{tag} {ns} w="{w}" cap="flat" cmpd="sng" algn="ctr">'
                   '<a:solidFill><a:srgbClr val="{c}"/></a:solidFill>'
                   '<a:prstDash val="solid"/></{tag}>').format(
                tag=tag, ns=nsdecls("a"), w=int(w_pt * 12700), c=color)
        else:
            xml = ('<{tag} {ns} w="0" cap="flat" cmpd="sng" algn="ctr">'
                   '<a:noFill/><a:prstDash val="solid"/></{tag}>').format(tag=tag, ns=nsdecls("a"))
        made[tag] = parse_xml(xml)
    for tag in reversed(order):
        tcPr.insert(0, made[tag])


def table(slide, x, y, w, col_w, data, row_h=0.4, header_h=0.44, size=T.T_TABLE,
          header_size=None, header_fill=T.NAVY, header_color=T.WHITE, first_col_bold=False,
          zebra=True, align=None, valign="m", padding=0.07, header_align="c",
          border_color=T.LINE, first_col_fill=None, first_col_color=None, row_colors=None,
          header_lines=1, qa_tag=""):
    """data: list of rows (first row = header). col_w given right-to-left (logical)."""
    nrows, ncols = len(data), len(data[0])
    total_h = header_h + row_h * (nrows - 1)
    gf = slide.shapes.add_table(nrows, ncols, _inch(x), _inch(y), _inch(w), _inch(total_h))
    tbl = gf.table
    tbl.first_row = False
    tbl.horz_banding = False
    tbl.first_col = False
    # physical order = reversed(logical)
    for i, cw in enumerate(reversed(col_w)):
        tbl.columns[i].width = Inches(cw)
    tbl.rows[0].height = Inches(header_h)
    for r in range(1, nrows):
        tbl.rows[r].height = Inches(row_h)
    aligns = align or (["r"] + ["c"] * (ncols - 1))
    for r, row in enumerate(data):
        for j in range(ncols):
            cell = tbl.cell(r, ncols - 1 - j)   # logical index j -> physical
            content = row[j]
            fill = None
            if r == 0:
                fill = header_fill
            elif first_col_fill and j == 0:
                fill = first_col_fill
            elif row_colors and row_colors.get(r):
                fill = row_colors[r]
            elif zebra and r % 2 == 0:
                fill = T.BG_SOFT
            else:
                fill = T.WHITE
            cell.fill.solid()
            cell.fill.fore_color.rgb = T.hexcolor(fill)
            cell.margin_left = Inches(padding)
            cell.margin_right = Inches(padding)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE}[valign]
            tf = cell.text_frame
            tf.word_wrap = True
            bold = r == 0 or (first_col_bold and j == 0)
            color = header_color if r == 0 else (first_col_color if (first_col_color and j == 0) else T.TEXT)
            if isinstance(content, dict):
                items = content.get("items") or [{"text": content.get("text", "")}]
                c_align = content.get("align", aligns[j])
                c_bold = content.get("bold", bold)
                c_color = content.get("color", color)
                c_size = content.get("size", header_size if (r == 0 and header_size) else size)
            else:
                items = [{"text": str(content)}]
                c_align = aligns[j]
                c_bold, c_color = bold, color
                c_size = header_size if (r == 0 and header_size) else size
            write(tf, items, {"size": c_size, "color": c_color, "bold": c_bold,
                              "align": c_align, "ls": 1.15})
            _cell_borders(cell, color=border_color if r > 0 else header_fill, w_pt=0.75)
            # text fit check
            inner = col_w[j] - 2 * padding
            txt_all = " ".join(i.get("text", "") for i in items)
            if valign == "t":
                need = est_height(txt_all, inner, c_size, 1.15)
                if need > row_h - 0.06:
                    QA.append({"kind": "cell-tall", "tag": qa_tag, "text": txt_all[:40],
                               "need": round(need, 2), "have": round(row_h - 0.06, 2)})
    return gf


# ------------------------------------------------------------------ chrome
def deck():
    prs = Presentation()
    prs.slide_width = Inches(T.SW)
    prs.slide_height = Inches(T.SH)
    return prs


def blank(prs, bg=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    if bg:
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = T.hexcolor(bg)
    return s


def header(slide, kicker, title, dark=False, kicker_color=None, title_color=None, y_title=None):
    tx_color = title_color or (T.WHITE if dark else T.NAVY)
    k_color = kicker_color or (T.GOLD if dark else T.GOLD_DEEP)
    if kicker:
        txt(slide, T.ML, T.HEADER_KICKER_Y, T.CW, 0.28, kicker, size=T.T_KICKER, color=k_color,
            bold=True, ls=1.0, qa=False)
    txt(slide, T.ML, y_title or T.HEADER_TITLE_Y, T.CW, 0.62, title, size=T.T_TITLE, color=tx_color,
        bold=True, ls=1.0, qa=False)
    if not dark:
        hline(slide, T.ML, T.HEADER_RULE_Y, T.CW, T.LINE, 0.75)
        # short gold segment at the right (start of RTL line)
        hline(slide, T.SW - T.MR - 1.15, T.HEADER_RULE_Y, 1.15, T.GOLD, 2.25)


def footer(slide, num, total=T.TOTAL, dark=False, label=None):
    color = T.MUTED_LIGHT if dark else T.MUTED
    if not dark:
        hline(slide, T.ML, T.FOOTER_RULE_Y, T.CW, T.LINE_SOFT, 0.75)
    label = label or "دانشگاه جامع علمی-کاربردی فردوس  |  حسابرسی حساب‌های پرداختنی و سایر بدهی‌ها"
    txt(slide, T.ML + 1.40, T.FOOTER_TEXT_Y, T.CW - 1.40, 0.3, label, size=8.5, color=color,
        align="r", ls=1.0, qa=False)
    fa = "۰۱۲۳۴۵۶۷۸۹"
    conv = lambda v: "".join(fa[int(d)] if d.isdigit() else d for d in str(v))
    txt(slide, T.ML, T.FOOTER_TEXT_Y - 0.02, 1.3, 0.3,
        f"صفحه {conv(num)} از {conv(total)}", size=8.5, color=color, align="l", ls=1.0, qa=False)


def notes(slide, text):
    """Speaker notes = only the text the presenter reads aloud (plain RTL paragraphs)."""
    tf = slide.notes_slide.notes_text_frame
    tf.word_wrap = True
    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]
    first = True
    for ln in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.RIGHT
        pPr = p._p.get_or_add_pPr()
        pPr.set("rtl", "1")
        p.line_spacing = 1.2
        p.space_after = Pt(6)
        r = p.add_run()
        r.text = ln
        set_font(r, T.FONT, 12, bold=False, color=T.TEXT)


PRES_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset(path):
    return path if os.path.isabs(path) else os.path.join(PRES_ROOT, path.split("presentation/")[-1])


def picture_fill(slide, path, x, y, w, h):
    from PIL import Image
    path = asset(path)
    iw, ih = Image.open(path).size
    target, src = w / h, iw / ih
    pic = slide.shapes.add_picture(path, _inch(x), _inch(y), _inch(w), _inch(h))
    if src > target:
        frac = (1 - target / src) / 2
        pic.crop_left = frac
        pic.crop_right = frac
    else:
        frac = (1 - src / target) / 2
        pic.crop_top = frac
        pic.crop_bottom = frac
    return pic


def bg_gradient(slide, c1, c2, angle=45):
    fill = slide.background.fill
    fill.gradient()
    fill.gradient_angle = angle
    stops = fill.gradient_stops
    stops[0].color.rgb = T.hexcolor(c1)
    stops[0].position = 0.0
    stops[1].color.rgb = T.hexcolor(c2)
    stops[1].position = 1.0
