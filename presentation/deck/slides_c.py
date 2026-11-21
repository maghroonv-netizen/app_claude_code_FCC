"""Slides 16-21 (stage 2): substantive tests and audit working papers."""

from pptx.enum.dml import MSO_LINE

from . import kit as K
from . import theme as T

TOTAL = T.TOTAL
RIGHT = T.SW - T.MR
KICKER = "۰۷ · آزمون‌های محتوا"


# ------------------------------------------------------------------ shared helpers
def lead(s, text, y=1.50):
    K.txt(s, T.ML, y, T.CW, 0.30, text, size=11, color=T.MUTED, ls=1.0, qa=False)


def panel(s, x, y, w, h, tag, title, items, head=T.NAVY, size=9.5, sa=5, markers=None):
    """White card with a navy title bar and a bullet list."""
    K.rect(s, x, y, w, h, fill=T.WHITE, line=T.LINE, lw=1.0, radius=0.04)
    K.rect(s, x, y, w, 0.54, fill=head, line=None)
    segs = []
    if tag:
        segs.append({"text": tag + "   ", "size": 11, "bold": True, "color": T.GOLD})
    segs.append({"text": title, "size": 11, "bold": True, "color": T.WHITE})
    K.txt(s, x + 0.2, y, w - 0.4, 0.54, items=[{"segs": segs}], anchor="m", ls=1.05)
    rows = []
    for i, t in enumerate(items):
        rows.append({"text": t, "size": size, "marker": markers[i] if markers else "•",
                     "ls": 1.3, "sa": sa})
    K.txt(s, x + 0.2, y + 0.68, w - 0.4, h - 0.78, rows)


def card(s, x, y, w, h, title, items=None, fill=T.BG_SOFT, line=None, title_color=T.NAVY,
         size=9, sa=4, markers=None, title_size=10.5):
    K.rect(s, x, y, w, h, fill=fill, line=line, lw=1.0, radius=0.04)
    K.txt(s, x + 0.18, y + 0.10, w - 0.36, 0.28, title, size=title_size, color=title_color,
          bold=True, ls=1.0, qa=False)
    if items:
        rows = []
        for i, t in enumerate(items):
            rows.append({"text": t, "size": size, "marker": markers[i] if markers else "•",
                         "ls": 1.3, "sa": sa})
        K.txt(s, x + 0.18, y + 0.46, w - 0.36, h - 0.54, rows)


def hypo_tag(s, x, y, text="مثال فرضی", w=1.05):
    K.chip(s, x, y, w, 0.28, text, fill=T.WHITE, color=T.GOLD_DEEP, size=8.5, line=T.GOLD)


def context_line(s, text, tag="مثال فرضی", y=1.56, tag_w=1.05):
    """Small tag at the right edge followed by one line of context."""
    hypo_tag(s, RIGHT - tag_w, y, tag, tag_w)
    K.txt(s, T.ML, y, T.CW - tag_w - 0.15, 0.28, text, size=10, color=T.MUTED, anchor="m",
          ls=1.0, qa=False)


def B(text, color=None, align=None):
    d = {"text": text, "bold": True}
    if color:
        d["color"] = color
    if align:
        d["align"] = align
    return d


