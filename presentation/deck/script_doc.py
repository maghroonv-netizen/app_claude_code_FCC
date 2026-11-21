"""Write the read-aloud script as a right-to-left Word document."""

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK  # noqa: F401
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from . import theme as T
from .script import PARTS

FONT = "Tahoma"
FA = "۰۱۲۳۴۵۶۷۸۹"


def fa(n):
    return "".join(FA[int(c)] for c in str(n))


def _rgb(hex_):
    return RGBColor.from_string(hex_.upper())


PPR_SEQ = ["pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
           "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
           "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
           "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap",
           "jc", "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl", "divId",
           "cnfStyle", "rPr", "sectPr", "pPrChange"]
RPR_SEQ = ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike",
           "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden",
           "color", "spacing", "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect",
           "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout",
           "specVanish", "oMath"]


def _place(parent, el, seq):
    """Insert el into parent at the position the OOXML schema requires (Word is strict)."""
    name = el.tag.split("}")[1]
    idx = seq.index(name)
    for old in parent.findall(el.tag):
        parent.remove(old)
    for child in parent:
        cname = child.tag.split("}")[1]
        if cname in seq and seq.index(cname) > idx:
            child.addprevious(el)
            return el
    parent.append(el)
    return el


def _fix_order(parent, seq):
    kids = list(parent)
    kids.sort(key=lambda c: seq.index(c.tag.split("}")[1]) if c.tag.split("}")[1] in seq else 999)
    for k in kids:
        parent.remove(k)
    for k in kids:
        parent.append(k)


def _rtl_par(p, align="r", before=0, after=6, line=1.5, keep_next=False):
    ppr = p._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    _place(ppr, bidi, PPR_SEQ)
    if align != "r":   # a bidi paragraph with no w:jc is right-aligned by default
        p.alignment = {"c": WD_ALIGN_PARAGRAPH.CENTER, "j": WD_ALIGN_PARAGRAPH.JUSTIFY}[align]
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    pf.keep_with_next = keep_next
    _fix_order(ppr, PPR_SEQ)


def _run(p, text, size=13, bold=False, color=T.TEXT):
    r = p.add_run(text)
    rpr = r._r.get_or_add_rPr()
    fonts = OxmlElement("w:rFonts")
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        fonts.set(qn(a), FONT)
    rpr.insert(0, fonts)
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = _rgb(color)
    for tag, val in (("w:bCs", "1" if bold else "0"), ("w:szCs", str(int(size * 2)))):
        el = OxmlElement(tag)
        el.set(qn("w:val"), val)
        rpr.append(el)
    rtl = OxmlElement("w:rtl")
    rtl.set(qn("w:val"), "1")
    rpr.append(rtl)
    _fix_order(rpr, RPR_SEQ)
    return r


def _border_bottom(p, color=T.GOLD, sz=8):
    ppr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    b.set(qn("w:val"), "single")
    b.set(qn("w:sz"), str(sz))
    b.set(qn("w:space"), "4")
    b.set(qn("w:color"), color)
    bdr.append(b)
    _place(ppr, bdr, PPR_SEQ)


def _shade(p, fill):
    ppr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    _place(ppr, shd, PPR_SEQ)


def _page_number_footer(section):
    p = section.footer.paragraphs[0]
    _rtl_par(p, align="c", after=0, line=1.0)
    _run(p, "صفحه ", size=9, color=T.MUTED)
    r = _run(p, "", size=9, color=T.MUTED)
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        r._r.append(el)


def write_script_docx(path, script, titles):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.3)
    sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.0)
    sectpr = sec._sectPr
    bidi = OxmlElement("w:bidi")
    grid = sectpr.find(qn("w:docGrid"))
    if grid is not None:
        grid.addprevious(bidi)
    else:
        sectpr.append(bidi)
    _page_number_footer(sec)

    st = doc.styles["Normal"]
    st.font.name = FONT
    st.font.size = Pt(13)

    words = sum(len(v.split()) for v in script.values())
    minutes = round(words / 120)

    # ---- cover block
    p = doc.add_paragraph()
    _rtl_par(p, after=2, line=1.2)
    _run(p, "دانشگاه جامع علمی-کاربردی فردوس", size=10.5, color=T.MUTED)
    p = doc.add_paragraph()
    _rtl_par(p, after=2, line=1.3)
    _run(p, "متن ارائه", size=24, bold=True, color=T.NAVY)
    p = doc.add_paragraph()
    _rtl_par(p, after=10, line=1.3)
    _run(p, "حسابرسی حساب‌های پرداختنی و سایر بدهی‌ها", size=15, bold=True, color=T.GOLD_DEEP)
    _border_bottom(p)

    p = doc.add_paragraph()
    _rtl_par(p, after=2, line=1.5)
    _run(p, "استاد درس:  ", size=11, bold=True, color=T.NAVY)
    _run(p, "جناب آقای مرتضی فرخد اسماعیلی", size=11)
    for name_part, name, a, b in PARTS:
        p = doc.add_paragraph()
        _rtl_par(p, after=0, line=1.5)
        _run(p, f"{name}:  ", size=11, bold=True, color=T.NAVY)
        _run(p, f"اسلایدهای {fa(a)} تا {fa(b)}", size=11)
    p = doc.add_paragraph()
    _rtl_par(p, before=8, after=4, line=1.5)
    _shade(p, T.BG_TINT)
    _run(p, "این فایل فقط متنی است که هنگام نمایش هر اسلاید خوانده می‌شود. "
            f"همین متن در بخش یادداشت‌های فایل پاورپوینت هم هست. زمان خواندن کل متن حدود {fa(minutes)} دقیقه است.",
         size=10.5, color=T.TEXT)

    # ---- body
    for part, name, a, b in PARTS:
        p = doc.add_paragraph()
        _rtl_par(p, before=20, after=8, line=1.2, keep_next=True)
        _shade(p, T.NAVY)
        _run(p, f"  {part}  •  {name}  •  اسلایدهای {fa(a)} تا {fa(b)}", size=12.5, bold=True,
             color=T.WHITE)
        for n in range(a, b + 1):
            p = doc.add_paragraph()
            _rtl_par(p, before=14, after=6, line=1.2, keep_next=True)
            _run(p, f"اسلاید {fa(n)}", size=12, bold=True, color=T.GOLD_DEEP)
            _run(p, "   " + titles[n], size=12, bold=True, color=T.NAVY)
            _border_bottom(p, color=T.LINE, sz=6)
            for line in script[n].split("\n"):
                p = doc.add_paragraph()
                _rtl_par(p, align="j", after=7, line=1.6)
                _run(p, line, size=13)

    doc.save(path)
    return words
