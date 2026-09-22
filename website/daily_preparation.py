"""Daily homepage guidance with source fingerprints and an offline-safe preparation CLI."""
from pathlib import Path
from datetime import datetime, timezone
import fcntl, hashlib, json, os, tempfile
from supplementary import day, participation
from study_workflow import lesson_progress
from classroom_memory import project_memory

def read(path, fallback):
    try:return json.loads(path.read_text())
    except (FileNotFoundError,ValueError):return fallback

def atomic(path,value):
    with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno());name=f.name
    os.replace(name,path)

class DailyPreparation:
    def __init__(self,root):
        self.root=Path(root);self.directory=self.root/'study/daily-preparation'

    def context(self,date=None):
        date=date or day()
        state=read(self.root/'study/state.json',{})
        sessions=[read(p,{}) for p in (self.root/'study/classrooms').glob('*.json')]
        learned=sorted([s for s in sessions if s.get('messages') and participation(s)],key=lambda s:max(m['created_at'] for m in participation(s)),reverse=True)
        latest=learned[0] if learned else None
        previous=next(iter(sorted([s for s in learned if s.get('supplement') and s['supplement']['learning_date']<date],key=lambda s:s['supplement']['created_at'],reverse=True)),None)
        review=previous['supplement']['exercises'][:5] if previous else [e for e in read(self.root/'study/library/exercises.json',[]) if e.get('group') in ('review','pending')]
        responses=[];journal=self.root/'study/practice/website-responses.jsonl'
        if journal.exists():
            for line in journal.read_text().splitlines():
                try:responses.append(json.loads(line))
                except ValueError:continue # A concurrent append can leave an incomplete final line.
        review_ids={e['id'] for e in review}
        answered={a['exercise_id'] for a in responses if a.get('phase')=='preclass' and a.get('answered_at') and day(a['answered_at'])==date and a.get('exercise_id') in review_ids}
        snapshot=read(self.root/'study/anki/website-sync/latest.json',{})
        stamp=snapshot.get('captured_at')
        anki={'snapshot_date':day(stamp) if stamp else None,'due_count':snapshot.get('due_count'),'reviewed_count':snapshot.get('reviewed_count')}
        last_stamp=max(m['created_at'] for m in participation(latest)) if latest else state.get('last_updated')
        data={'date':date,'timezone':'Asia/Hong_Kong','lesson_id':lesson_progress(self.root)['current_lesson'],
              'last_learning_date':day(last_stamp) if last_stamp else None,
              'latest_classroom':{k:latest.get(k) for k in ('id','status','summary','next_step','stage','observations')} if latest else None,
              'legacy_next_step':state.get('current_session',{}).get('next_action') or state.get('next_session',{}).get('focus') or state.get('textbook_progress',{}).get('next_action'),
              'memory':project_memory(sessions),
              'review_questions':[{k:e.get(k) for k in ('id','prompt','topic','target')} for e in review],
              'review_done':len(answered),'review_total':len(review),
              'recent_answers':responses[-20:],'anki_snapshot':anki,
              'profile':read(self.root/'study/profile.json',{})}
        words=read(self.root/'study/daily-words'/(date+'.json'),{})
        data['daily_words']={'date':words.get('date'),'lesson_id':words.get('lesson_id'),'items':[{k:w.get(k) for k in ('note_id','word','reading','category')} for w in words.get('items',[])]}
        progress=lesson_progress(self.root,sessions)
        data['current_lesson_state']=next(x for x in progress['lessons'] if x['lesson_id']==data['lesson_id'])
        fingerprint=hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        return {'source_fingerprint':fingerprint,'context':data}

    def get(self,trigger='page_open',draft=None,date=None):
        self.directory.mkdir(parents=True,exist_ok=True)
        # The web process and the scheduled task share this lock; neither imports Classroom.
        with (self.directory/'.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            source=self.context(date);ctx=source['context'];path=self.directory/(ctx['date']+'.json')
            existing=read(path,{})
            if draft is None and existing.get('source_fingerprint')==source['source_fingerprint']:
                return {k:v for k,v in existing.items() if k!='context'}
            if draft is not None:
                if not isinstance(draft,dict) or set(draft)!={'source_fingerprint','date','headline','guidance'}:raise ValueError('准备稿字段应为 source_fingerprint、date、headline、guidance。')
                if draft['source_fingerprint']!=source['source_fingerprint'] or draft['date']!=ctx['date']:raise ValueError('学习记录已经更新，请重新读取上下文后准备。')
                for k,limit in (('headline',80),('guidance',700)):
                    if not isinstance(draft[k],str) or not 0<len(draft[k].strip())<=limit:raise ValueError('准备稿文字长度无效。')
            lesson=int(ctx['lesson_id'][1:]);current=ctx['latest_classroom']
            next_step=(current.get('next_step') or current.get('summary')) if current else ctx['legacy_next_step']
            guidance=f"先完成 Anki 到期复习，再做课前回忆（今天已提交 {ctx['review_done']}/{ctx['review_total']} 题）。"
            if next_step:guidance+='接续安排：'+next_step
            else:guidance+=f'进入第 {lesson} 课，让教练先确认基础和本节目标。'
            result={**source,'schema_version':1,'date':ctx['date'],'lesson_id':ctx['lesson_id'],
                    'generated_at':datetime.now(timezone.utc).isoformat(),'trigger':trigger,
                    'mode':'coach_prepared' if draft else 'records_based',
                    'headline':draft['headline'] if draft else f'第 {lesson} 课：接着真实进度学',
                    'guidance':draft['guidance'] if draft else guidance,
                    'last_learning_date':ctx['last_learning_date'],
                    'source_session_id':current['id'] if current else None,
                    'focus_topics':list(dict.fromkeys(e.get('topic') or e['prompt'] for e in ctx['review_questions']))[:3],
                    'review_done':ctx['review_done'],'review_total':ctx['review_total']}
            # Daily plans are preparation, not attendance, assessment, or Anki mutations.
            atomic(path,result)
            return {k:v for k,v in result.items() if k!='context'}