# ------------------------------------------------------------------ 16
def slide_vouch_reconcile(prs, num):
    s = K.blank(prs, T.WHITE)
    K.header(s, KICKER, "گام ۶ و ۷: سندرسی و مغایرت‌گیری با صورت‌حساب فروشنده")
    lead(s, "دو آزمون جزئیات: اثبات اعتبار مانده‌های ثبت‌شده و کشف اختلاف با مدارکی که بیرون از شرکت تهیه شده است")

    pw = 5.90
    panel(s, RIGHT - pw, 1.92, pw, 2.44, "گام ۶", "سندرسی مانده‌های انتخابی", [
        "مراجعه به برگه‌های حسابداری، فاکتورها، سفارش‌های خرید و گزارش‌های دریافت",
        "هدف: اثبات اعتبار تراز آزمایشی حساب‌های پرداختنی که صاحبکار تهیه کرده است",
        "در سیستم برگه‌ای، پرونده برگه‌های پرداخت‌نشده هر روز تغییر می‌کند",
        "پس فهرست برگه‌های پرداخت‌نشده در تاریخ ترازنامه باید نگهداری شود: نام فروشنده، شماره برگه، سررسید و مبلغ",
    ])
    panel(s, T.ML, 1.92, pw, 2.44, "گام ۷", "مغایرت‌گیری با صورت‌حساب ماهانه فروشندگان", [
        "اگر صاحبکار هر ماه و مرتب مغایرت‌گیری کرده باشد: بررسی محدود حسابرس کافی است",
        "اگر انجام نشده باشد: حسابرس خود مغایرت‌گیری را انجام می‌دهد",
        "کنترل داخلی ضعیف: حسابرس مراسلات دریافتی را کنترل می‌کند تا همه صورت‌حساب‌ها به دستش برسد",
        "اختلاف رایج: هزینه حمل و کالای در راهی که فاکتور آن هنوز ثبت نشده است",
    ], head=T.NAVY_2)

    # cut-off band
    K.txt(s, T.ML, 4.50, T.CW, 0.26, "انقطاع زمانی پایان سال: مرز دو دوره کجاست؟", size=10.5,
          color=T.NAVY, bold=True, ls=1.0, qa=False)
    y, h = 4.82, 0.92
    side_w, mid_w, gap = 4.32, 2.95, 0.25
    xr = RIGHT - side_w
    xm = xr - gap - mid_w
    xl = T.ML
    K.rect(s, xr, y, side_w, h, fill=T.BG_TINT, line=None, radius=0.06)
    K.txt(s, xr + 0.16, y + 0.10, side_w - 0.32, 0.26, "گزارش‌های دریافت تا آخرین شماره سال",
          size=10, color=T.NAVY, bold=True, ls=1.0, qa=False)
    K.txt(s, xr + 0.16, y + 0.40, side_w - 0.32, 0.46,
          "فاکتور این دریافت‌ها بدهی پایان سال است و کالا در موجودی پایان دوره می‌آید.",
          size=9, color=T.TEXT, ls=1.25)
    K.rect(s, xm, y, mid_w, h, fill=T.NAVY, line=None, radius=0.06)
    K.txt(s, xm + 0.12, y + 0.10, mid_w - 0.24, 0.26, "آخرین گزارش دریافت سال", size=10,
          color=T.GOLD, bold=True, align="c", ls=1.0, qa=False)
    K.txt(s, xm + 0.12, y + 0.40, mid_w - 0.24, 0.46,
          "شماره آن هنگام نظارت بر شمارش موجودی یادداشت می‌شود.",
          size=9, color=T.WHITE, align="c", ls=1.25)
    K.rect(s, xl, y, side_w, h, fill=T.BG_SOFT, line=T.LINE, lw=0.75, radius=0.06)
    K.txt(s, xl + 0.16, y + 0.10, side_w - 0.32, 0.26, "گزارش‌های دریافت با شماره‌های بعدی",
          size=10, color=T.NAVY, bold=True, ls=1.0, qa=False)
    K.txt(s, xl + 0.16, y + 0.40, side_w - 0.32, 0.46,
          "بدهی دوره بعد است و کالای آن نباید جزء موجودی پایان دوره قلمداد شود.",
          size=9, color=T.TEXT, ls=1.25)

    K.rect(s, T.ML, 5.88, T.CW, 0.48, fill="F7E9E9", line=None, radius=0.10)
    K.txt(s, T.ML + 0.2, 5.88, T.CW - 0.4, 0.48,
          items=[{"segs": [
              {"text": "خطای انقطاع:  ", "size": 9.5, "bold": True, "color": T.RED},
              {"text": "اگر کالا در موجودی پایان سال شمارش شود ولی فاکتور و بدهی آن ثبت نشود، سود خالص به اندازه کل مبلغ فاکتور بیش از واقع نشان داده می‌شود.",
               "size": 9.5, "color": T.TEXT}]}], anchor="m", ls=1.0)
    K.txt(s, T.ML, 6.46, T.CW, 0.26,
          "کالای حمل‌شده با شرط فوب مبدأ که تا تاریخ ترازنامه نرسیده، منطقاً جزء موجودی است؛ فهرست کالای در راه تهیه و در صورت بااهمیت بودن اصلاح می‌شود.",
          size=8.5, color=T.MUTED, ls=1.0, qa=False)
    K.footer(s, num, TOTAL)


