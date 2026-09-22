"""Extract local EPUB content and images into sanitized, traceable chapters."""
from pathlib import Path
from html import escape
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile, json, posixpath, hashlib, re
local=lambda tag:tag.rsplit('}',1)[-1]
def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def extract_epub(source, folder, bid, image_widths=None):
    folder.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(source) as z:
        c=ET.fromstring(z.read('META-INF/container.xml'));opf=next(e.attrib['full-path'] for e in c.iter() if local(e.tag)=='rootfile');base=posixpath.dirname(opf);package=ET.fromstring(z.read(opf))
        manifest={e.attrib['id']:{**e.attrib,'path':posixpath.normpath(posixpath.join(base,unquote(e.attrib['href'])))} for e in package.iter() if local(e.tag)=='item'}
        members=[manifest[e.attrib['idref']]['path'] for e in package.iter() if local(e.tag)=='itemref'];chapters=[];member_ids={name:f'c{i+1:03d}' for i,name in enumerate(members)}
        titles={};toc=[]
        for item in manifest.values():
            if item.get('media-type')=='application/x-dtbncx+xml':
                nav=ET.fromstring(z.read(item['path']));ns={'n':'http://www.daisy.org/z3986/2005/ncx/'}
                for point in nav.findall('.//n:navPoint',ns):
                    text=point.find('n:navLabel/n:text',ns);ref=point.find('n:content',ns)
                    if text is not None and ref is not None:
                        target=posixpath.normpath(posixpath.join(posixpath.dirname(item['path']),unquote(ref.attrib['src'].split('#')[0])));titles[target]=''.join(text.itertext())
        assets={};image_dir=folder/'images';image_dir.mkdir(exist_ok=True)
        for item in manifest.values():
            if item.get('media-type') in ('image/jpeg','image/png','image/gif','image/webp'):
                path=item['path'];name=hashlib.sha256(path.encode()).hexdigest()[:16]+Path(path).suffix.lower();(image_dir/name).write_bytes(z.read(path));assets[path]=f'reading/{bid}/images/{name}'
        allowed={'p','div','span','section','article','h1','h2','h3','h4','h5','h6','blockquote','ul','ol','li','b','strong','i','em','small','sub','sup','ruby','rt','rp','table','thead','tbody','tr','td','th','br','hr','a','figure','figcaption'}
        def render(el,member):
            tag=local(el.tag)
            if tag in ('script','style','head','iframe','object','form'):return ''
            if tag in ('img','image'):
                src=el.get('src') or el.get('{http://www.w3.org/1999/xlink}href') or '';path=posixpath.normpath(posixpath.join(posixpath.dirname(member),unquote(src)))
                width=next(((image_widths or {}).get(c) for c in el.get('class','').split() if c in (image_widths or {})),None)
                size=f' style="width:{int(width)}px"' if width else ''
                return '<img loading="lazy"'+size+' src="'+assets[path]+'" alt="'+escape(el.get('alt','书中插图'),quote=True)+'">' if path in assets else ''
            inner=escape(el.text or '')+''.join(render(child,member)+escape(child.tail or '') for child in el)
            if tag not in allowed:return inner
            attrs=''
            if el.get('id'):attrs+=' id="'+escape(member_ids[member]+'-'+el.get('id'),quote=True)+'"'
            if tag=='a':
                target=urlsplit(el.get('href',''));path=posixpath.normpath(posixpath.join(posixpath.dirname(member),unquote(target.path))) if target.path else member
                if not target.scheme and path in member_ids:attrs+=' href="#reading/'+bid+'/'+member_ids[path]+('~'+escape(target.fragment,quote=True) if target.fragment else '')+'"'
            if tag in ('td','th'):
                for attr in ('rowspan','colspan'):
                    if el.get(attr,'').isdigit():attrs+=' '+attr+'="'+el.get(attr)+'"'
            return '<'+tag+attrs+'>'+inner+('' if tag in ('br','hr') else '</'+tag+'>')
        volume='全书'
        for member in members:
            doc=ET.fromstring(z.read(member));body=next(e for e in doc.iter() if local(e.tag)=='body');title=titles.get(member) or next((''.join(e.itertext()) for e in doc.iter() if local(e.tag)=='title'),'书页')
            if member==members[0]:title='全书封面'
            if re.search(r'第.*卷',title):volume=title
            cid=member_ids[member];html=render(body,member);text=''.join(body.itertext())
            dump(folder/f'{cid}.json',{'id':cid,'title':title,'source_member':member,'html':html})
            chapters.append({'id':cid,'title':title,'volume':volume,'length':len(text.strip())})
        cover_id=next((e.get('content') for e in package.iter() if local(e.tag)=='meta' and e.get('name')=='cover'),None);cover=assets.get(manifest.get(cover_id,{}).get('path',''))
    return {'chapters':chapters,'sections':len(chapters),'cover':cover,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
