"""Isolated evidence, daily manifest, resume and recovery regressions."""
import copy,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'website'))
from study_workflow import StudyWorkflow,save,lesson_progress,validate_checks,AREAS
from backup_study import backup,verify
with tempfile.TemporaryDirectory(prefix='jp-workflow-check-') as t:
 root=Path(t);save(root/'study/state.json',{'textbook_progress':{'current_lesson':1}})
 w=StudyWorkflow(root);date='2025-02-22';stamp=date+'T12:00:00+08:00'
 notes={}
 for n in range(1,43):notes[str(n)]={'note_id':n,'vocabulary':{'word':'語'+str(n),'reading':'ご','meaning':'fixture','lesson_number':1 if n<41 else 2},'cards':[{'cardId':n,'queue':0,'type':0,'reps':0,'is_due':False,'reviewed_today':False}]}
 notes['40']['vocabulary']['word']='語1' # same word not double counted
 save(root/'website/dist/data/library.json',{'vocabulary':[{'note_id':41,'assessment':'needs_review'}]})
 snap={'connected':True,'captured_at':stamp,'notes':notes,'due_count':2}
 assert not w.manifest({'connected':False},'b01',date)['items']
 first=w.manifest(snap,'b01',date);assert len(first['items'])==30 and all(x['lesson_number']==1 or x['note_id']==41 for x in first['items']) and first['items'][0]['note_id']==41
 del notes['1'];notes['2']['cards'][0]['queue']=-1
 frozen=w.manifest(snap,'b01',date);assert [x['note_id'] for x in frozen['items']]==[x['note_id'] for x in first['items']]
 assert frozen['missing']==2 and next(x for x in frozen['items'] if x['note_id']==1)['binding_status']=='unavailable'
 off=w.manifest({**snap,'connected':False},'b01',date);assert off['items']==frozen['items'] and not off['fresh']
 assert not w.manifest(snap,'b01','2025-02-23')['items'],'old snapshot cannot select tomorrow cards'
 tomorrow=w.manifest({**snap,'captured_at':'2025-02-23T12:00:00+08:00'},'b01','2025-02-23');assert len(tomorrow['items'])==30
 plan={'review_exercises':[{'id':'q1'},{'id':'q2'}]}
 s={'id':'fixture','lesson_id':'b01','status':'active','messages':[],'updated_at':stamp,'lesson_checks':[]}
 save(root/'study/classrooms/fixture.json',s)
 tasks=w.get(snap,plan,date)['tasks'];assert tasks['steps'][2]['href']=='#classroom/fixture' and tasks['steps'][2]['status']=='in_progress'
 # Actual independent answers, quoted and replied to; same-day re-tests cannot complete a lesson.
 for phase,dt in [('practice',date),('retest',date),('retest','2025-02-23')]:
  for area in AREAS:
   mid=phase+dt+area;message={'id':mid,'role':'user','content':'fixture '+area,'created_at':dt+'T12:00:00+08:00'}
   s['messages'] += [message,{'id':'reply'+mid,'role':'assistant','content':'ok','in_reply_to':mid,'created_at':dt+'T12:01:00+08:00'}]
   c={'area':area,'phase':phase,'evaluation':'independent_correct','evidence_message_id':mid,'quote':message['content']}
   s['lesson_checks']+=validate_checks([c],s,dt+'T12:01:00+08:00')
  p=lesson_progress(root,[s]);assert p['lessons'][0]['status']==('completed' if dt=='2025-02-23' else 'retest')
 try:validate_checks([{**c,'quote':'invented'}],s,stamp)
 except ValueError:pass
 else:raise AssertionError('fabricated evidence accepted')
 s['lesson_checks'][-1]['evaluation']='needs_review';assert lesson_progress(root,[s])['completed_count']==0
 s['status']='ended';save(root/'study/classrooms/fixture.json',s)
 assert w.get(snap,plan,date)['tasks']['steps'][2]['status']=='done'
 journal=root/'study/practice/website-responses.jsonl';journal.parent.mkdir(parents=True);journal.write_text('\n'.join(json.dumps({'exercise_id':q,'phase':'preclass','answered_at':stamp}) for q in ['q1','q2'])+'\n')
 d=w.get({**snap,'due_count':0},plan,date);assert d['tasks']['next']['id']=='homework'
 assert d['progress']['completed_count']==0,'ending classroom claimed completion'
 b=backup(root);archive=root/b['file'];verify(archive,root/'restored')
 assert (root/'restored/study/classrooms/fixture.json').read_bytes()==(root/'study/classrooms/fixture.json').read_bytes()
 assert not any('auth' in n for n in verify(archive)['files'])
 try:verify(archive,root/'study')
 except ValueError:pass
 else:raise AssertionError('restore allowed overwrite')
print('PASS: daily rollover, offline guard, stable card IDs, removed/suspended cards, dedup, no premature lessons, evidence-based retest, resume, tasks, verified backup and safe restore.')
