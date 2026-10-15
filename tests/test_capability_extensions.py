from pathlib import Path
import importlib.util,unittest,tempfile,json,sys,subprocess,os
ROOT=Path(__file__).resolve().parents[1]
def load(path):
    sys.path.insert(0,str(ROOT/'scripts'))
    spec=importlib.util.spec_from_file_location('extension',ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class AssetLedger(unittest.TestCase):
    def test_rights_unknown_holds_and_duplicates(self):
        m=load('scripts/build_asset_index.py')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'a.bin').write_bytes(b'asset');(p/'b.bin').write_bytes(b'asset')
            (p/'index.json').write_text(json.dumps({'assets':[{'file':'a.bin'},{'file':'b.bin','rights':'owned','rights_evidence':'Created by reviewer'}]}))
            rows=m.build(p/'index.json')['assets'];self.assertEqual(rows[0]['release_status'],'HOLD');self.assertEqual(rows[1]['duplicate_of'],'a.bin');self.assertFalse(rows[1]['rights_verified'])
    def test_escape_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'i.json';p.write_text(json.dumps({'assets':[{'file':'../outside'}]}))
            with self.assertRaises(ValueError):load('scripts/build_asset_index.py').build(p)
