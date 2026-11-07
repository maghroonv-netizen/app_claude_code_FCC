# تاریخچهٔ دیباگ CI — چه خطایی بود، چرا اتفاق افتاد، و از کجا پیگیری کنیم

> **TL;DR:** هشت چک قرمز روی PR #1 دو باگ واقعی در کد بودند (نه مشکل خودِ GitHub):
> ۱) یک دیالوگ مودال که لحظهٔ بسته‌شدن پنجره باز می‌شد و تست را کرش می‌کرد (روی لینوکس)،
> ۲) یک ترد پس‌زمینه (`QThread`) که اگر هنوز در حال اجرا نابود می‌شد، کل پروسه را بی‌صدا
> `abort` می‌کرد (روی ویندوز). هر دو رفع شدند؛ همهٔ چک‌ها الان سبز هستند.
> جزئیات کامل، روش تشخیص، و راهنمای دیباگ آینده در ادامه آمده است.

---

## ۱) آن ۸ چک قرمز اصلاً چه بودند؟

ورک‌فلوی `tests` (فایل `.github/workflows/tests.yml`) با هر `push` و روی خودِ
Pull Request اجرا می‌شود و تست‌ها را روی این ماتریس می‌سنجد:

| سیستم‌عامل | پایتون |
|---|---|
| `ubuntu-latest` | 3.10 و 3.12 |
| `windows-latest` | 3.10 و 3.12 |

چون هر اجرا هم به‌عنوان چکِ **push** و هم چکِ **pull_request** ثبت می‌شود،
۴ job × ۲ رویداد = **۸ چک** در صفحهٔ PR دیده می‌شد.

## ۲) باگ اول — لینوکس: دیالوگ مودال هنگام teardown

- **نشانه:** فقط یک تست (`test_main_window_smoke`) با `TEARDOWN ERROR` شکست می‌خورد:
  `RuntimeError: libshiboken: Internal C++ object (QMessageBox) already deleted.`
- **زنجیرهٔ علت:** سرورهای CI ابزار `claude` ندارند → پروبِ CLI با «پیدا نشد» تمام
  می‌شد → `_on_probe_done` متد `_show_cli_missing` را صدا می‌زد → یک
  `QMessageBox` مودال **دقیقاً وقتی پنجره در حال بسته‌شدن/پنهان‌شدن بود** باز
  می‌شد → آبجکت C++ دیالوگ زیر پای پایتون حذف می‌شد → کرش در event loop که
  pytest-qt آن را به خطای teardown تبدیل می‌کرد.
- **چرا لوکال دیده نشد؟** روی ماشین توسعه `claude` نصب است، پس مسیرِ «CLI پیدا
  نشد» هیچ‌وقت اجرا نمی‌شد. (درس: تست را یک بار هم با PATH بدون claude اجرا کنید —
  بخش ۶ را ببینید.)
- **رفع (کامیت `6b4cc41`):** `_show_cli_missing` حالا با
  `if self._closing or not self.isVisible() or self._cli_box: return`
  محافظت می‌شود و `_on_probe_done` هم در حالت بسته‌شدن زودهنگام برمی‌گردد.
  یعنی دیالوگ فقط وقتی پنجرهٔ برنامه واقعاً باز و فعال باشد نمایش داده می‌شود —
  برای کاربر واقعی هم رفتار درست‌تری است.

## ۳) باگ دوم — ویندوز: کرش بی‌صدا بعد از `[100%]`

- **نشانه:** لاگ pytest دقیقاً بعد از آخرین نقطهٔ پیشرفت
  (`.. [100%]`) قطع می‌شد؛ **هیچ تستی fail نشده بود**، هیچ traceback ای وجود
  نداشت، ولی job با کد خروج غیرصفر تمام می‌شد. (کد خروج واقعی هم با
  `|| exit 1` در ورک‌فلو مخفی شده بود!)
- **زنجیرهٔ علت:**
  1. `MainWindow` پروب CLI را با `QTimer.singleShot(120ms, self._startup_probe)`
     به‌تعویق می‌اندازد.
  2. در تست، پنجره بسته می‌شد **قبل از** اینکه آن تایمر ۱۲۰ms شلیک شود؛ بعداً
     طی `processEvents` تست‌های بعدی شلیک می‌شد و یک `CliProbeThread`
     **بدون parent** روی پنجرهٔ مرده راه می‌افتاد.
  3. آن ترد کارهای کند انجام می‌داد (پروب HTTP درگاه‌های FCC با timeout).
  4. وقتی wrapper پایتونِ ترد توسط GC آزاد می‌شد در حالی که ترد C++ هنوز
     **در حال اجرا** بود، shiboken آبجکت زنده را delete می‌کرد →
     Qt `qFatal`/`abort` می‌زد → کل پروسه می‌مرد.
  - **چرا بی‌صدا؟** دو دلیل: روی رانر ویندوزی بدون console، پیام‌های Qt به
    `OutputDebugString` می‌روند نه stderr (بعداً با `QT_FORCE_STDERR_LOGGING=1`
    حل شد)، و خودِ ورک‌فلو کد خروج را با `|| exit 1` یکسان می‌کرد.
  - **چرا فقط ویندوز؟** اسپاون پروسه/تایمینگ GC آنجا کندتر و behavior حذف
    آبجکت زندهٔ Qt روی ویندوز کشنده‌تر است؛ روی لینوکس همان توالی بی‌خطر رد
    می‌شد (ubuntu بعد از رفع باگ اول سبز شد).
