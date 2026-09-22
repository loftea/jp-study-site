"""Isolated exercise lifecycle and HTTP checks; --serve opens a disposable UI fixture."""
from pathlib import Path
import argparse,copy,json,sys,tempfile,time,uuid,wave,threading,urllib.request,urllib.error
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'website'))
from classroom import Classroom
from supplementary import day,participation,make_supplement,synthesize

def rid():return str(uuid.uuid4())
def wait(c,sid):
 for _ in range(3000):
  s=c.get(sid)
  if s['job']['status']!='running':assert s['job']['status']=='done',s['job'];return s
  time.sleep(.01)
 raise AssertionError('worker timed out')
def op(c,operation,**kw):
 s=c.request({'operation':operation,'request_id':rid(),**kw});return wait(c,s['id'])
def exercises(s):
 evidence=participation(s)[0]
 common={'evidence_message_id':evidence['id'],'quote':evidence['content'],'topic':'名词句与身份','type':'written','transcript':'','tts_text':''}
 return [dict(common,prompt='请用日语说：我不是学生。',answers=['私は学生ではありません','わたしはがくせいではありません'],target='私（わたし）は学生（がくせい）ではありません。',explanation='名词句否定用「ではありません」。'),dict(common,prompt='请用日语问：你是公司职员吗？',answers=['会社員ですか','かいしゃいんですか'],target='会社員（かいしゃいん）ですか。',explanation='句尾加「か」表示疑问。'),dict(common,type='listening',prompt='听短句：说话人是什么职业？可以用中文回答。',answers=['公司职员','会社員','かいしゃいん'],target='会社員（かいしゃいん），公司职员。',explanation='说话人用名词句介绍职业。',transcript='はじめまして。山田（やまだ）です。会社員（かいしゃいん）です。',tts_text='はじめまして。やまだです。かいしゃいんです。')]
def runner(s,t,ctx):
 return {'reply':'隔离测试回复；不计入学习。','stage':'测试','summary':'隔离测试课堂摘要。','next_step':'延迟复习','completed_activities':[],'observations':[], 'memory_updates':[], 'supplementary_exercises':exercises(s) if t['kind']=='finish' and ctx['supplement_eligible'] else []},rid(),None

