"""Build the stage-1 Persian audit deck (slides 1-15)."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deck import kit as K
from deck import slides_a as A
from deck import slides_b as B

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "stage1.pptx")


SLIDES = [
    (1, lambda prs: A.slide_title(prs)),
    (2, A.slide_agenda), (3, A.slide_why), (4, A.slide_nature), (5, A.slide_classification),
    (6, A.slide_cycle), (7, A.slide_accrued), (8, A.slide_objectives),
    (9, B.slide_risk), (10, B.slide_segregation), (11, B.slide_controls2), (12, B.slide_assess),
    (13, B.slide_test_of_controls), (14, B.slide_program), (15, B.slide_worksheet),
]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=1)
    ap.add_argument("--to", dest="end", type=int, default=15)
    ap.add_argument("--out", dest="out", default=None)
    a = ap.parse_args()
    K.qa_reset()
    prs = K.deck()
    for num, fn in SLIDES:
        if a.start <= num <= a.end:
            if fn.__code__.co_argcount == 1:
                fn(prs)
            else:
                fn(prs, num)
    out = a.out or OUT
    os.makedirs(os.path.dirname(out), exist_ok=True)
    prs.save(out)
    print("saved", out, os.path.getsize(out) // 1024, "KB", "slides:", len(prs.slides._sldIdLst))
    print("QA issues:", len(K.QA))
    for q in K.QA:
        print(json.dumps(q, ensure_ascii=False))


if __name__ == "__main__":
    main()
