import sys, os
from spire.presentation import Presentation
src, outdir, first = sys.argv[1], sys.argv[2], int(sys.argv[3])
tag = sys.argv[4] if len(sys.argv) > 4 else ""
os.makedirs(outdir, exist_ok=True)
p = Presentation(); p.LoadFromFile(src)
for i in range(p.Slides.Count):
    img = p.Slides[i].SaveAsImageByWH(1600, 900)
    fn = os.path.join(outdir, f"s{first+i:02d}{tag}.png"); img.Save(fn); img.Dispose(); print(fn)
p.Dispose()
