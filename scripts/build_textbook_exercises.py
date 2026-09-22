"""Attach original exercise pages to lessons without changing learning records."""
from pathlib import Path
import json,subprocess,concurrent.futures
ROOT=Path(__file__).resolve().parents[1];LIB=ROOT/'study/library';DIST=ROOT/'website/dist'
import argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',required=True,type=Path);args=parser.parse_args()
source=args.source.resolve()
LIB.mkdir(parents=True,exist_ok=True);(DIST/'data').mkdir(parents=True,exist_ok=True)
out=DIST/'images/textbook';out.mkdir(parents=True,exist_ok=True)
lessons={};items=[]
for n in range(1,25):
    lid=f'b{n:02d}';start=39+10*(n-1)+6*((n-1)//4)
    pages=[]
    for page in range(start+6,start+9):
        task=f'textbook-{lid}-page-{page}'
        pages.append({'page':page,'image':f'images/textbook/page-{page:03d}.jpg','response_id':task,'transcription_status':'original_scan'})
        items.append({'id':task,'group':lid,'prompt':f'《标日》初级上第{n}课教材练习，扫描第{page}页（请注明题号）。','answers':[],'target':'待教练结合原题核对。','source_type':'textbook_scan_exercise','source_page':page,'source_id':'beginner-upper-pdf','reference_status':'not_prepared'})
    lessons[lid]={'lesson_id':lid,'number':n,'pages':pages,'question_ids':[],'listening_audio_status':'not_linked'}
def render(page):
    dest=out/f'page-{page:03d}.jpg'
    if not dest.exists():subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-singlefile','-scale-to','1700','-jpeg','-jpegopt','quality=90',str(source),str(dest.with_suffix(''))],check=True,stdout=subprocess.DEVNULL)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(render,[p['page'] for l in lessons.values() for p in l['pages']]))
reviewed=LIB/'reviewed-textbook-exercises.json'
if reviewed.exists():
    for e in json.loads(reviewed.read_text()):
        items.append(e);lessons[e['group']]['question_ids'].append(e['id'])
data={'schema_version':'1.0','source_id':'beginner-upper-pdf','source_path':source.name,'scope':'beginner_upper','lessons':lessons,'exercises':items}
for path in (LIB/'textbook-exercises.json',DIST/'data/textbook-exercises.json'):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(f'{len(lessons)} lessons, {sum(len(l["pages"]) for l in lessons.values())} original pages, {len(items)-72} verified text/image questions')
