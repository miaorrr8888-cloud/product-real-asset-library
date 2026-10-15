"""Inspect common images and MP4/MOV headers without decoding or uploading media."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

IMG_EXT={"png","jpg","jpeg","webp","bmp","gif"}
VID_EXT={"mp4","mov","m4v"}

def png_size(p):
    with open(p,'rb') as f: d=f.read(24)
    if len(d)<24 or d[:8]!=b'\x89PNG\r\n\x1a\n' or d[12:16]!=b'IHDR': return None
    return struct.unpack('>II',d[16:24])

def jpg_size(p):
    with open(p,'rb') as f:
        if f.read(2)!=b'\xff\xd8': return None
        while True:
            b=f.read(1)
            while b and b!=b'\xff': b=f.read(1)
            if not b: return None
            marker=f.read(1)
            while marker==b'\xff': marker=f.read(1)
            if not marker: return None
            m=marker[0]
            if m in (0xD9,0xDA): return None
            if m==0xD8 or 0xD0<=m<=0xD7: continue
            size=f.read(2)
            if len(size)!=2: return None
            length=struct.unpack('>H',size)[0]
            if length<2: return None
            if 0xC0<=m<=0xCF and m not in (0xC4,0xC8,0xCC):
                d=f.read(5)
                if len(d)!=5: return None
                h,w=struct.unpack('>HH',d[1:5]); return w,h
            f.seek(length-2,1)

def webp_size(p):
    with open(p,'rb') as f: d=f.read(32)
    if len(d)<25 or d[:4]!=b'RIFF' or d[8:12]!=b'WEBP': return None
    tag=d[12:16]
    if tag==b'VP8X' and len(d)>=30:
        return int.from_bytes(d[24:27],'little')+1,int.from_bytes(d[27:30],'little')+1
    if tag==b'VP8 ' and len(d)>=30 and d[23:26]==b'\x9d\x01\x2a':
        return int.from_bytes(d[26:28],'little')&0x3FFF,int.from_bytes(d[28:30],'little')&0x3FFF
    if tag==b'VP8L' and d[20]==0x2F:
        bits=int.from_bytes(d[21:25],'little'); return (bits&0x3FFF)+1,((bits>>14)&0x3FFF)+1
    return None

def dims(p,ext):
    try:
        if ext=='png': return png_size(p)
        if ext in {'jpg','jpeg'}: return jpg_size(p)
        if ext=='webp': return webp_size(p)
        with open(p,'rb') as f: d=f.read(32)
        if ext=='gif' and len(d)>=10 and d[:6] in {b'GIF87a',b'GIF89a'}: return struct.unpack('<HH',d[6:10])
        if ext=='bmp' and len(d)>=26 and d[:2]==b'BM':
            width,height=struct.unpack('<ii',d[18:26]); return abs(width),abs(height)
    except (OSError,struct.error): return None
    return None

def mp4_info(p):
    """Read bounded atom headers; never load mdat or the whole video into RAM."""
    duration=None; dimensions=None; seen=0
    with open(p,'rb') as f:
        total=os.fstat(f.fileno()).st_size
        def walk(start,end,depth=0):
            nonlocal duration,dimensions,seen
            position=start
            while position+8<=end and seen<10000 and depth<6:
                seen+=1; f.seek(position); header=f.read(8)
                if len(header)!=8: return
                size,kind=struct.unpack('>I4s',header); skip=8
                if size==1:
                    d=f.read(8)
                    if len(d)!=8: return
                    size=struct.unpack('>Q',d)[0]; skip=16
                elif size==0: size=end-position
                if size<skip or position+size>end: return
                payload=position+skip; stop=position+size
                if kind in {b'moov',b'trak',b'mdia'}: walk(payload,stop,depth+1)
                elif kind==b'mvhd':
                    f.seek(payload); d=f.read(min(stop-payload,32))
                    if len(d)>=20 and d[0]==0: timescale,length=struct.unpack('>II',d[12:20])
                    elif len(d)>=32 and d[0]==1: timescale,length=struct.unpack('>IQ',d[20:32])
                    else: timescale=length=0
                    if timescale and length not in {0xFFFFFFFF,0xFFFFFFFFFFFFFFFF}: duration=length/timescale
                elif kind==b'tkhd' and stop-payload>=84:
                    f.seek(stop-8); d=f.read(8)
                    width,height=struct.unpack('>II',d)
                    if width and height: dimensions=(round(width/65536),round(height/65536))
                position=stop
        walk(0,total)
    return duration,dimensions

def inspect(path):
    p=Path(path); ext=p.suffix.lower().lstrip('.')
    result={'path':str(p),'resolution':None,'duration':None,'bytes':None,'sha256':None,'md5_10':None,'status':'UNKNOWN'}
    try:
        if ext in VID_EXT: result['duration'],result['resolution']=mp4_info(p)
        else: result['resolution']=dims(p,ext)
        sha=hashlib.sha256(); md5=hashlib.md5()
        with p.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''): sha.update(chunk); md5.update(chunk)
        result.update(bytes=p.stat().st_size,sha256=sha.hexdigest(),md5_10=md5.hexdigest()[:10])
        result['status']='OK' if result['resolution'] or result['duration'] is not None else 'PARTIAL'
    except (OSError,ValueError,struct.error) as exc:
        result.update(status='ERROR',error=type(exc).__name__)
    return result

def main(paths,json_output=False):
    files=[]; missing=[]
    for raw in paths:
        p=Path(raw)
        if not p.exists(): missing.append(str(p)); continue
        if p.is_dir():
            for dp,dn,fn in os.walk(p,followlinks=False):
                dn[:]=[d for d in dn if not (Path(dp)/d).is_symlink()]
                files.extend(Path(dp)/name for name in fn if not (Path(dp)/name).is_symlink())
        elif not p.is_symlink(): files.append(p)
    files=sorted({p for p in files if p.suffix.lower().lstrip('.') in IMG_EXT|VID_EXT})
    records=[inspect(p) for p in files]
    if json_output: print(json.dumps({'files':records,'missing_paths':missing},ensure_ascii=False,indent=2))
    else:
        print('STATUS\tRESOLUTION\tDURATION\tBYTES\tSHA256\tPATH')
        for r in records:
            resolution='x'.join(map(str,r['resolution'])) if r['resolution'] else 'UNKNOWN'
            print(f"{r['status']}\t{resolution}\t{r['duration']}\t{r['bytes']}\t{r['sha256']}\t{r['path']}")
        for path in missing: print('MISSING: '+path,file=sys.stderr)
    return 2 if missing or not records else (1 if any(r['status']!='OK' for r in records) else 0)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('paths',nargs='+'); parser.add_argument('--json',action='store_true')
    args=parser.parse_args(); raise SystemExit(main(args.paths,args.json))
