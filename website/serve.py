#!/usr/bin/env python3
"""Loopback-only Japanese study site. Native Anki ratings require explicit user actions."""
from config import ANKI_URL, require_anki
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, threading, urllib.request, urllib.parse, re, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from anki_sync import MIRROR
from anki_calendar import CALENDAR
from reviewer import REVIEWER
from classroom import CLASSROOM, cli_path
from daily_preparation import DailyPreparation
from study_workflow import StudyWorkflow, lesson_progress
import time

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'website/dist'
JOURNAL=ROOT/'study/practice/website-responses.jsonl'
LOCK=threading.Lock()
PREPARATION=DailyPreparation(ROOT)
WORKFLOW=StudyWorkflow(ROOT)
STARTED=time.time()

def anki(action, **params):
    require_anki()
    assert action in {'findCards','cardsInfo'}
    request=urllib.request.Request(ANKI_URL,data=json.dumps({'action':action,'version':6,'params':params}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=8) as response:
        data=json.load(response)
    if data.get('error'):raise RuntimeError(data['error'])
    return data['result']

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(PUBLIC),**kwargs)
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','same-origin')
        self.send_header('Cache-Control','no-cache')
        super().end_headers()
    def json(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def valid_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
    def do_GET(self):
        if not self.valid_host():return self.json(403,{'error':'Host not allowed'})
        path=urllib.parse.urlsplit(self.path).path
        if path=='/api/health':return self.json(200,{'service':'jp-study-local','version':3,'anki_auto_sync':True,'anki_review':True})
        if path=='/api/lesson-progress':return self.json(200,lesson_progress(ROOT))
        if path=='/api/study-workflow':
            try:return self.json(200,WORKFLOW.get(MIRROR.get(),CLASSROOM.learning_plan()))
            except (OSError,ValueError,KeyError):return self.json(503,{'error':'学习任务暂时无法更新，已有记录保留。'})
        if path=='/api/system/status':
            from study_workflow import read
            return self.json(200,{'running':True,'uptime_seconds':int(time.time()-STARTED),'managed':__import__('os').environ.get('JP_SITE_MANAGED')=='1','backup':read(ROOT/'study/system/backup-status.json',{})})
        if path=='/api/classrooms/memory':return self.json(200,CLASSROOM.memory())
        if path=='/api/learning-plan':return self.json(200,CLASSROOM.learning_plan())
        if path=='/api/daily-preparation':
            try:return self.json(200,PREPARATION.get())
            except (OSError,ValueError):return self.json(503,{'error':'今日安排暂未更新，请稍后重试。'})
        if path=='/api/classrooms/audio':
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                payload=CLASSROOM.audio(query.get('session_id',[''])[0],query.get('exercise_id',[''])[0])
                self.send_response(200);self.send_header('Content-Type','audio/wav');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            except (ValueError, OSError):return self.json(404,{'error':'音频尚未准备好。'})
            return
        if path=='/api/classrooms':
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                if query.get('id'):return self.json(200,CLASSROOM.get(query['id'][0]))
                return self.json(200,{'sessions':CLASSROOM.list(),'cli_available':bool(cli_path())})
            except ValueError as e:return self.json(404,{'error':str(e)})
        if path=='/api/practice':
            with LOCK:
                rows=[json.loads(line) for line in JOURNAL.read_text().splitlines() if line.strip()] if JOURNAL.exists() else []
            return self.json(200,rows)
        if path=='/api/anki/calendar':return self.json(200,CALENDAR.get())
        if path=='/api/anki/sync':
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            return self.json(200,MIRROR.get(force=query.get('force')==['1']))
        if path=='/api/anki/review/media':
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                name=query.get('name',[''])[0];payload=REVIEWER.media_file(query.get('token',[''])[0],name)
                import mimetypes
                self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            except Exception:return self.json(404,{'error':'Media unavailable'})
            return
        if path=='/api/anki/audio':
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            try:
                note_id=int(query.get('note_id',[''])[0]);payload,ext=MIRROR.audio(note_id)
                self.send_response(200);self.send_header('Content-Type',{'.mp3':'audio/mpeg','.wav':'audio/wav','.ogg':'audio/ogg','.m4a':'audio/mp4','.flac':'audio/flac'}[ext]);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            except Exception:return self.json(404,{'error':'Audio unavailable'})
            return
        if path=='/api/anki':
            try:
                due=anki('findCards',query='deck:JP is:due -is:suspended')
                reviewed=anki('findCards',query='deck:JP rated:1')
                info=anki('cardsInfo',cards=due[:50]) if due else []
                words=[re.sub('<[^>]*>','',c.get('fields',{}).get('日文',{}).get('value','')) for c in info]
                result={'ok':True,'captured_at':datetime.now(timezone.utc).isoformat(),'due_count':len(due),'reviewed_count':len(reviewed),'due_words':[w for w in words if w],'due_card_ids':due,'reviewed_card_ids':reviewed}
                return self.json(200,result)
            except Exception:return self.json(503,{'ok':False,'error':'本机 Anki 未连接，请打开 Anki 并启用 AnkiConnect。'})
        if path.startswith('/api/'):return self.json(404,{'error':'Not found'})
        # SimpleHTTPRequestHandler normalizes paths; also reject symlink escapes.
        resolved=Path(self.translate_path(self.path)).resolve()
        if not resolved.is_relative_to(PUBLIC.resolve()):return self.json(403,{'error':'Forbidden'})
        return super().do_GET()
    def do_POST(self):
        if not self.valid_host():return self.json(403,{'error':'Host not allowed'})
        origin=self.headers.get('Origin')
        if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}:return self.json(403,{'error':'Origin not allowed'})
        path=urllib.parse.urlsplit(self.path).path
        if path not in ('/api/practice','/api/anki/review','/api/classrooms','/api/classrooms/audio'):return self.json(404,{'error':'Not found'})
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=(40000 if path=='/api/classrooms' else 20000):raise ValueError('Invalid length')
            if 'application/json' not in self.headers.get('Content-Type',''):raise ValueError('JSON required')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError('JSON object required')
            if path=='/api/classrooms/audio':
                if not isinstance(data,dict) or set(data)!={'session_id'}:raise ValueError('Invalid audio request')
                try:return self.json(200,CLASSROOM.retry_audio(data['session_id']))
                except ValueError as e:return self.json(409,{'error':str(e)})
            if path=='/api/classrooms':
                try:return self.json(202,CLASSROOM.request(data))
                except ValueError as e:return self.json(409,{'error':str(e)})
            if path=='/api/anki/review':
                if not isinstance(data,dict) or data.get('operation') not in ('status','start','reveal','grade'):raise ValueError('Invalid review operation')
                if set(data)-{'operation','token','card_id','rating','request_id'}:raise ValueError('Unexpected review parameter')
                try:result=REVIEWER.request(data)
                except ValueError as e:return self.json(409,{'error':str(e)})
                except Exception:return self.json(503,{'error':'Anki 暂未连接。若刚安装复习组件，请重启 Anki 后重新读取；请勿重复评分。'})
                if data['operation']=='grade':
                    with MIRROR.lock:MIRROR.last_attempt=None
                return self.json(200,result)
            exercises=json.loads((ROOT/'study/library/exercises.json').read_text())
            textbook=ROOT/'study/library/textbook-exercises.json'
            if textbook.exists():exercises+=json.loads(textbook.read_text())['exercises']
            ex=next((e for e in exercises if e['id']==data.get('exercise_id')),None) or CLASSROOM.supplementary_exercise(data.get('exercise_id'))
            if not ex or not isinstance(data.get('response'),str) or not 0<len(data['response'].strip())<=5000:raise ValueError('Invalid response')
            # The server owns the reference and evaluation, not the request payload.
            import unicodedata
            norm=lambda s:re.sub(r'[\s。、，,.!?！？]','',unicodedata.normalize('NFKC',s))
            result='matches_reference' if any(norm(a)==norm(data['response']) for a in ex['answers']) else 'needs_teacher_review'
            record={'exercise_id':ex['id'],'prompt':ex['prompt'],'response':data['response'],'target':ex['target'],
                    'result':result,'support':data.get('support') if data.get('support') in {'answer_viewed','transcript_viewed','no_answer_shown_in_this_attempt'} else 'unknown',
                    'answered_at':datetime.now(timezone.utc).isoformat(),'source':'learning_website','mastery_updated':False,
                    'source_type':ex.get('source_type'),'source_id':ex.get('source_id'),'source_page':ex.get('source_page'),
                    'reference_status':ex.get('reference_status'),'session_id':ex.get('session_id'),
                    'phase':data.get('phase') if data.get('phase') in {'preclass','supplement'} else 'practice',
                    'listening_plays':max(0,min(100,int(data.get('listening_plays',0)))),
                    'exercise_type':ex.get('type','written')}
            if record['phase']=='supplement' and not ex.get('session_id'):raise ValueError('Not a classroom supplement')
            if record['phase']=='preclass' and ex['id'] not in {e['id'] for e in CLASSROOM.learning_plan()['review_exercises']}:raise ValueError('Review plan has changed')
            with LOCK:
                JOURNAL.parent.mkdir(parents=True,exist_ok=True)
                with JOURNAL.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
            return self.json(201,{'saved':True,'record':record})
        except (ValueError,TypeError,KeyError,json.JSONDecodeError):return self.json(400,{'error':'Invalid practice response'})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8766);args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Japanese study site: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
