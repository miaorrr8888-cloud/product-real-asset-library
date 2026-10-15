from pathlib import Path
import importlib.util, unittest, tempfile, subprocess, sys, json, zipfile, io, struct, os
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

class MediaRobustness(unittest.TestCase):
    def setUp(self): self.m=load('probe',ROOT/'scripts/media_probe.py')
    def test_common_formats_have_real_dimensions(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            for ext in ['png','jpg','gif','bmp','webp']:
                p=Path(d)/('image.'+ext); Image.new('RGB',(12,9),'white').save(p)
                self.assertEqual(self.m.dims(p,ext),(12,9)); self.assertEqual(self.m.inspect(p)['status'],'OK')
    def test_truncated_jpeg_does_not_loop(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.jpg'; p.write_bytes(bytes.fromhex('ffd8ffe00000'))
            self.assertIsNone(self.m.jpg_size(p))
    def test_mp4_uses_bounded_header_reads(self):
        def atom(name,data): return struct.pack('>I4s',len(data)+8,name)+data
        payload=atom(b'moov',atom(b'mvhd',bytes(12)+struct.pack('>II',1000,2500))+atom(b'trak',atom(b'tkhd',bytes(76)+struct.pack('>II',320*65536,240*65536))))
        class Bounded(io.BytesIO):
            def fileno(self): return 1
            def read(self,n=-1):
                if n<0 or n>32: raise AssertionError('unbounded video read')
                return super().read(n)
        with patch('builtins.open',return_value=Bounded(payload)),patch.object(self.m.os,'fstat',return_value=type('S',(),{'st_size':len(payload)})()):
            self.assertEqual(self.m.mp4_info('fixture.mp4'),(2.5,(320,240)))
    def test_fake_atoms_in_media_payload_are_not_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fake.mp4'; data=b'noise-mvhd-and-tkhd-noise'; p.write_bytes(struct.pack('>I4s',len(data)+8,b'mdat')+data)
            self.assertEqual(self.m.mp4_info(p),(None,None))
    def test_bad_video_does_not_hide_good_image(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); Image.new('RGB',(5,6)).save(p/'good.png'); (p/'bad.mp4').write_bytes(b'broken')
            r=subprocess.run([sys.executable,str(ROOT/'scripts/media_probe.py'),d,'--json'],capture_output=True,text=True)
            self.assertEqual(r.returncode,1); self.assertEqual(len(json.loads(r.stdout)['files']),2)
    def test_wps_namespace_and_reversed_relationship_attributes(self):
        m=load('xlsx',ROOT/'scripts/xlsx_cellimage_map.py')
        with zipfile.ZipFile(io.BytesIO(),'w') as z:
            z.writestr('xl/cellimages.xml','<root xmlns:p="urn:picture" xmlns:q="urn:drawing" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:pic><p:cNvPr name="ID_DEMO"/><q:blip r:embed="rId1"/></p:pic></root>')
            z.writestr('xl/_rels/cellimages.xml.rels','<Relationships><Relationship Target="/xl/media/image1.png" Id="rId1"/><Relationship TargetMode="External" Target="https://example.org/p.png" Id="rId2"/></Relationships>')
            self.assertEqual(m.cellimages(z),{'ID_DEMO':'xl/media/image1.png'})
    def test_shared_strings_with_prefix_and_entities(self):
        m=load('xlsx',ROOT/'scripts/xlsx_cellimage_map.py')
        with zipfile.ZipFile(io.BytesIO(),'w') as z:
            z.writestr('xl/sharedStrings.xml','<s:sst xmlns:s="urn:sheet"><s:si><s:r><s:t>Demo &amp; </s:t></s:r><s:r><s:t>Unit</s:t></s:r></s:si></s:sst>')
            self.assertEqual(m.load_strings(z),['Demo & Unit'])

if __name__=="__main__": unittest.main()
