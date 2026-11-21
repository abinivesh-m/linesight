# -*- coding: utf-8 -*-
"""Re-render slide 3 (Technical Approach) only, inside the delivered deck.

Slide 4 (Working Prototype) is frozen: this script never rebuilds it, never
re-runs its layout and never rewrites its XML. It transplants a freshly built
slide 3 into NexussAI_LineSight_R2_Deck.pptx and reports the SHA-256 of
slide 4's XML before and after so the "untouched" claim can be checked.

Run:  python docs/build_slide3.py
"""

import hashlib
import sys
import zipfile
from copy import deepcopy

from pptx import Presentation

import build_slides_3_4 as b

SLIDE_3 = 3
SLIDE_4 = 4


def xml_hash(path, slide_no):
    with zipfile.ZipFile(path) as z:
        return hashlib.sha256(z.read(f"ppt/slides/slide{slide_no}.xml")).hexdigest()


def transplant_slide3(src_slide, dst_slide):
    """Replace every shape on dst_slide with the shapes built on src_slide."""
    src_tree = src_slide.shapes._spTree
    dst_tree = dst_slide.shapes._spTree

    for el in list(dst_tree):
        if el.tag.rsplit("}", 1)[-1] in ("nvGrpSpPr", "grpSpPr"):
            continue
        dst_tree.remove(el)

    for el in list(src_tree):
        if el.tag.rsplit("}", 1)[-1] in ("nvGrpSpPr", "grpSpPr"):
            continue
        dst_tree.append(deepcopy(el))


def main():
    deck_path = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else str(b.OUT)
    deck = Presentation(deck_path)
    assert len(deck.slides) == 10, len(deck.slides)

    before_4 = xml_hash(deck_path, SLIDE_4)

    # build slide 3 on a scratch copy of the team deck, then move only that slide over
    scratch = Presentation(str(b.SRC))
    b.build_technical(scratch.slides[SLIDE_3 - 1])
    transplant_slide3(scratch.slides[SLIDE_3 - 1], deck.slides[SLIDE_3 - 1])
    b.notes(deck.slides[SLIDE_3 - 1], b.NOTES_3)

    deck.save(deck_path)

    after_4 = xml_hash(deck_path, SLIDE_4)
    print("wrote:", deck_path)
    print("slide 4 xml sha256 before:", before_4)
    print("slide 4 xml sha256 after :", after_4)
    print("slide 4 untouched:", before_4 == after_4)


if __name__ == "__main__":
    main()