# ------------------------------------------------------------------ 17
def slide_reconciliation_wp(prs, num):
    s = K.blank(prs, T.WHITE)
    K.header(s, KICKER, "کاربرگ مغایرت‌گیری صورت‌حساب فروشنده")
    context_line(s, "فروشنده: بازرگانی بتا   •   تاریخ ترازنامه: ۲۹ اسفند   •   ادامه همان ردیف کاربرگ اسلاید ۱۵")

    tw = 7.60
    tx = RIGHT - tw
    data = [
        ["شرح", "مبلغ (ریال)", "ملاحظه حسابرس"],
        ["مانده طبق صورت‌حساب فروشنده در ۲۹ اسفند", "11,650,000", "صورت‌حساب ماهانه"],
        ["کسر می‌شود: چک صادره ۲۸ اسفند که فروشنده هنوز ثبت نکرده است", "(1,200,000)", "تفاوت زمانی"],
        [B("مانده تعدیل‌شده صورت‌حساب فروشنده"), B("10,450,000"), ""],
        ["مانده طبق دفتر معین بستانکاران", "8,150,000", "مطابق تراز آزمایشی"],
        ["اضافه می‌شود: فاکتور ۴۱۲۷؛ کالا ۲۷ اسفند دریافت شده اما ثبت نشده است", "2,300,000",
         {"text": "بدهی ثبت‌نشده", "bold": True, "color": T.RED}],
        [B("مانده تعدیل‌شده دفاتر"), B("10,450,000"), {"text": "دو مانده برابر شد", "bold": True, "color": T.GREEN}],
    ]
    K.table(s, tx, 2.02, tw, [4.35, 1.50, 1.75], data, row_h=0.54, header_h=0.46, size=9.5,
            header_size=9.5, align=["r", "c", "c"], valign="m",
            row_colors={3: T.BG_TINT, 6: T.BG_TINT}, zebra=False, qa_tag="s17")
    K.txt(s, tx, 5.80, tw, 0.24,
          "تفاوت زمانی ثبت اصلاحی نمی‌خواهد؛ قلم ثبت‌نشده به کاربرگ بدهی‌های ثبت‌نشده منتقل می‌شود.",
          size=8.5, color=T.MUTED, ls=1.0, qa=False)

    lx, lw = T.ML, 4.24
    # proposed adjusting entry
    K.rect(s, lx, 2.02, lw, 1.72, fill=T.BG_SOFT, line=None, radius=0.04)
    K.txt(s, lx + 0.16, 2.11, lw - 0.32, 0.26, "ثبت اصلاحی پیشنهادی", size=10.5, color=T.NAVY,
          bold=True, ls=1.0, qa=False)
    K.table(s, lx + 0.12, 2.46, lw - 0.24, [2.00, 1.00, 1.00],
            [["حساب", "بدهکار", "بستانکار"],
             ["خرید مواد و کالا", "2,300,000", ""],
             ["حساب‌های پرداختنی", "", "2,300,000"]],
            row_h=0.38, header_h=0.36, size=9, header_size=8.5, header_fill=T.STEEL,
            align=["r", "c", "c"], zebra=False, qa_tag="s17j")

    # effect on the financial statements
    card(s, lx, 3.88, lw, 1.86, "اثر بر صورت‌های مالی پیش از اصلاح", [
        "بدهی‌های جاری 2,300,000 ریال کمتر از واقع",
        "کالا در شمارش پایان سال آمده است؛ پس بهای تمام‌شده کمتر و سود 2,300,000 ریال بیش از واقع",
        "سرمایه در گردش و نسبت جاری بهتر از واقع",
    ], fill=T.WHITE, line=T.RED, title_color=T.RED, size=9, sa=3)

    K.rect(s, T.ML, 6.12, T.CW, 0.54, fill=T.NAVY, line=None, radius=0.08)
    K.txt(s, T.ML + 0.2, 6.12, T.CW - 0.4, 0.54,
          items=[{"segs": [
              {"text": "ترتیب کار حسابرس:  ", "size": 9.5, "bold": True, "color": T.GOLD},
              {"text": "دریافت صورت‌حساب  ←  تطبیق قلم‌به‌قلم با دفتر معین  ←  پی‌جویی هر قلم باز تا سند  ←  تفکیک تفاوت زمانی از بدهی ثبت‌نشده",
               "size": 9.5, "color": T.WHITE}]}], anchor="m", ls=1.0)
    K.footer(s, num, TOTAL)


