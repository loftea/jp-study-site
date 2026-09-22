#!/usr/bin/env python3
"""Import one user-supplied EPUB/PDF into the local reading shelf. No books are bundled."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, subprocess
from epub_reader import extract_epub, dump
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path);p.add_argument('--id',required=True)
    p.add_argument('--title',required=True);p.add_argument('--author',default='');p.add_argument('--language',default='日文')
    a=p.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',a.id) or a.id=='vocab-workbook':p.error('Use a unique lowercase book ID; vocab-workbook is reserved')
    source=a.source.resolve();folder=ROOT/'website/dist/reading'/a.id
    if folder.exists():p.error('Book ID already exists; choose another ID')
    if source.suffix.lower() not in ('.epub','.pdf'):p.error('Expected EPUB or PDF')
    folder.mkdir(parents=True)
    try:
        if source.suffix.lower()=='.epub':
            book=extract_epub(source,folder,a.id)
            book.update(format='EPUB',reader_type='epub')
        else:
            info=subprocess.check_output(['pdfinfo',str(source)],text=True)
            count=int(re.search(r'^Pages:\s+(\d+)',info,re.M)[1]);pages=folder/'pages';pages.mkdir()
            subprocess.run(['pdftoppm','-scale-to','1600','-jpeg',str(source),str(pages/'page')],check=True)
            images=sorted(pages.glob('page-*.jpg'))
            for n,img in enumerate(images,1):img.rename(pages/f'normalized-{n:03d}.jpg')
            for n in range(1,count+1):(pages/f'normalized-{n:03d}.jpg').rename(pages/f'page-{n:03d}.jpg')
            shutil.copy2(source,folder/'original.pdf')
            book={'format':'PDF','reader_type':'pdf_pages','pages':count,'cover':f'reading/{a.id}/pages/page-001.jpg','original_url':f'reading/{a.id}/original.pdf'}
        book.update(id=a.id,title=a.title,author=a.author,language=a.language,category='本机导入',description='用户自行提供的阅读材料；未代表已读或已掌握。',source_path=source.name,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        target=ROOT/'website/dist/data/reading-library.json'
        data=json.loads(target.read_text()) if target.exists() else {'books':[]}
        if any(b['id']==a.id for b in data['books']):raise ValueError('Duplicate book ID')
        data['books'].append(book);dump(target,data);dump(ROOT/'study/library/reading/catalog.json',data)
    except Exception:
        shutil.rmtree(folder)
        raise
    print('Imported local book; generated content is excluded from Git.')
if __name__=='__main__':main()
