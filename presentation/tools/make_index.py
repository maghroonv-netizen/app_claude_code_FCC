"""Rebuild index.html (preview page with download buttons and the read-aloud script)."""
import html
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from deck.script import SCRIPT, TITLES  # noqa: E402

FA = "۰۱۲۳۴۵۶۷۸۹"
fa = lambda n: "".join(FA[int(c)] for c in str(n))  # noqa: E731
B = "deliverables/Hesabresi-Hesabhaye-Pardakhtani"

cards = []
for n in range(1, 28):
    paras = "".join(
        f'<p class="turn">{html.escape(l)}</p>' if l == "(نفر بعدی)" else f"<p>{html.escape(l)}</p>"
        for l in SCRIPT[n].split("\n"))
    cards.append(f'''<section class="card" id="s{n}">
  <div class="num">اسلاید {fa(n)} از ۲۷ &nbsp;•&nbsp; {html.escape(TITLES[n])}</div>
  <img src="preview/slide-{n:02d}.jpg" alt="اسلاید {fa(n)}" loading="lazy">
  <details><summary>متن ارائه این اسلاید</summary><div class="script">{paras}</div></details>
</section>''')

page = f'''<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>حسابرسی حساب‌های پرداختنی و سایر بدهی‌ها – فایل‌های ارائه</title>
<style>
  body {{ margin:0; font-family: Tahoma, "Segoe UI", sans-serif; background:#eef2f6; color:#0f2a42; line-height:1.9; }}
  header {{ background:#0f2a42; color:#fff; padding:20px 16px; text-align:center; }}
  header h1 {{ margin:0 0 4px; font-size:19px; }}
  header p {{ margin:0 0 14px; font-size:13px; color:#c9d8e2; }}
  .btns {{ display:flex; gap:10px; justify-content:center; flex-wrap:wrap; }}
  .btn {{ display:inline-block; background:#c39a47; color:#081a2a; font-weight:bold; padding:10px 20px; border-radius:8px; text-decoration:none; font-size:14px; }}
  .btn.alt {{ background:#fff; }}
  .btn.small {{ background:transparent; color:#c9d8e2; border:1px solid #6e93ab; font-weight:normal; font-size:12.5px; padding:7px 14px; }}
  main {{ max-width:1000px; margin:0 auto; padding:16px; }}
  .note {{ background:#fff; border-right:4px solid #c39a47; padding:10px 14px; font-size:13px; border-radius:6px; margin-bottom:16px; }}
  .card {{ background:#fff; border-radius:10px; padding:12px; margin-bottom:18px; box-shadow:0 1px 4px rgba(15,42,66,.12); }}
  .card img {{ width:100%; height:auto; display:block; border:1px solid #ccd9e3; border-radius:6px; }}
  .num {{ font-size:13px; font-weight:bold; color:#9a7626; margin-bottom:6px; }}
  details {{ margin-top:8px; font-size:14px; }}
  summary {{ cursor:pointer; font-weight:bold; }}
  .script {{ background:#f3f6f9; padding:6px 14px; border-radius:6px; margin-top:8px; }}
  .script p {{ margin:8px 0; text-align:justify; }}
  .script p.turn {{ font-weight:bold; color:#9a7626; }}
</style>
</head>
<body>
<header>
  <h1>حسابرسی حساب‌های پرداختنی و سایر بدهی‌ها</h1>
  <p>ارائه کامل: ۲۷ اسلاید &nbsp;•&nbsp; دو فایل جدا: پاورپوینت و متن ارائه</p>
  <div class="btns">
    <a class="btn" href="{B}-Final.pptx" download>دانلود پاورپوینت کامل (PPTX)</a>
    <a class="btn alt" href="{B}-Matn-Eraeh.docx" download>دانلود متن ارائه (Word)</a>
  </div>
  <div class="btns" style="margin-top:10px">
    <a class="btn small" href="{B}-Stage1.pptx" download>فقط اسلایدهای ۱ تا ۱۵</a>
    <a class="btn small" href="{B}-Stage2.pptx" download>فقط اسلایدهای ۱۶ تا ۲۷</a>
  </div>
</header>
<main>
  <div class="note">این تصاویر فقط پیش‌نمایش هستند. نوشته کم‌رنگ انگلیسی بالای هر تصویر مربوط به ابزار تولید پیش‌نمایش است و در فایل پاورپوینت وجود ندارد. فاصله‌گذاری متن در PowerPoint ممکن است کمی متفاوت باشد.</div>
  {"".join(cards)}
</main>
</body>
</html>
'''
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(page)
print("index.html written")
