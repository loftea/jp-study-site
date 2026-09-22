"""Isolated classroom lifecycle, duplicate delivery, evidence and restart checks."""
from pathlib import Path
import sys, tempfile, time, uuid, threading, json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'website'))
from classroom import Classroom, ROOT, cli_reply, atomic_json
from check_supplementary import exercises, fake_tts

def wait(c,sid):
    until=time.monotonic()+10
    while c.get(sid)['job']['status']=='running':
        assert time.monotonic()<until,'worker timed out'
        time.sleep(.01)
    return c.get(sid)

def rid():return str(uuid.uuid4())
def output(reply='测试回复',observations=None):
    return {'reply':reply,'stage':'练习','summary':'测试总结；不代表掌握','next_step':'延迟回忆','completed_activities':[], 'observations':observations or []}

with tempfile.TemporaryDirectory(prefix='jp-classroom-test-') as temp:
    directory=Path(temp)/'sessions'; calls=[]; gate=threading.Event()
    def runner(s,t,ctx):
        calls.append(t);assert ctx['lesson']['id']=='b01'
        gate.wait(3)
        result=output(observations=[{'evidence_message_id':t['id'],'quote':t['text'],'topic':'测试','evaluation':'unknown','feedback':'测试'}])
        result['lesson_checks']=[{'area':'grammar','phase':'practice','evaluation':'independent_correct','evidence_message_id':t['id'],'quote':t['text']}] if t['kind']=='message' else []
        result['supplementary_exercises']=exercises(s) if t['kind']=='finish' and ctx['supplement_eligible'] else []
        return result,rid(),None
    c=Classroom(directory=directory,runner=runner,synthesizer=fake_tts)
    creation={'operation':'create','request_id':rid(),'lesson_id':'b01'}
    s=c.request(creation);sid=s['id']
    assert c.request(creation)['id']==sid
    assert c.get(sid)['job']['status']=='running'
    try:c.request({'operation':'message','session_id':sid,'request_id':rid(),'message':'busy'})
    except ValueError:pass
    else:raise AssertionError('overlapping turns accepted')
    gate.set();s=wait(c,sid);assert not s['observations'],'control messages counted as evidence'
    req={'operation':'message','session_id':sid,'request_id':rid(),'message':'飲んで'}
    c.request(req);s=wait(c,sid);c.request(req)
    assert len(calls)==2 and s['user_answer_count']==1
    assert s['observations'][0]['quote']=='飲んで'
    assert c.load(sid)['lesson_checks'][0]['quote']=='飲んで'
    assert len(c.load(sid)['lesson_checks'])==1
    reopened=Classroom(directory=directory,runner=runner,synthesizer=fake_tts)
    assert reopened.get(sid)['messages']==s['messages']
    reopened.request({'operation':'finish','session_id':sid,'request_id':rid()});s=wait(reopened,sid)
    assert s['status']=='ended' and s['ended_at']
    try:reopened.request({'operation':'message','session_id':sid,'request_id':rid(),'message':'late'})
    except ValueError:pass
    else:raise AssertionError('ended session accepted')
    try:c.get('../../profile')
    except ValueError:pass
    else:raise AssertionError('path traversal accepted')
    attempts=[]
    def failure(s,t,ctx):
        attempts.append(t)
        if len(attempts)==1:raise RuntimeError('test failure')
        return output(),rid(),None
    c=Classroom(directory=Path(temp)/'failures',runner=failure)
    s=c.request({'operation':'create','request_id':rid(),'lesson_id':'b01'});sid=s['id'];s=wait(c,sid)
    assert s['job']['status']=='error'
    c.request({'operation':'retry','request_id':rid(),'session_id':sid});s=wait(c,sid)
    assert s['job']['status']=='done' and len(s['messages'])==2
    raw=c.load(sid);raw['job']['status']='running';c.save(raw)
    restarted=Classroom(directory=c.directory,runner=failure)
    assert restarted.get(sid)['job']['status']=='error'
    assert restarted.load(sid)['cli_thread_id'] is None
print('PASS: durable messages, exact session routing, idempotency, busy/ended guards, retry, evidence validation, restart recovery; no learner records changed.')
