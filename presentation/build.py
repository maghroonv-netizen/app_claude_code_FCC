"""Build the Persian audit deck (chapter 15: accounts payable and other liabilities).

    python3 build.py                 -> all deliverables (final deck, stage files, script .docx)
    python3 build.py --from 16 --to 20 --out scratch/part.pptx   -> any slide range
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from deck import kit as K                  # noqa: E402
from deck import slides_a as A             # noqa: E402
from deck import slides_b as B             # noqa: E402
from deck import slides_c as C             # noqa: E402
from deck import slides_d as D             # noqa: E402
from deck.script import SCRIPT, TITLES     # noqa: E402

OUT_DIR = os.path.join(HERE, "deliverables")
BASE = "Hesabresi-Hesabhaye-Pardakhtani"

SLIDES = [
    (1, A.slide_title), (2, A.slide_agenda), (3, A.slide_why), (4, A.slide_nature),
    (5, A.slide_classification), (6, A.slide_cycle), (7, A.slide_accrued), (8, A.slide_objectives),
    (9, B.slide_risk), (10, B.slide_segregation), (11, B.slide_controls2), (12, B.slide_assess),
    (13, B.slide_test_of_controls), (14, B.slide_program), (15, B.slide_worksheet),
    (16, C.slide_vouch_reconcile), (17, C.slide_reconciliation_wp), (18, C.slide_confirmation),
    (19, C.slide_analytics), (20, C.slide_subsequent), (21, C.slide_unrecorded_wp),
    (22, D.slide_materiality), (23, D.slide_related_presentation), (24, D.slide_other_liabilities),
    (25, D.slide_accrued_wp), (26, D.slide_summary), (27, D.slide_references),
]


def build(start, end, out):
    """Build slides start..end into `out`; speaker notes = read-aloud script only."""
    K.qa_reset()
    prs = K.deck()
    for num, fn in SLIDES:
        if start <= num <= end:
            if fn.__code__.co_argcount == 1:
                fn(prs)
            else:
                fn(prs, num)
            K.notes(prs.slides[len(prs.slides._sldIdLst) - 1], SCRIPT[num])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    prs.save(out)
    n = len(prs.slides._sldIdLst)
    print(f"saved {os.path.relpath(out, HERE)}  {os.path.getsize(out) // 1024} KB  slides: {n}  QA issues: {len(K.QA)}")
    for q in K.QA:
        print("  ", json.dumps(q, ensure_ascii=False))
    return len(K.QA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=None)
    ap.add_argument("--to", dest="end", type=int, default=None)
    ap.add_argument("--out", dest="out", default=None)
    a = ap.parse_args()
    if a.out:
        build(a.start or 1, a.end or len(SLIDES), os.path.join(HERE, a.out) if not os.path.isabs(a.out) else a.out)
        return
    issues = build(1, len(SLIDES), os.path.join(OUT_DIR, BASE + "-Final.pptx"))
    issues += build(1, 15, os.path.join(OUT_DIR, BASE + "-Stage1.pptx"))
    issues += build(16, len(SLIDES), os.path.join(OUT_DIR, BASE + "-Stage2.pptx"))
    from deck.script_doc import write_script_docx
    path = os.path.join(OUT_DIR, BASE + "-Matn-Eraeh.docx")
    words = write_script_docx(path, SCRIPT, TITLES)
    print(f"saved {os.path.relpath(path, HERE)}  {os.path.getsize(path) // 1024} KB  words: {words}")
    print("total QA issues:", issues)


if __name__ == "__main__":
    main()