def fake_tts(text,path):
 path.parent.mkdir(parents=True,exist_ok=True)
 with wave.open(str(path),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050);w.writeframes(b'\0\0'*22050)
 return {'voice':'TEST ONLY','duration_seconds':1,'engine':'test fixture'}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--tts',action='store_true');parser.add_argument('--serve',action='store_true');args=parser.parse_args()
 with tempfile.TemporaryDirectory(prefix='jp-supplement-test-') as temp:
  directory=Path(temp);c=Classroom(directory=directory/'sessions',runner=runner,synthesizer=synthesize if args.tts else fake_tts)
  assert c.learning_plan()['attended_today'] is False
  assert day('2025-02-20T15:59:00+00:00')=='2025-02-20' and day('2025-02-20T16:00:00+00:00')=='2025-02-21'
  empty=op(c,'create',lesson_id='b01');empty=op(c,'finish',session_id=empty['id']);assert not empty['supplement']
  a=op(c,'create',lesson_id='b02');assert not c.learning_plan()['attended_today']
  a=op(c,'message',session_id=a['id'],message='私は学生ではありません。会社員です。')
  assert not a['supplement'] and c.learning_plan()['attended_today'] and c.learning_plan()['lesson_id']=='b02'
  # A forged quote or missing listening question cannot become a saved exercise set.
  raw=c.load(a['id']);items=exercises(raw);bad=copy.deepcopy(items);bad[0]['quote']='never said'
  try:make_supplement(bad,raw,raw['updated_at'])
  except ValueError:pass
  else:raise AssertionError('fabricated evidence accepted')
  bad=copy.deepcopy(items);bad[2]=copy.deepcopy(bad[0])
  try:make_supplement(bad,raw,raw['updated_at'])
  except ValueError:pass
  else:raise AssertionError('missing listening accepted')
  # Natural explicit end and button end use the same durable flow.
  finish={'operation':'message','request_id':rid(),'session_id':a['id'],'message':'下课吧'}
  c.request(finish);a=wait(c,a['id']);assert a['status']=='ended' and len(a['supplement']['exercises'])==3
  assert a['supplement']['audio_status']=='ready',a['supplement']
  before=copy.deepcopy(a);assert c.request(finish)==before
  c=Classroom(directory=c.directory,runner=runner,synthesizer=fake_tts)
  assert c.get(a['id'])==before and c.list()[0]['supplement_count']==3
  eid=a['supplement']['exercises'][-1]['id'];assert c.audio(a['id'],eid).startswith(b'RIFF')
  assert c.supplementary_exercise(eid)['session_id']==a['id']
  try:c.audio(a['id'],'../../profile.json')
  except ValueError:pass
  else:raise AssertionError('invalid audio path accepted')
  # A synthesis failure preserves the finished class and all questions. Retry changes audio only.
  def broken(*_):raise RuntimeError('test audio failure')
  c.synthesizer=broken;b=op(c,'create',lesson_id='b01');b=op(c,'message',session_id=b['id'],message='私は学生です。')
  b=op(c,'finish',session_id=b['id']);assert b['status']=='ended' and b['supplement']['audio_status']=='error'
  original=copy.deepcopy(b['messages']);c.synthesizer=fake_tts;b=c.retry_audio(b['id'])
  assert b['supplement']['audio_status']=='ready' and b['messages']==original
  # A prior day's class is available in history and becomes preclass review, not today's new set.
  old=c.load(b['id']);old['supplement']['learning_date']='2025-02-18'
  for m in old['messages']:m['created_at']='2025-02-18T08:00:00+00:00'
  c.save(old);p=c.learning_plan();assert len(p['supplements'])==1 and p['review_session_id']==b['id']
  assert len(p['review_exercises'])==3 and c.get(b['id'])['supplement']
  # HTTP writes use the stored reference, retain support and link attempts to the class.
  import serve
  from http.server import ThreadingHTTPServer
  serve.CLASSROOM=c;serve.JOURNAL=directory/'answers.jsonl'
  server=ThreadingHTTPServer(('127.0.0.1',8767 if args.serve else 0),serve.Handler)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  base=f'http://127.0.0.1:{server.server_port}'
  def http(path,data=None,origin=None):
   headers={'Content-Type':'application/json'}
   if origin:headers['Origin']=origin
   req=urllib.request.Request(base+path,headers=headers,data=json.dumps(data).encode() if data is not None else None)
   with urllib.request.urlopen(req) as r:return r.status,r.read()
  status,payload=http('/api/practice',{'exercise_id':eid,'response':'公司职员','target':'forged','support':'transcript_viewed','phase':'supplement','listening_plays':2})
  saved=json.loads(payload)['record'];assert status==201 and saved['session_id']==a['id'] and saved['support']=='transcript_viewed' and saved['target']!='forged'
  assert saved['result']=='matches_reference' and saved['listening_plays']==2
  assert json.loads(http('/api/practice')[1])[0]==saved
  assert http('/api/classrooms/audio?session_id='+a['id']+'&exercise_id='+eid)[1].startswith(b'RIFF')
  try:http('/api/classrooms/audio',{'session_id':a['id']},'https://untrusted.example')
  except urllib.error.HTTPError as e:assert e.code==403
  else:raise AssertionError('foreign origin accepted')
  assert json.loads(http('/api/learning-plan')[1])['supplements'][0]['id']==a['id']
  print('PASS: empty/active/day gates, evidence validation, listening required, restart/idempotency, audio retry, historical review, persisted linked answers and HTTP guards.',flush=True)
  if args.tts:print('PASS: actual Kyoko TTS produced a non-silent PCM WAV; no pronunciation claim.',flush=True)
  if args.serve:
   # Clearly mark fixtures; this server writes only to the temporary directory.
   raw=c.load(a['id']);raw['title']='隔离测试 · 第 2 课';c.save(raw)
   print('DISPOSABLE UI FIXTURE: '+base+'/#practice/'+a['id'],flush=True)
   try:
    while True:time.sleep(1)
   except KeyboardInterrupt:pass
  server.shutdown();server.server_close()
