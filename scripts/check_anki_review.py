"""Exercise native bridge invariants with a fake scheduler; never grade real cards."""
import importlib.util,sys,types,copy
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.modules['aqt']=types.SimpleNamespace(gui_hooks=types.SimpleNamespace(profile_did_open=[]))
spec=importlib.util.spec_from_file_location('test_bridge',root/'website/anki_addon/__init__.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class DB:
    def __init__(self):self.logs={}
    def scalar(self,sql,arg):
        if 'max(id)' in sql:return max((i for i,(cid,ease) in self.logs.items() if cid==arg),default=0)
        return self.logs[arg][1]
class Fake:
    def __init__(self):
        self.db=DB();self.c=types.SimpleNamespace(id=1,reps=0,mod=1);self.r=types.SimpleNamespace(card=self.c,state='question');self.w=types.SimpleNamespace(state='review');self.calls=0;self.mode='success';self.deck='JP::test';self.active=True
    def collection(self):return self
    def reviewer(self):return self.r
    def window(self):return self.w
    def guiReviewActive(self):return self.active
    def guiCurrentCard(self):return dict(cardId=self.c.id,deckName=self.deck,template='Card',question='QUESTION',answer='SECRET',css='',buttons=[1,2,3,4],nextReviews=['1m','6m','1d','3d'])
    def guiShowAnswer(self):self.r.state='answer';return True
    def guiDeckReview(self,name):self.active=True;self.deck=name;return True
    def guiAnswerCard(self,ease):
        self.calls+=1
        if self.mode=='reject':return False
        if self.mode=='raise':raise RuntimeError('ambiguous')
        if self.mode=='async':return True
        self.complete(ease);return True
    def complete(self,ease):self.db.logs[len(self.db.logs)+1]=(self.c.id,ease);self.c.reps+=1;self.r.state='question'
def revealed(fake,bridge):
    q=bridge.handle();assert q['html']=='QUESTION' and not q['buttons']
    return bridge.handle('reveal',q['token'],q['card_id'])
def grade(bridge,a,rid='request-1'):return bridge.handle('grade',a['token'],a['card_id'],3,rid)
f=Fake();b=m.ReviewBridge(f);a=revealed(f,b)
r=grade(b,a);assert r['receipt']['status']=='saved' and f.calls==1
assert grade(b,a)['receipt']['status']=='saved' and f.calls==1
try:grade(b,a,'request-2');raise AssertionError('accepted stale token')
except ValueError:pass
# Same card reappearing, and desktop advances, must invalidate stale website token.
a=revealed(f,b);f.complete(4)
try:grade(b,a,'request-3');raise AssertionError('accepted desktop-stale token')
except ValueError:pass
f=Fake();f.mode='async';b=m.ReviewBridge(f);a=revealed(f,b);r=grade(b,a);assert r['current']['state']=='saving'
grade(b,a);assert f.calls==1
f.complete(3);assert b.handle(request_id='request-1')['receipt']['status']=='saved'
f=Fake();f.mode='reject';b=m.ReviewBridge(f);a=revealed(f,b);r=grade(b,a);assert r['receipt']['status']=='rejected' and r['current']['token'] and not b.pending
f=Fake();f.mode='raise';b=m.ReviewBridge(f);a=revealed(f,b)
try:grade(b,a)
except RuntimeError:pass
assert b.handle()['state']=='saving';grade(b,a);assert f.calls==1
f.complete(3);assert b.handle(request_id='request-1')['receipt']['status']=='saved'
f.deck='Other';assert b.handle()['state']=='other_deck'
# Native media markers resolve to actual AV filenames, preserving side/index.
f=Fake();b=m.ReviewBridge(f)
f.c.question_av_tags=lambda:[types.SimpleNamespace(filename='q.mp3')]
f.c.answer_av_tags=lambda:[types.SimpleNamespace(filename='a.mp3')]
base=f.guiCurrentCard
f.guiCurrentCard=lambda:{**base(),'question':'[anki:play:q:0]','answer':'[anki:play:a:0]'}
q=b.handle();assert 'q.mp3' in q['html'] and 'a.mp3' not in q['html']
a=b.handle('reveal',q['token'],q['card_id']);assert 'a.mp3' in a['html']
sys.path.insert(0,str(root/'website'))
from reviewer import Reviewer
payload={'state':'answer','token':'test','html':'<script>SECRETJS</script><ruby>本<rt>ほん</rt></ruby>[sound:test.mp3]<img src="https://evil/img" onerror="alert(1)">','css':'.card{color:black}'}
r=Reviewer(lambda **kw:copy.deepcopy(payload));result=r.request({'operation':'status'});doc=result['document']
assert 'SECRETJS' not in doc and 'onerror' not in doc and 'https://evil' not in doc and '<rt>ほん</rt>' in doc and '<audio controls' in doc
assert r.media=={'test':{'test.mp3'}}
try:r.media_file('wrong','test.mp3');raise AssertionError('invalid media accepted')
except ValueError:pass
print('PASS: real-scheduler delegation, hidden answers, stale-card rejection, idempotency, async completion, rejection and uncertain retry protection, HTML/media isolation. No real cards graded.')
# Exercise HTTP grade validation with an isolated fake Anki instance.
import threading,json,urllib.request,urllib.error
from http.server import ThreadingHTTPServer
import serve
f=Fake();b=m.ReviewBridge(f);serve.REVIEWER=Reviewer(lambda **kw:b.handle(**kw))
server=ThreadingHTTPServer(('127.0.0.1',0),serve.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
def post(data,origin=None):
    headers={'Content-Type':'application/json'}
    if origin:headers['Origin']=origin
    req=urllib.request.Request('http://127.0.0.1:'+str(server.server_port)+'/api/anki/review',data=json.dumps(data).encode(),headers=headers)
    try:
        with urllib.request.urlopen(req) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
try:
    code,q=post({'operation':'status'});assert code==200 and 'SECRET' not in q['document']
    assert post({'operation':'grade'},'https://external.example')[0]==403
    assert post({'operation':'grade','token':'stale','card_id':1,'rating':3,'request_id':'http-fake'})[0]==409
    for n in (1,2,3,4):
        code,q=post({'operation':'status'})
        code,a=post({'operation':'reveal','token':q['token'],'card_id':q['card_id']});assert code==200 and 'SECRET' in a['document']
        data={'operation':'grade','token':a['token'],'card_id':a['card_id'],'rating':n,'request_id':'http-fake-'+str(n)}
        code,r=post(data);assert code==200 and r['receipt']['status']=='saved'
        post(data);assert f.calls==n
    assert [e for cid,e in f.db.logs.values()]==[1,2,3,4]
finally:server.shutdown();server.server_close()
print('PASS: isolated HTTP question/reveal/all four native ratings, duplicate requests and cross-origin rejection.')