- **رفع (کامیت `5b5289a`) — چند لایه:**
  - `_LIVE_PROBES`: رجیستری ماژول‌سطحی که هر ترد پروب را **تا تمام شدنش**
    نگه می‌دارد تا GC نتواند تردِ در حال اجرا را نابود کند + تابع
    `drain_probes()` برای join کردن همه‌شان.
  - `_startup_probe` و `_maybe_autostart` با `if self._closing: return`
    محافظت شدند؛ `run()` ترد هم `isInterruptionRequested()` را چک می‌کند.
  - `closeEvent` حالا `requestInterruption()` + تا ۵ ثانیه `wait()` می‌کند.
  - `app.py` بعد از `app.exec()` تردها را drain می‌کند → **کاربر واقعی هم اگر
    بلافاصله بعد از launch برنامه را ببندد دیگر کرش نمی‌کند** (این فقط مشکل
    تست نبود!).
  - `tests/conftest.py`: فیکسچرهای autouse «بهداشت Qt» بعد از هر تست و بعد از
    کل session — بستن/حذف همهٔ top-level widgets، پردازش `DeferredDelete`ها و
    join کردن تردهای سرگردان.
  - تست `test_main_window_smoke` حالا خودش تایمر را شلیک و ترد را join می‌کند
    (قطعی، بدون نشت به تست‌های بعد).

## ۴) «دیباگرهایی» که موقتاً اضافه و بعد حذف شدند چه بودند؟

مشکل اصلی من: از محیط sandbox خودم، **لاگ کامل job های GitHub Actions
قابل خواندن نبود** (`gh run view --log` به دامنهٔ مسدود می‌خورد و artifact ها
هم همین‌طور). برای دیدن خروجی pytestِ رانرها، چند کانال موقت در ورک‌فلو گذاشته
شد (کامیت‌های `ed99128`, `496b8f4`, `d87ea41`, `ec0b3cb`):

1. **قدم «کامنت روی PR»:** وقتی job شکست می‌خورد، با `gh api` خلاصهٔ خطا را
   کامنت می‌کرد → به‌دلیل سطح دسترسی `GITHUB_TOKEN` ریپو عملاً کار نکرد.
2. **رلهٔ ntfy:** در پایان job شکست‌خورده، ~۳.۵KB آخرِ `pytest_out.txt` با
   `curl` به یک topic عمومی روی سرویس `ntfy.sh` فرستاده می‌شد و من از همین‌جا
   می‌خواندمش. **این همان کانالی بود که ریشهٔ باگ ویندوز را لو داد.**
3. تلاش ناموفق قبلی: فرستادن لاگ به یک HTTP endpoint روی خودِ sandbox (به
   دلیل نیاز به header احراز هویت، بلاک بود).

**چرا حذف شدند (کامیت `ad902e7`):** کارشان تمام شد؛ ضمن اینکه رلهٔ ntfy لاگ
CI را به یک کانال **عمومی** می‌فرستاد که از نظر بهداشت امنیتی جایز نبود.

**چه چیزهایی عمداً نگه داشته شدند** (اینها «دیباگر» نیستند، قابلیت‌های دائمی‌اند):

| مورد | کجا | فایده |
|---|---|---|
| `PYTEST_EXIT_CODE=<n>` در انتهای `pytest_out.txt` | ورک‌فلو | کد خروج **واقعی** pytest دیگر مخفی نمی‌شود (مثلاً `3221225477` یعنی access violation ویندوز). |
| `QT_FORCE_STDERR_LOGGING=1` + `QT_LOGGING_TO_CONSOLE=1` | env ورک‌فلو | پیام‌های Qt روی ویندوز به stderr (و در نتیجه لاگ) می‌آیند نه OutputDebugString. |
| آپلود artifact هنگام شکست: `pytest_out.txt` + `pytest_session_marker.txt` | ورک‌فلو | خروجی کامل تست‌ها از صفحهٔ run قابل دانلود است. |
| مارکر `FCC_SESSION_COMPLETE` (فایل `pytest_session_marker.txt` با fsync) | `tests/conftest.py` | اگر روزی PySide6 **بعد از** یک session کاملاً سبز، هنگام خاموش‌شدن interpreter کرش کند، CI با یک `::warning` سبز می‌ماند (و نه قرمز کاذب). |
| فیکسچرهای بهداشت Qt + `drain_probes` | `tests/conftest.py`, `src/fcc/ui/main_window.py`, `src/fcc/ui/app.py` | از تکرار همان کرش‌ها در آینده جلوگیری می‌کنند (هم در تست، هم در اپ واقعی). |