# ------------------------------------------------------------------ 18
def slide_confirmation(prs, num):
    s = K.blank(prs, T.WHITE)
    K.header(s, KICKER, "گام ۸: تأییدیه حساب‌های پرداختنی")

    # letter mock-up (right)
    lw_ = 6.30
    x = RIGHT - lw_
    y0, h0 = 1.64, 4.96
    K.rect(s, x, y0, lw_, h0, fill=T.WHITE, line=T.LINE, lw=1.25, radius=0.02)
    K.rect(s, x, y0, lw_, 0.07, fill=T.GOLD, line=None, radius=0.0)
    hypo_tag(s, x + lw_ - 2.86, y0 + 0.20, "شکل ۱۵-۳ کتاب (خلاصه‌شده)", 2.70)
    K.txt(s, x + 0.25, y0 + 0.20, 3.2, 0.28, "نمونه درخواست تأییدیه بستانکاران", size=10.5,
          color=T.NAVY, bold=True, anchor="m", align="l", ls=1.0, qa=False)
    K.txt(s, x + 0.25, y0 + 0.62, lw_ - 0.5, 0.54,
          items=[{"segs": [{"text": "از:  ", "size": 9.5, "bold": True, "color": T.MUTED},
                           {"text": "شرکت بسته‌بندی فین (سهامی عام)", "size": 9.5, "color": T.TEXT}],
                  "ls": 1.3},
                 {"segs": [{"text": "به:  ", "size": 9.5, "bold": True, "color": T.MUTED},
                           {"text": "شرکت پخش تفتان (سهامی عام)", "size": 9.5, "color": T.TEXT}],
                  "ls": 1.3}], qa=False)
    K.txt(s, x + 0.25, y0 + 1.26, lw_ - 0.5, 1.56,
          items=[{"text": "«مؤسسه حسابرسی کاشفان مشغول رسیدگی به صورت‌های مالی این شرکت است. خواهشمند است "
                          "مبلغ بدهی این شرکت را در تاریخ ۲۹ اسفند در محل تعیین‌شده در زیر درج و آن را "
                          "مستقیماً برای آن مؤسسه ارسال دارید.", "size": 9.5, "ls": 1.45, "sa": 5},
                 {"text": "خواهشمند است آخرین صورت‌حسابی که تمام اقلام پرداخت‌نشده این شرکت را نشان دهد "
                          "نیز پیوست پاسخ خود نمایید.»", "size": 9.5, "ls": 1.45}])
    K.txt(s, x + 0.25, y0 + 2.86, lw_ - 0.5, 0.26, "امضا: معاون مالی و اداری شرکت", size=9,
          color=T.MUTED, align="l", ls=1.0, qa=False)
    K.hline(s, x + 0.25, y0 + 3.26, lw_ - 0.5, T.STEEL_LIGHT, 1.0, dash=MSO_LINE.DASH)
    K.txt(s, x + 0.25, y0 + 3.38, lw_ - 0.5, 0.26, "بخش پاسخ (فروشنده پر می‌کند و مستقیم برای حسابرس می‌فرستد)",
          size=9, color=T.GOLD_DEEP, bold=True, ls=1.0, qa=False)
    K.txt(s, x + 0.25, y0 + 3.70, lw_ - 0.5, 0.74,
          "«مدارک این شرکت در تاریخ ۲۹ اسفند نشان می‌دهد که شرکت بسته‌بندی فین مبلغ 26,800,000 ریال "
          "به شرح صورت‌حساب پیوست به این شرکت بدهکار است.»", size=9.5, color=T.TEXT, ls=1.45)
    K.txt(s, x + 0.25, y0 + 4.52, lw_ - 0.5, 0.26, "تاریخ: ..............     امضا و سمت: ..............",
          size=9, color=T.MUTED, align="l", ls=1.0, qa=False)

    # left column
    lx, lw = T.ML, 5.52
    card(s, lx, 1.64, lw, 2.26, "برای چه حساب‌هایی فرستاده می‌شود؟", [
        "همه فروشندگانی که در طول سال خرید عمده از آنان شده، صرف‌نظر از مانده پایان سال",
        "حساب‌های با مانده صفر، اگر تأمین‌کننده عمده باشند",
        "حساب‌هایی که صورت‌حساب ماهانه آن‌ها به حسابرس ارائه نشده است",
        "حساب‌های با معاملات غیرعادی؛ شرکت مادر و شرکت‌های تابع",
        "حساب‌های تضمین‌شده با وثیقه دارایی‌ها",
    ], size=9, sa=3)
    card(s, lx, 4.04, lw, 1.86, "چرا به اندازه تأییدیه بدهکاران اهمیت ندارد؟", [
        "خطر اصلی، بدهی ثبت‌نشده است؛ تأیید مانده ثبت‌شده، نبود بدهی ثبت‌نشده را اثبات نمی‌کند",
        "شواهد بیرونی مثل فاکتور و صورت‌حساب ماهانه در محل صاحبکار موجود است",
        "بیشتر مانده‌ها پیش از پایان رسیدگی پرداخت می‌شوند و همین پرداخت، تأیید دیگری است",
    ], fill=T.WHITE, line=T.LINE, size=9, sa=3, markers=["۱.", "۲.", "۳."])
    K.rect(s, lx, 6.04, lw, 0.56, fill=T.BG_TINT, line=None, radius=0.10)
    K.txt(s, lx + 0.16, 6.04, lw - 0.32, 0.56,
          "استاندارد حسابرسی ۵۰۵ «تأییدیه‌های برون‌سازمانی»: درخواست زیر کنترل حسابرس فرستاده و پاسخ مستقیماً به حسابرس برگردانده می‌شود.",
          size=8.5, color=T.NAVY, anchor="m", ls=1.2)
    K.footer(s, num, TOTAL)


