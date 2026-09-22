"""Memory survives classrooms/restarts; replacements and forgetting retain provenance."""
import sys,tempfile,uuid,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'website'))
from classroom import Classroom
from classroom_memory import validate_updates

def rid():return str(uuid.uuid4())
def wait(c,sid):
 for _ in range(1000):
  s=c.get(sid)
  if s['job']['status']!='running':assert s['job']['status']=='done',s;return s
  time.sleep(.01)
 raise AssertionError('timeout')
def op(c,operation,**kw):
 s=c.request({'operation':operation,'request_id':rid(),**kw});return wait(c,s['id'])
contexts=[]
def runner(s,t,ctx):
 contexts.append(ctx)
 updates=[]
 if t['kind']=='message':
  updates=[{'operation':'forget' if '忘记' in t['text'] else 'upsert','kind':'preference','key':'例句数量','content':t['text'], 'evidence_message_id':t['id'],'quote':t['text']}]
 return {'reply':'测试回复','stage':'练习','summary':'测试总结','next_step':'测试','completed_activities':[],'observations':[],'memory_updates':updates},rid(),None
with tempfile.TemporaryDirectory(prefix='jp-memory-test-') as temp:
 c=Classroom(directory=Path(temp)/'sessions',runner=runner)
 a=op(c,'create',lesson_id='b01');assert not c.memory()['items']
 a=op(c,'message',session_id=a['id'],message='以后每次给我三个例句。')
 assert len(a['memory_updates'])==1 and c.memory()['event_count']==1
 c=Classroom(directory=c.directory,runner=runner)
 b=op(c,'create',lesson_id='b02')
 assert contexts[-1]['long_term_memory']['items'][0]['content']=='以后每次给我三个例句。'
 b=op(c,'message',session_id=b['id'],message='改为两个例句。')
 memory=c.memory();assert len(memory['items'])==1 and memory['event_count']==2
 assert memory['items'][0]['content']=='改为两个例句。'
 b=op(c,'message',session_id=b['id'],message='忘记例句数量这个偏好。')
 assert c.memory()['items']==[] and c.memory()['event_count']==3
 c=Classroom(directory=c.directory,runner=runner)
 op(c,'create',lesson_id='b01');assert contexts[-1]['long_term_memory']['items']==[]
 raw=c.load(a['id']);turn={'id':rid()}
 candidate={'operation':'upsert','kind':'preference','key':'虚构','content':'应拒绝','evidence_message_id':raw['messages'][0]['id'],'quote':raw['messages'][0]['content']}
 assert not validate_updates([candidate],raw,turn,'2025-02-20'),'control evidence allowed'
 candidate.update(evidence_message_id=raw['messages'][2]['id'],quote='没有说过')
 assert not validate_updates([candidate],raw,turn,'2025-02-20'),'invented quote allowed'
print('PASS: cross-classroom memory, restart persistence, same-key correction, explicit forgetting, source linkage, control/fabricated evidence rejection; isolated data only.')
