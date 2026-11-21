from pptx import Presentation
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
p = Presentation(r'C:\Users\abini\Downloads\NexussAI_LineSight_R2_Deck.pptx')
print('slides:', len(p.slides))
for i, s in enumerate(p.slides, 1):
    txts = []
    for sh in s.shapes:
        if sh.has_text_frame:
            for para in sh.text_frame.paragraphs:
                if para.text.strip():
                    txts.append(para.text.strip()[:70])
    print(i, '|', ' ; '.join(txts)[:150])