# ------------------------------------------------------------------ 19
def slide_analytics(prs, num):
    s = K.blank(prs, T.WHITE)
    K.header(s, KICKER, "گام ۹: روش‌های تحلیلی و تحلیل سنی پرداختنی‌ها")

    # right: analytical procedures from the book
    rw = 4.28
    rx = RIGHT - rw
    K.rect(s, rx, 1.64, rw, 4.96, fill=T.BG_SOFT, line=None, radius=0.03)
    K.txt(s, rx + 0.18, 1.74, rw - 0.36, 0.28, "چهار مقایسه‌ای که کتاب پیشنهاد می‌کند", size=10.5,
          color=T.NAVY, bold=True, ls=1.0, qa=False)
    items = [
        ("۱", "نسبت‌ها", "نسبت بستانکاران به خرید و به مجموع بدهی‌های جاری؛ مقایسه با سال‌های قبل"),
        ("۲", "صورت‌ریز فروشندگان", "مقایسه مانده هر فروشنده با پایان سال‌های گذشته؛ شناسایی فروشندگان غیرمعمول"),
        ("۳", "اقلام سررسیدگذشته", "مقایسه پرداختنی‌های سررسیدگذشته با مبالغ مشابه سال‌های پیش"),
        ("۴", "تخفیفات نقدی", "نسبت تخفیفات نقدی دریافتی به مجموع خرید؛ کاهش عمده، نشانه تغییر شرایط خرید، استفاده نکردن از تخفیف یا دستکاری است"),
    ]
    ys = [2.14, 3.12, 4.10, 5.08]
    hs = [0.88, 0.88, 0.88, 1.38]
    for (n, t, d), y, h in zip(items, ys, hs):
        K.rect(s, rx + 0.14, y, rw - 0.28, h, fill=T.WHITE, line=T.LINE, lw=0.75, radius=0.06)
        K.circle_num(s, rx + rw - 0.56, y + 0.10, 0.28, n, fill=T.NAVY, size=9.5)
        K.txt(s, rx + 0.28, y + 0.10, rw - 0.98, 0.28, t, size=10, color=T.NAVY, bold=True,
              ls=1.0, qa=False)
        K.txt(s, rx + 0.28, y + 0.40, rw - 0.56, h - 0.46, d, size=8.5, color=T.MUTED, ls=1.25)

    # left: aged analysis (hypothetical)
    lx = T.ML
    lw = T.CW - rw - 0.25
    hypo_tag(s, lx + lw - 1.05, 1.64)
    K.txt(s, lx, 1.64, lw - 1.2, 0.28, "تحلیل سنی حساب‌های پرداختنی در پایان سال (ریال)", size=10.5,
          color=T.NAVY, bold=True, anchor="m", ls=1.0, qa=False)
    data = [
        ["طبقه سنی", "سال جاری", "درصد", "سال قبل", "درصد"],
        ["سررسید نشده", "17,580,000", "60", "19,600,000", "70"],
        ["۱ تا ۳۰ روز از سررسید گذشته", "5,860,000", "20", "5,600,000", "20"],
        ["۳۱ تا ۹۰ روز از سررسید گذشته", "3,516,000", "12", "1,960,000", "7"],
        ["بیش از ۹۰ روز از سررسید گذشته", "2,344,000", {"text": "8", "bold": True, "color": T.RED},
         "840,000", "3"],
        [B("جمع"), B("29,300,000"), B("100"), B("28,000,000"), B("100")],
    ]
    K.table(s, lx, 2.02, lw, [2.76, 1.50, 0.80, 1.50, 1.003], data, row_h=0.38, header_h=0.42,
            size=9.5, header_size=9.5, align=["r", "c", "c", "c", "c"], valign="m",
            row_colors={5: T.BG_TINT}, qa_tag="s19")

    # KPI chips
    kw, kg = (lw - 2 * 0.16) / 3, 0.16
    kpis = [
        ("نسبت پرداختنی به خرید سال", "سال قبل: 16.0 درصد", "سال جاری: 12.5 درصد"),
        ("رشد نسبت به سال قبل", "خرید: 34 درصد", "پرداختنی‌ها: 4.6 درصد"),
        ("نسبت تخفیف نقدی به خرید", "سال قبل: 2.0 درصد", "سال جاری: 1.0 درصد"),
    ]
    ky = 4.70
    for i, (t, a, b) in enumerate(kpis):
        kx = lx + lw - kw - i * (kw + kg)
        K.rect(s, kx, ky, kw, 0.98, fill=T.WHITE, line=T.LINE, lw=1.0, radius=0.06)
        K.rect(s, kx, ky, kw, 0.05, fill=T.GOLD, line=None, radius=0.0)
        K.txt(s, kx + 0.12, ky + 0.12, kw - 0.24, 0.26, t, size=9, color=T.MUTED, bold=True,
              align="c", ls=1.0, qa=False)
        K.txt(s, kx + 0.12, ky + 0.40, kw - 0.24, 0.56,
              items=[{"text": a, "size": 10.5, "color": T.TEXT, "align": "c", "ls": 1.25},
                     {"text": b, "size": 10.5, "bold": True, "color": T.NAVY, "align": "c", "ls": 1.25}],
              qa=False)
    K.txt(s, lx, 4.40, lw, 0.24,
          "خرید سال: 234,400,000 در برابر 175,000,000   •   تخفیف نقدی: 2,344,000 در برابر 3,500,000",
          size=8.5, color=T.MUTED, ls=1.0, qa=False)

    K.rect(s, lx, 5.78, lw, 0.82, fill=T.NAVY, line=None, radius=0.06)
    K.txt(s, lx + 0.18, 5.78, lw - 0.36, 0.82,
          items=[{"segs": [
              {"text": "تفسیر حسابرس:  ", "size": 9.5, "bold": True, "color": T.GOLD},
              {"text": "خرید 34 درصد رشد کرده ولی پرداختنی‌ها تقریباً ثابت مانده است؛ احتمال بدهی ثبت‌نشده بالا می‌رود. "
                       "رشد اقلام بیش از ۹۰ روز و افت تخفیف نقدی هم باید پی‌جویی شود.",
               "size": 9.5, "color": T.WHITE}]}], anchor="m", ls=1.35)
    K.footer(s, num, TOTAL)


