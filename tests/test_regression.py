from pathlib import Path
import importlib.util, unittest, tempfile, subprocess, sys, json, zipfile, io, os
R=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

class Assets(unittest.TestCase):
    def test_absolute_relative_relationships_and_xml_attributes(self):
        m=load('xlsx',R/'scripts/xlsx_cellimage_map.py')
        for target in ['/xl/worksheets/sheet1.xml','worksheets/sheet1.xml']:
            with zipfile.ZipFile(io.BytesIO(),'w') as z:
                z.writestr('xl/workbook.xml','<workbook xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet r:id="rId1" name="A &amp; B" /></sheets></workbook>')
                z.writestr('xl/_rels/workbook.xml.rels',f'<Relationships><Relationship Target="{target}" Id="rId1" /></Relationships>')
                self.assertEqual(m.sheet_map(z),{'A & B':'xl/worksheets/sheet1.xml'})
    def test_relationship_escape_rejected(self):
        m=load('xlsx',R/'scripts/xlsx_cellimage_map.py')
        with self.assertRaises(ValueError): m.resolve_target('../../private')
    def test_xml_text_entities(self):
        m=load('xlsx',R/'scripts/xlsx_cellimage_map.py')
        self.assertEqual(m.text_of('<t>A &amp; B</t>'),'A & B')

if __name__=="__main__": unittest.main(verbosity=2)
