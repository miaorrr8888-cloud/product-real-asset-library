"""Create a source/rights ledger for explicitly listed local assets."""
import argparse,hashlib,json
from pathlib import Path
from urllib.parse import urlsplit

def build(manifest):
    manifest=Path(manifest).resolve(); data=json.loads(manifest.read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict) or not isinstance(data.get('assets'),list): raise ValueError('assets array required')
    rows=[]; seen={}
    for entry in data['assets']:
        rel=entry.get('file'); rights=entry.get('rights','unknown'); source=entry.get('source_url')
        if not isinstance(rel,str): raise ValueError('file must be text')
        path=manifest.parent/rel
        if path.is_symlink() or not path.resolve().is_relative_to(manifest.parent) or not path.is_file(): raise ValueError('asset must be a local file within manifest directory')
        if rights not in {'owned','licensed','public_domain','unknown'}: raise ValueError('invalid rights')
        if source:
            u=urlsplit(source)
            if u.scheme!='https' or not u.hostname or u.username or u.password: raise ValueError('invalid source URL')
        with path.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
        evidence=entry.get('rights_evidence')
        ready=rights!='unknown' and isinstance(evidence,str) and bool(evidence.strip())
        rows.append({'file':rel,'sha256':digest,'bytes':path.stat().st_size,'source_url':source,
                     'rights':rights,'rights_evidence':evidence,'release_status':'READY_FOR_REVIEW' if ready else 'HOLD',
                     'duplicate_of':seen.get(digest),'source_verified':False,'rights_verified':False})
        seen.setdefault(digest,rel)
    return {'assets':rows,'notice':'Source and rights are supplied declarations, not legal verification.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest');a=p.parse_args()
    try: result=build(a.manifest)
    except (OSError,ValueError,TypeError) as e:p.exit(2,'Input error: '+str(e)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
if __name__=='__main__':main()