# ------------------------------------------------------------------ 20
def slide_subsequent(prs, num):
    s = K.blank(prs, T.WHITE)
    K.header(s, KICKER, "گام ۱۰: جست‌وجوی بدهی‌های ثبت‌نشده")

    rw = 4.10
    rx = RIGHT - rw
    K.rect(s, rx, 1.64, rw, 2.02, fill=T.NAVY, line=None, radius=0.04)
    K.txt(s, rx + 0.18, 1.74, rw - 0.36, 0.28, "مؤثرترین روش", size=10, color=T.GOLD, bold=True,
          ls=1.0, qa=False)
    K.txt(s, rx + 0.18, 2.06, rw - 0.36, 1.52,
          items=[{"text": "مقایسه پرداخت‌های نقدی پس از تاریخ ترازنامه با صورت‌ریز حساب‌های پرداختنی در آن تاریخ.",
                  "size": 10, "bold": True, "color": T.WHITE, "ls": 1.4, "sa": 6},
                 {"text": "منطق کتاب: هر بدهی سرانجام باید پرداخت شود؛ پس دست‌کم هنگام پرداخت در دفاتر دیده می‌شود.",
                  "size": 9, "color": "C9D8E2", "ls": 1.35}])
    card(s, rx, 3.80, rw, 2.80, "سه جای دیگر برای جست‌وجو", [
        "کار در جریان: فاکتورهای بدون گزارش دریافت و گزارش‌های دریافت بدون فاکتور",
        "برگه‌هایی که پس از تاریخ ترازنامه در معین بستانکاران ثبت شده‌اند",
        "فاکتورهایی که صاحبکار پس از تاریخ ترازنامه دریافت کرده است",
        "برای اطمینان از دیدن همه پرداخت‌ها، ترتیب شماره چک‌های صادره تا پایان رسیدگی کنترل می‌شود",
    ], size=9, sa=5, markers=["۱.", "۲.", "۳.", "✓"])

    lx = T.ML
    lw = T.CW - rw - 0.25
    hypo_tag(s, lx + lw - 1.05, 1.64)
    K.txt(s, lx, 1.64, lw - 1.2, 0.28, "کاربرگ بررسی پرداخت‌های پس از تاریخ ترازنامه (۲۹ اسفند)",
          size=10.5, color=T.NAVY, bold=True, anchor="m", ls=1.0, qa=False)
    red = lambda t: {"text": t, "bold": True, "color": T.RED}
    data = [
        ["چک", "تاریخ پرداخت", "ذی‌نفع و شرح", "مبلغ (ریال)", "دریافت کالا یا خدمت", "در فهرست ۲۹ اسفند؟", "نتیجه"],
        ["5012", "۵ فروردین", "شرکت آلفا، خرید مواد", "4,200,000", "۲۰ اسفند", "بله", "ثبت شده"],
        ["5013", "۸ فروردین", "خدمات دلتا، حق‌الزحمه خدمات", "1,200,000", "آبان", red("خیر"), red("بدهی ثبت‌نشده")],
        ["5014", "۱۰ فروردین", "صنایع گاما، خرید مواد", "3,100,000", "۶ فروردین", "خیر", "دوره بعد"],
        ["5015", "۱۵ فروردین", "اجاره انبار، فروردین", "900,000", "فروردین", "خیر", "دوره بعد"],
        ["5016", "۱۸ فروردین", "بازرگانی بتا، علی‌الحساب", "2,000,000", "اسفند", "بله", "ثبت شده"],
    ]
    K.table(s, lx, 2.02, lw, [0.62, 1.00, 2.10, 1.05, 1.05, 0.90, 1.023], data, row_h=0.50,
            header_h=0.62, size=9, header_size=8.5, align=["c", "c", "r", "c", "c", "c", "c"],
            valign="m", row_colors={2: "FBF1F1"}, qa_tag="s20")
    y = 5.26
    K.rect(s, lx, y, lw, 0.70, fill=T.BG_TINT, line=None, radius=0.06)
    K.txt(s, lx + 0.18, y, lw - 0.36, 0.70,
          items=[{"segs": [
              {"text": "نتیجه کاربرگ:  ", "size": 9.5, "bold": True, "color": T.NAVY},
              {"text": "یک قلم بدهی ثبت‌نشده به مبلغ 1,200,000 ریال کشف شد و به کاربرگ بدهی‌های ثبت‌نشده منتقل می‌شود. "
                       "توالی چک‌های 5012 تا 5016 بدون افتادگی است.", "size": 9.5, "color": T.TEXT}]}],
          anchor="m", ls=1.35)
    K.txt(s, lx, 6.08, lw, 0.50,
          "پرسش حسابرس درباره هر پرداخت: کالا یا خدمت چه زمانی دریافت شده است؟ اگر پیش از تاریخ ترازنامه بوده و در فهرست نیست، بدهی ثبت‌نشده است.",
          size=8.5, color=T.MUTED, ls=1.3)
    K.footer(s, num, TOTAL)