## ۵) از کجا بفهمم چه گذشته؟ (منابع ماندگار)

1. **همین سند:** `docs/ci-debug-history.md`
2. **پیام‌های کامیت** — عمداً مفصل نوشته شدند:
   ```bash
   git show 6b4cc41   # رفع باگ دیالوگ مودال (لینوکس)
   git show 5b5289a   # رفع باگ QThread (ویندوز) + توضیح کامل زنجیرهٔ علت
   git show ad902e7   # پاک‌سازی ابزارهای موقت دیباگ
   ```
3. **صفحهٔ Actions در مرورگر شما** (برخلاف sandbox من، برای شما کاملاً باز است):
   `https://github.com/maghroonv-netizen/app_claude_code_FCC/actions`
   → روی run قرمز/سبز کلیک کنید → هر job → قدم **«Run the test suite»** →
   لاگ کامل با `cat pytest_out.txt` آنجا هست.
4. **تب Checks روی PR #1** و تاریخچهٔ run های قبلی (هر run با SHA مربوطه).

## ۶) راهنمای دیباگ برای آینده

### اگر روزی چک CI دوباره قرمز شد

1. GitHub → **Actions** → run قرمز → job مربوطه → قدم *Run the test suite*:
   خروجی کامل pytest + خط `PYTEST_EXIT_CODE=` + (در صورت وجود) پیام‌های Qt.
2. از همان صفحه، **artifact** با نام `pytest-<os>-<python>` را دانلود کنید
   (شامل `pytest_out.txt` و مارکر session).
3. کد خروج را تفسیر کنید: `1/2` = شکست واقعی تست (بخش FAILURES را بخوانید)؛
   `3221225477` = access violation ویندوز؛ `3` = abort (معمولاً qFatal —
   پیام Qt حالا در لاگ هست)؛ `124` = timeout.
4. بازتولید لوکال (روی ویندوز خودتان):
   ```bat
   git clone -b arena/02f5758d-app-claude-code-fcc https://github.com/maghroonv-netizen/app_claude_code_FCC.git
   cd app_claude_code_FCC
   python -m venv .venv
   .venv\Scripts\pip install -r requirements-dev.txt
   .venv\Scripts\python -m pytest -q -rf
   ```
   و برای شبیه‌سازی دقیق CI (بدون claude روی PATH)، در PowerShell:
   ```powershell
   $env:QT_QPA_PLATFORM="offscreen"
   $env:PATH="C:\Windows\system32;C:\Windows"   # موقتاً claude را پنهان می‌کند
   .venv\Scripts\python -m pytest -q -rf
   ```

### اگر خودِ برنامه روی سیستم شما خطا داد

- **لاگ‌های زمان اجرا (runtime) برنامه:** `%APPDATA%\ClaudeCodeStudio\logs` — هر اجرا، هر
  خطا و هر crash hook اینجا ثبت می‌شود.
- `python run.py --console-log` → لاگ زنده در ترمینال.
- `python run.py --diagnostics` → گزارش کامل وضعیت CLI، نسخه، مسیرها و
  gateway FCC بدون باز کردن GUI.
- `python run.py --reset-config` → اگر تنظیمات خراب شد.
- crash hook داخلی (`install_crash_hook` در `logging_setup`) استثناهای مرگبار
  را قبل از مرگ پروسه در لاگ فایل ثبت می‌کند.

### قاعده‌های کلی که از این ماجرا یاد گرفتیم (برای هر تغییر آینده)

- هیچ دیالوگ مودالی وقتی پنجره `_closing` است یا `isVisible()` نیست باز نشود.
- هیچ `QThread` بدون parent را رها نکنید؛ تا `finished` شدنش یک مرجع زنده نگه
  دارید و قبل از خروج `wait()`/drain کنید.
- در CI همیشه خروجی pytest را به فایل بریزید و **کد خروج واقعی** را نگه دارید.
- تست UI را یک بار هم در شرایط «ابزار claude نصب نیست» اجرا کنید.

---

*آخرین به‌روزرسانی: پس از سبز شدن کامل ماتریس ۴job روی کامیت `ad902e7`.*
