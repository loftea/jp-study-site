"""Daily preparation freshness checks, using only disposable learner fixtures."""
import copy,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'website'))
from daily_preparation import DailyPreparation

def write(root,name,data):
 p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,ensure_ascii=False))
with tempfile.TemporaryDirectory(prefix='jp-daily-test-') as temporary:
 root=Path(temporary)
 write(root,'study/state.json',{'last_updated':'2025-02-14T12:00:00+08:00','textbook_progress':{'current_lesson':1},'current_session':{'next_action':'继续未完成的名词句。'}})
 write(root,'study/profile.json',{'timezone':'Asia/Hong_Kong'})
 write(root,'study/library/exercises.json',[{'id':'test-1','group':'review','prompt':'写出日语否定句。','target':'参考答案'}])
 write(root,'study/anki/website-sync/latest.json',{'captured_at':'2025-02-20T10:00:00+08:00','due_count':8,'reviewed_count':0})
 preparation=DailyPreparation(root);date='2025-02-20'
 first=preparation.get(date=date);assert first['last_learning_date']=='2025-02-14' and first['date']==date
 draft={k:first[k] for k in ('date','source_fingerprint')};draft.update(headline='本日恢复名词句',guidance='按记录复习，再继续当前课。')
 coach=preparation.get('scheduled',draft,date);assert coach['mode']=='coach_prepared'
 assert preparation.get(date=date)==coach,'unchanged visits rewrote the plan'
 # Poll timestamps alone must not discard the coach's draft.
 write(root,'study/anki/website-sync/latest.json',{'captured_at':'2025-02-20T11:00:00+08:00','due_count':8,'reviewed_count':0})
 assert preparation.get(date=date)==coach
 tomorrow=preparation.get(date='2025-02-21');assert tomorrow['mode']=='records_based' and tomorrow['source_fingerprint']!=coach['source_fingerprint']
 try:preparation.get('scheduled',draft,'2025-02-21')
 except ValueError:pass
 else:raise AssertionError('yesterday draft accepted as current')
 journal=root/'study/practice/website-responses.jsonl';journal.parent.mkdir(parents=True,exist_ok=True)
 journal.write_text(json.dumps({'exercise_id':'test-1','phase':'preclass','answered_at':'2025-02-20T12:00:00+08:00','response':'testing','result':'needs_teacher_review'})+'\n')
 updated=preparation.get(date=date);assert updated['review_done']==1 and updated['mode']=='records_based'
 try:preparation.get('scheduled',draft,date)
 except ValueError:pass
 else:raise AssertionError('stale evidence overwrote the current plan')
 # Opening a new lesson alone is not progression; a completed real exchange is.
 session={'id':'fixture','lesson_id':'b02','status':'active','messages':[{'id':'start','role':'control','created_at':'2025-02-20T13:00:00+08:00'}]}
 write(root,'study/classrooms/fixture.json',session);assert preparation.get(date=date)['lesson_id']=='b01'
 session['messages'] += [{'id':'learner','role':'user','content':'test','created_at':'2025-02-20T13:01:00+08:00'},{'id':'coach','role':'assistant','in_reply_to':'learner','content':'test','created_at':'2025-02-20T13:02:00+08:00'}]
 session['next_step']='开始第2课下一小节。';write(root,'study/classrooms/fixture.json',session)
 latest=preparation.get(date=date);assert latest['lesson_id']=='b02' and latest['source_session_id']=='fixture' and latest['last_learning_date']==date
 assert json.loads((root/'study/classrooms/fixture.json').read_text())==session
 assert len(journal.read_text().splitlines())==1
print('PASS: daily rollover, unchanged cache, timestamp-only refresh, stale draft rejection, new answer/class invalidation, no invented attendance or learner mutations.')
