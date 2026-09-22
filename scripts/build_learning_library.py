#!/usr/bin/env python3
"""Build runtime library data from an explicit local JSON bundle (or original demo).
Never copy learner history, Anki snapshots, credentials or books into source control.
"""
from pathlib import Path
import argparse, copy, json
ROOT=Path(__file__).resolve().parents[1]

def dump(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def build(source, root=ROOT):
    data=json.loads(Path(source).read_text(encoding='utf8'))
    for key in ('lessons','vocabulary','grammar','exercises','sources'):
        if not isinstance(data.get(key),list):raise ValueError('Expected array: '+key)
    lessons=data['lessons']
    if not lessons or len({l['id'] for l in lessons})!=len(lessons):raise ValueError('Missing or duplicate lesson IDs')
    for l in lessons:
        if l['id']!=f"b{l['number']:02d}" or not 1<=l['number']<=48:raise ValueError('Expected b01–b48 lessons')
        for key in ('sections','vocabulary_ids','grammar','exercises'):
            if not isinstance(l.get(key),list):raise ValueError('Invalid lesson field: '+key)
    data=copy.deepcopy(data)
    # Imported material is never imported learning evidence.
    data['study']={'sessions_completed':0,'lessons_completed':0,'daily_word_ids':[],'last_session_date':None,'word_target':30}
    data['counts']={'vocabulary':len(data['vocabulary']),'audio':sum(bool(w.get('audio')) for w in data['vocabulary']),'lessons':len(lessons)}
    data.setdefault('built_on','local import')
    public=root/'website/dist/data';library=root/'study/library'
    dump(public/'library.json',data)
    for key in ('lessons','vocabulary','grammar','exercises'):
        dump(library/(key+'.json'),data[key])
    for l in lessons:dump(library/'lessons'/(l['id']+'.json'),l)
    defaults={'reading-library.json':{'books':[]},'vocabulary-workbook-reader.json':{'id':'vocab-workbook','chapters':[]},'ocr.json':{'pages':[]},'workbook.json':{'chapters':[]},'legacy-classrooms.json':[],'textbook-exercises.json':{'lessons':{},'exercises':[]}}
    for name,value in defaults.items():
        if not (public/name).exists():dump(public/name,value)
    if not (library/'textbook-exercises.json').exists():dump(library/'textbook-exercises.json',defaults['textbook-exercises.json'])
    for name,value in [('profile.json',{'schema_version':1,'timezone':'Asia/Hong_Kong','preferences':{'language':'zh-CN','japanese_readings':True},'daily_word_budget':30}),('state.json',{'textbook_progress':{'current_lesson':1,'lessons_completed':[]}})]:
        if not (root/'study'/name).exists():dump(root/'study'/name,value)
    print('Library ready; personal progress was not replaced.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'examples/library.demo.json')
    args=parser.parse_args();build(args.source)
