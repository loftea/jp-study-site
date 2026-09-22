"""Evidence-derived lesson progress, stable daily word manifests and resumable tasks.
No imports of Classroom and no writes to Anki or original learning evidence.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, os, tempfile, threading, unicodedata
from supplementary import day, participation

AREAS = ('vocabulary', 'grammar', 'reading', 'listening', 'application')
AREA_NAMES = dict(zip(AREAS, ('词汇', '句型', '阅读', '听力', '运用')))

def read(path, default):
    try: return json.loads(Path(path).read_text())
    except (OSError, ValueError): return default

def save(path, data):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False, encoding='utf8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno()); name=f.name
    os.replace(name, path)

def sessions_at(root):
    return [s for p in (Path(root)/'study/classrooms').glob('*.json') if (s:=read(p,{})).get('id')]

def journal_at(root):
    path=Path(root)/'study/practice/website-responses.jsonl'; rows=[]
    if path.exists():
        for line in path.read_text().splitlines():
            try: rows.append(json.loads(line))
            except ValueError: pass
    return rows

def validate_checks(checks, session, stamp):
    if not isinstance(checks,list) or len(checks)>20: raise ValueError('课次证据格式无效')
    evidence={m['id']:m for m in session['messages'] if m['role']=='user' and m.get('kind')!='finish'}
    result=[]
    for c in checks:
        if not isinstance(c,dict) or c.get('area') not in AREAS or c.get('phase') not in ('practice','retest'): raise ValueError('课次证据范围无效')
        if c.get('evaluation') not in ('independent_correct','assisted_correct','self_corrected','needs_review','unknown'): raise ValueError('课次证据判断无效')
        m=evidence.get(c.get('evidence_message_id')); quote=c.get('quote')
        if not m or not isinstance(quote,str) or not quote.strip() or quote not in m['content']: raise ValueError('课次证据未引用真实作答')
        result.append({**c,'recorded_at':stamp,'answered_at':m['created_at'],'source':'teacher_assessed'})
    return result

def lesson_progress(root, sessions=None):
    root=Path(root); sessions=sessions if sessions is not None else sessions_at(root)
    state=read(root/'study/state.json',{}); current='b%02d'%state.get('textbook_progress',{}).get('current_lesson',1)
    result=[]
    for n in range(1,49):
        lid=f'b{n:02d}'; ss=[s for s in sessions if s.get('lesson_id')==lid]; checks=[]
        for s in ss:
            users={m['id']:m for m in participation(s)}
            for c in s.get('lesson_checks',[]):
                m=users.get(c.get('evidence_message_id'))
                if c.get('area') in AREAS and m and c.get('quote') and c['quote'] in m['content']:
                    checks.append({**c,'session_id':s['id'],'answered_at':m['created_at']})
        checks.sort(key=lambda c:(c['answered_at'],c.get('recorded_at','')))
        covered={c['area'] for c in checks if c['phase']=='practice' and c['evaluation']!='unknown'}
        passed=set()
        for area in AREAS:
            candidates=[c for c in checks if c['area']==area]
            if not candidates:continue
            last=candidates[-1]
            earlier=any(c['phase']=='practice' and day(c['answered_at'])<day(last['answered_at']) for c in candidates)
            if earlier and last['phase']=='retest' and last['evaluation']=='independent_correct':passed.add(area)
        status='completed' if len(passed)==len(AREAS) else 'retest' if len(covered)==len(AREAS) else 'learning' if any(participation(s) for s in ss) or lid==current else 'not_started'
        # Earlier explicit completion records remain traceable; no new completion is inferred from a session ending.
        if n in state.get('textbook_progress',{}).get('lessons_completed',[]) and not checks:status='completed'
        latest=max(ss,key=lambda s:s.get('updated_at',''),default={})
        result.append({'lesson_id':lid,'number':n,'status':status,'covered':sorted(covered),'retested':sorted(passed),
                       'pending_areas':[AREA_NAMES[a] for a in AREAS if a not in passed], 'evidence':checks,
                       'source':'classroom_evidence' if checks else 'legacy_state' if lid==current or status=='completed' else 'none',
                       'next_step':latest.get('next_step','') or ((state.get('current_session',{}).get('next_action') or state.get('textbook_progress',{}).get('next_action') or '') if lid==current else ''),'session_id':latest.get('id')})
    active=sorted([s for s in sessions if s.get('status')=='active'],key=lambda s:s.get('updated_at',''),reverse=True)
    learned=sorted([s for s in sessions if participation(s)],key=lambda s:max(m['created_at'] for m in participation(s)),reverse=True)
    current=(learned or [{'lesson_id':current}])[0]['lesson_id']
    if not active and next((r['status'] for r in result if r['lesson_id']==current),None)=='completed':
        current=next((r['lesson_id'] for r in result if r['number']>=int(current[1:]) and r['status']!='completed'),current)
    return {'current_lesson':current,'lessons':result,'completed_count':sum(r['status']=='completed' for r in result)}

class StudyWorkflow:
    def __init__(self,root): self.root=Path(root); self.lock=threading.RLock()

    def manifest(self, snapshot, lesson_id, date=None):
        date=date or day(); root=self.root; path=root/'study/daily-words'/f'{date}.json'
        with self.lock:
            prior=read(path,None); captured=snapshot.get('captured_at')
            fresh=bool(snapshot.get('connected') and captured and day(captured)==date)
            notes=snapshot.get('notes',{}); library=read(root/'website/dist/data/library.json',{})
            words={str(w.get('note_id')):w for w in library.get('vocabulary',[])}
            observations=sorted([o for s in sessions_at(root) for o in s.get('observations',[])],key=lambda o:o.get('recorded_at',''))
            def item(n):
                v=n.get('vocabulary',{}); cards=[c for c in n['cards'] if c.get('queue',-1)>=0]
                w=words.get(str(n['note_id']),{}); matches=[o for o in observations if v.get('word') and v['word'] in o.get('quote','')]
                weak=(matches[-1].get('evaluation')!='independent_correct') if matches else w.get('assessment')=='needs_review'
                category='consolidation' if weak else 'recovery' if any((c.get('reps') or 0)>0 or c.get('type')!=0 for c in cards) else 'new'
                return {'note_id':n['note_id'],'card_ids':[c['cardId'] for c in cards],'word':v['word'],'reading':v.get('reading',''),
                        'meaning':v.get('meaning',''),'lesson_number':v['lesson_number'],'category':category,
                        'reason':'历史作答提示需巩固' if weak else '已有 Anki 学习记录，安排恢复' if category=='recovery' else '卡片尚未学习，暂列新学；不推断你从未学过',
                        'is_due':any(c.get('is_due') for c in cards),'reviewed_today':any(c.get('reviewed_today') for c in cards),
                        'binding_status':'verified','verified_at':captured}
            if prior is None and not fresh:
                return {'date':date,'lesson_id':lesson_id,'items':[],'target':30,'status':'awaiting_anki','missing':30,'fresh':False,'captured_at':captured,'notice':'连接 Anki 后生成今天词单；不使用过期快照选卡。'}
            if prior is None or (not prior.get('items') and fresh):
                candidates=[]
                for n in notes.values():
                    v=n.get('vocabulary',{})
                    if not v.get('word') or not v.get('lesson_number'):continue
                    known=words.get(str(n['note_id']),{}).get('assessment') not in (None,'not_assessed') or any(v['word'] in o.get('quote','') for o in observations)
                    if v['lesson_number']>int(lesson_id[1:]) and not known:continue
                    if not any(c.get('queue',-1)>=0 for c in n.get('cards',[])):continue
                    candidates.append(item(n))
                candidates.sort(key=lambda w:(w['reviewed_today'],0 if w['category']=='consolidation' else 1 if w['is_due'] else 2 if w['category']=='new' else 3,w['lesson_number']!=int(lesson_id[1:]),w['note_id']))
                selected=[];seen=set()
                for w in candidates:
                    key=unicodedata.normalize('NFKC',w['word']).replace(' ','')
                    if key in seen:continue
                    selected.append(w);seen.add(key)
                    if len(selected)==30:break
                prior={'schema_version':1,'date':date,'lesson_id':lesson_id,'target':30,'created_at':datetime.now(timezone.utc).isoformat(),'items':selected}
            elif fresh:
                # Keep today's chosen note IDs stable. Removed/suspended cards are explicit, never silently replaced.
                for w in prior['items']:
                    n=notes.get(str(w['note_id']))
                    if not n or not n.get('vocabulary') or not any(c.get('queue',-1)>=0 for c in n.get('cards',[])):
                        w.update(binding_status='unavailable',reviewed_today=False);continue
                    updated=item(n);updated['category']=w['category'];updated['reason']=w['reason'];w.update(updated)
            available=sum(w['binding_status']=='verified' for w in prior['items'])
            prior.update(status='ready' if available==30 else 'partial',missing=30-available,verified_at=captured if fresh else prior.get('verified_at'))
            if fresh:save(path,prior)
            return {**prior,'fresh':fresh,'captured_at':prior.get('verified_at'),'notice':'按不同词去重；同日保持已选词；当前课及以前课次之外，只纳入已有作答证据的词。' if fresh else 'Anki 离线或快照已过期；显示已保存词单，卡片状态待重连核对。'}

    def get(self, snapshot, plan, date=None):
        with self.lock:
            date=date or day(); sessions=sessions_at(self.root); rows=journal_at(self.root)
            progress=lesson_progress(self.root,sessions); lid=progress['current_lesson']; manifest=self.manifest(snapshot,lid,date)
            progress['computed_at']=datetime.now(timezone.utc).isoformat()
            save(self.root/'study/progress/lessons.json',progress)
            fresh=bool(snapshot.get('connected') and snapshot.get('captured_at') and day(snapshot['captured_at'])==date)
            today=[r for r in rows if r.get('answered_at') and day(r['answered_at'])==date]
            active=sorted([s for s in sessions if s.get('status')=='active'],key=lambda s:s.get('updated_at',''),reverse=True)
            ended=sorted([s for s in sessions if s.get('status')=='ended' and participation(s,date)],key=lambda s:s.get('ended_at',''))
            review_ids={e['id'] for e in plan.get('review_exercises',[])}
            done_review={r['exercise_id'] for r in today if r.get('phase')=='preclass'} & review_ids
            packs=[s for s in sessions if s.get('supplement',{}).get('learning_date')==date]
            supplement_ids={e['id'] for s in packs for e in s['supplement']['exercises']}
            done_sup={r['exercise_id'] for r in today if r.get('phase')=='supplement'} & supplement_ids
            homework_lid=ended[-1]['lesson_id'] if ended else lid
            textbook=read(self.root/'study/library/textbook-exercises.json',{}).get('exercises',[])
            textbook_ids={e['id'] for e in textbook if e.get('group')==homework_lid and e.get('source_type')=='textbook_scan_exercise'}
            done_book={r['exercise_id'] for r in today} & textbook_ids
            class_href='#classroom/'+active[0]['id'] if active else '#classroom'
            if active:class_state='in_progress'
            elif ended:class_state='done'
            else:class_state='pending'
            homework_done=bool(ended and supplement_ids and done_sup==supplement_ids and done_book==textbook_ids)
            steps=[
                {'id':'anki','title':'Anki 到期复习','status':'done' if fresh and snapshot.get('due_count')==0 else 'pending' if fresh else 'unknown','detail':f"到期 {snapshot.get('due_count','—')} 张；以 Anki 当前队列为准" if fresh else '等待 Anki 实时连接','href':'#review'},
                {'id':'preclass','title':'课前复习','status':'done' if review_ids and done_review==review_ids else 'in_progress' if done_review else 'pending','detail':f'今天已提交 {len(done_review)} / {len(review_ids)} 题','href':'#practice/review'},
                {'id':'classroom','title':'文字课堂','status':class_state,'detail':active[0].get('stage') or '继续未结束的课堂' if active else '今天已有真实互动并结束课堂' if ended else '尚未完成今天课堂','href':class_href},
                {'id':'homework','title':'课后练习','status':'done' if homework_done else 'in_progress' if done_sup or done_book else 'pending' if ended else 'locked','detail':f'补充题 {len(done_sup)}/{len(supplement_ids)} · 教材原页 {len(done_book)}/{len(textbook_ids)} 已提交' if ended else '结束课堂后生成补充练习','href':'#practice/'+packs[-1]['id'] if packs and done_sup!=supplement_ids else '#textbook/'+homework_lid if ended and done_book!=textbook_ids else '#practice'}]
            next_step=next((s for s in steps if s['status']!='done'),None)
            task={'date':date,'lesson_id':lid,'steps':steps,'next':next_step,'all_done':next_step is None,'updated_at':progress['computed_at']}
            save(self.root/'study/daily-tasks'/f'{date}.json',task)
            return {'date':date,'words':manifest,'tasks':task,'progress':progress}
