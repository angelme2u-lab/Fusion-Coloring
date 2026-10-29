"""Regression tests for KDP art placement. No API calls or user content."""
import io
import re
import unittest
import base64
import json
import threading
import urllib.request
from PIL import Image
import folio_press

class PrintPlacementTests(unittest.TestCase):
    def test_wrap_cover_has_a_valid_catalog(self):
        for image in [None,self.sample()]:
            pdf=folio_press.build_cover_pdf('Cover test','Subtitle','Author','Back message',17,'white','#254AA6',False,image)
            root=int(re.search(rb'/Root (\d+) 0 R',pdf).group(1))
            self.assertIn(('%d 0 obj\n<< /Type /Catalog' % root).encode(),pdf)
            self.assertIn(b'/Count 1',pdf)

    def test_complete_book_endpoint_order_size_and_validation(self):
        server=folio_press.Press(('127.0.0.1',0),folio_press.Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def post(payload):
            request=urllib.request.Request('http://127.0.0.1:%d/complete-book' % server.server_port,
                json.dumps(payload).encode(),{'Content-Type':'application/json'})
            return urllib.request.urlopen(request)
        try:
            image=base64.b64encode(self.sample()).decode()
            payload={'pages':[{'kind':'art','image':image,'caption':'INSIDE FIRST'},
                              {'kind':'blank'},{'kind':'story','title':'INSIDE LAST','body':'A little story'}],
                'marks':True,'cover':{'title':'FRONT TITLE','subtitle':'For friends','author':'Author',
                    'blurb':'BACK MESSAGE','front_image':image,'back_image':image,'back_color':'#254AA6'}}
            with post(payload) as response:
                pdf=response.read()
                self.assertIn('complete.pdf',response.headers['Content-Disposition'])
            self.assertIn(b'/Count 5',pdf)
            self.assertEqual(pdf.count(b'/MediaBox [0 0 612 792]'),5)
            streams=re.findall(rb'stream\n(.*?)\nendstream',pdf,re.S)
            text_streams=[x for x in streams if b'BT /F' in x]
            self.assertIn(b'FRONT TITLE',text_streams[0])
            self.assertIn(b'BACK MESSAGE',text_streams[-1])
            self.assertLess(pdf.index(b'INSIDE FIRST'),pdf.index(b'INSIDE LAST'))
            self.assertIn(b'/DeviceRGB',pdf)
            for bad in [{'pages':[],'cover':payload['cover']},
                        {'pages':payload['pages'],'cover':{}},
                        {'pages':payload['pages'],'cover':{'title':'Bad','front_image':'invalid'}}]:
                with self.assertRaises(urllib.error.HTTPError) as error: post(bad)
                self.assertEqual(error.exception.code,400)
        finally:
            server.shutdown();server.server_close();thread.join()

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