# ------------------------------------------------------------------ 21
def slide_unrecorded_wp(prs, num):
    s = K.blank(prs, T.WHITE)
    K.header(s, KICKER, "کاربرگ کتاب: حساب‌های پرداختنی ثبت‌نشده")
    context_line(s, "شرکت تولیدی تهران (سهامی خاص)   •   سال مالی منتهی به ۳۱ شهریور   •   مبالغ به ریال",
                 tag="شکل ۱۵-۴ کتاب", tag_w=1.35)

    tw = 7.72
    tx = RIGHT - tw
    data = [
        ["فاکتور", "فروشنده و شرح", "منظور شده به حساب", "مبلغ"],
        ["۲۸۵۱، ۳۱ شهریور", "شرکت آهن‌فروش: فاکتور و کالای در راه", "موجودی‌ها", "1,065,000"],
        ["—", "مؤسسه حقوقی: حق‌المشاوره پرداخت‌نشده", "هزینه‌های حقوقی", "100,000"],
        ["۴۲۸، ۲۸ شهریور", "شرکت تعمیرکار: تعمیر و نگهداری ماشین‌آلات (پرداخت ۳ مهر)", "هزینه تعمیر و نگهداری", "1,260,000"],
        ["۳۱ شهریور", "شرکت حق‌العمل‌کار: فروش کالای امانی در ۲۹ شهریور", "فروش", "2,568,000"],
        ["—", "شرکت ابزارفروش: کالا با گزارش دریافت ۲۹۰۷ در ۳۱ شهریور رسیده، فاکتور نرسیده", "موجودی‌ها", "1,582,000"],
        ["—", "شرکت مهندسی راه: حق‌الزحمه مهندسین ساختمان در دست تکمیل", "ساختمان در جریان تکمیل", "2,337,000"],
        [B("جمع"), "", "", B("8,912,000")],
    ]
    K.table(s, tx, 2.02, tw, [1.42, 3.45, 1.70, 1.15], data, row_h=0.52, header_h=0.44, size=9,
            header_size=9.5, align=["c", "r", "c", "c"], valign="m", row_colors={7: T.BG_TINT},
            qa_tag="s21")

    lx, lw = T.ML, 4.10
    K.rect(s, lx, 2.02, lw, 3.10, fill=T.BG_SOFT, line=None, radius=0.03)
    K.txt(s, lx + 0.16, 2.11, lw - 0.32, 0.26, "ثبت اصلاحی کاربرگ", size=10.5, color=T.NAVY,
          bold=True, ls=1.0, qa=False)
    K.table(s, lx + 0.12, 2.46, lw - 0.24, [1.90, 0.98, 0.98],
            [["حساب", "بدهکار", "بستانکار"],
             ["موجودی مواد و کالا", "2,647,000", ""],
             ["ساختمان‌های در جریان تکمیل", "2,337,000", ""],
             ["فروش", "2,568,000", ""],
             ["هزینه‌های حقوقی و قانونی", "100,000", ""],
             ["هزینه تعمیر و نگهداری", "1,260,000", ""],
             [B("حساب‌های پرداختنی"), "", B("8,912,000")]],
            row_h=0.36, header_h=0.36, size=8.5, header_size=8.5, header_fill=T.STEEL,
            align=["r", "c", "c"], zebra=False, row_colors={6: T.BG_TINT}, qa_tag="s21j")

    K.rect(s, lx, 5.26, lw, 1.34, fill=T.WHITE, line=T.GOLD, lw=1.0, radius=0.05)
    K.txt(s, lx + 0.16, 5.35, lw - 0.32, 0.26, "نتیجه‌گیری حسابرس در پای کاربرگ", size=9.5,
          color=T.GOLD_DEEP, bold=True, ls=1.0, qa=False)
    K.txt(s, lx + 0.16, 5.66, lw - 0.32, 0.88,
          "«به نظر اینجانب، مبلغ 8,912,000 ریال شامل تمام حساب‌های پرداختنی ثبت‌نشده بااهمیت است.»",
          size=9.5, color=T.NAVY, ls=1.45)
    K.footer(s, num, TOTAL)
