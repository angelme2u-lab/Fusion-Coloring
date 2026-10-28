"""Regression tests for KDP art placement. No API calls or user content."""
import io
import re
import unittest
from PIL import Image
import folio_press

class PrintPlacementTests(unittest.TestCase):
    def sample(self, width=1024, height=1536):
        image=Image.new("RGB",(width,height),"white")
        for x in range(100,900):
            image.putpixel((x,400),(0,0,0))
        buf=io.BytesIO()
        image.save(buf,format="PNG")
        return buf.getvalue()

    def test_letter_pdf_and_larger_art(self):
        pdf=folio_press.build_pdf([{"kind":"art","png":self.sample(),"caption":""}],marks=False)
        self.assertIn(b"/MediaBox [0 0 612 792]",pdf)
        placements=re.findall(rb"q ([0-9.]+) 0 0 ([0-9.]+) ([0-9.]+) ([0-9.]+) cm /Im",pdf)
        self.assertEqual(len(placements),1)
        w,h,x,y=map(float,placements[0])
        self.assertGreater(w,470)  # more coverage than previous 440pt portrait
        self.assertLessEqual(w+x,580.1)
        self.assertGreaterEqual(x,31.9)
        self.assertGreaterEqual(y,31.9)
        self.assertLessEqual(h+y,764.1)
        embedded=re.search(rb"/Subtype /Image /Width ([0-9]+) /Height ([0-9]+)",pdf)
        self.assertIsNotNone(embedded)
        self.assertGreaterEqual(int(embedded.group(1)),round(w/72*300)-1)

    def test_marks_keep_bottom_reserve(self):
        pdf=folio_press.build_pdf([{"kind":"art","png":self.sample(),"caption":""}],marks=True)
        placements=re.findall(rb"q ([0-9.]+) 0 0 ([0-9.]+) ([0-9.]+) ([0-9.]+) cm /Im",pdf)
        self.assertEqual(len(placements),1)
        w,h,x,y=map(float,placements[0])
        self.assertGreaterEqual(y,55)
        self.assertLessEqual(h+y,765)

if __name__=="__main__":
    unittest.main()
