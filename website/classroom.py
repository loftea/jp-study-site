"""Local classroom sessions. The server owns persistence; Codex only returns teaching text."""
from pathlib import Path
from datetime import datetime, timezone
import copy, json, os, re, shutil, subprocess, tempfile, threading, uuid
from config import CODEX_ENABLED
from study_workflow import lesson_progress, validate_checks
from classroom_memory import validate_updates, project_memory
from supplementary import day, participation, make_supplement, prepare_audio, synthesize

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / 'website/prompts'
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

def now(): return datetime.now(timezone.utc).isoformat()
def read_json(path, fallback):
    try: return json.loads(path.read_text())
    except (FileNotFoundError, ValueError): return fallback

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def cli_path():
    if not CODEX_ENABLED: return None
    return shutil.which(os.environ.get('JP_CODEX_BIN', 'codex'))

def cli_reply(session, turn, context):
    binary = cli_path()
    if not binary: raise RuntimeError('课堂默认关闭。请先安装并登录 Codex CLI，设置 JP_CODEX_ENABLED=1 后重启。')
    # No shell interpolation, no browser-supplied flags, no personal integrations or hooks.
    with tempfile.TemporaryDirectory(prefix='jp-classroom-') as temporary:
        args = [binary, 'exec', '--ignore-user-config', '--sandbox', 'read-only', '--skip-git-repo-check', '--json', '-C', temporary,
                '-c', 'approval_policy="never"', '-c', 'web_search="disabled"',
                '-c', 'model_instructions_file='+json.dumps(str(PROMPTS/'classroom-system.md'))]
        for feature in ('shell_tool','unified_exec','apps','plugins','hooks','browser_use','computer_use','multi_agent','image_generation','memories','skill_search','shell_snapshot'):
            args += ['-c', f'features.{feature}=false']
        if session.get('cli_thread_id'):
            args += ['resume', session['cli_thread_id']]
        args += ['--output-schema', str(PROMPTS/'classroom-response.schema.json'), '-']
        payload = {'kind':turn['kind'], 'current_message_id':turn['id'], 'lesson_id':session['lesson_id'],
                   'context':context, 'instruction':turn['text']}
        # Canonical website history is also supplied after a failed/interrupted CLI turn.
        if not session.get('cli_thread_id'): payload['classroom_history'] = session['messages']
        env = os.environ.copy()
        for key in ('CODEX_THREAD_ID','CODEX_INTERNAL_ORIGINATOR_OVERRIDE'): env.pop(key, None)
        try:
            p = subprocess.run(args, input=json.dumps(payload,ensure_ascii=False), text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240, env=env)
        except subprocess.TimeoutExpired:
            raise RuntimeError('教练响应超时；你的消息已保存，可重试本轮。')
        thread_id = session.get('cli_thread_id'); answer = None; completed = False; usage = None
        for line in p.stdout.splitlines():
            try: event = json.loads(line)
            except ValueError: continue
            if event.get('type') == 'thread.started': thread_id = event.get('thread_id')
            if event.get('type') == 'turn.completed': completed = True; usage = event.get('usage')
            item = event.get('item',{})
            if event.get('type') == 'item.completed' and item.get('type') == 'agent_message': answer = item.get('text')
        if p.returncode or not completed or not answer:
            # Do not return raw CLI stderr, tokens, or unrelated internal details to the page.
            raise RuntimeError('Codex 未完成本轮回复。请检查 CLI 登录、网络或额度，然后重试；消息已保留。')
        if not isinstance(thread_id,str) or not UUID.fullmatch(thread_id): raise RuntimeError('Codex 会话标识无效，请重试。')
        try: output = json.loads(answer)
        except ValueError: raise RuntimeError('教练回复格式未通过校验，请重试。')
        return output, thread_id, usage

class Classroom:
    def __init__(self, root=ROOT, directory=None, runner=cli_reply, synthesizer=synthesize):
        self.root = Path(root); self.directory = Path(directory) if directory else self.root/'study/classrooms'
        self.runner = runner; self.synthesizer = synthesizer; self.lock = threading.RLock(); self.busy = False
        # A previous server may have stopped mid-turn. Never silently rerun or duplicate it.
        if self.directory.exists():
            for path in self.directory.glob('*.json'):
                s = read_json(path,{})
                if s.get('job',{}).get('status') == 'running':
                    s['job'].update(status='error',error='服务重启中断了回复；消息已保存，请重试本轮。')
                    s['cli_thread_id'] = None; atomic_json(path,s)

    def load(self, sid):
        if not isinstance(sid,str) or not UUID.fullmatch(sid): raise ValueError('课堂编号无效。')
        s = read_json(self.directory/(sid+'.json'),None)
        if s is None: raise ValueError('没有找到这次课堂。')
        return s

    def save(self, s):
        s['updated_at'] = now(); atomic_json(self.directory/(s['id']+'.json'),s)

    def list(self):
        with self.lock:
            rows = [read_json(p,{}) for p in self.directory.glob('*.json')] if self.directory.exists() else []
            return [self.public(s,brief=True) for s in sorted(rows,key=lambda x:x.get('created_at',''),reverse=True) if s.get('id')]

    def public(self,s,brief=False):
        value = {k:copy.deepcopy(s.get(k)) for k in ('id','title','lesson_id','created_at','updated_at','ended_at','status','summary','next_step','stage','completed_activities','job')}
        value['user_answer_count'] = sum(m['role']=='user' for m in s['messages'])
        value['supplement_count'] = len(s.get('supplement',{}).get('exercises',[]))
        if not brief: value['supplement'] = copy.deepcopy(s.get('supplement'))
        if not brief: value.update(messages=copy.deepcopy(s['messages']),observations=copy.deepcopy(s['observations']),memory_updates=copy.deepcopy(s.get('last_memory_updates',[])))
        return value

    def memory(self):
        with self.lock:
            sessions=[read_json(p,{}) for p in self.directory.glob('*.json')] if self.directory.exists() else []
            return project_memory(sessions)

    def get(self,sid):
        with self.lock: return self.public(self.load(sid))

    def supplementary_exercise(self,eid):
        match=re.fullmatch(r'sup-([0-9a-f-]{36})-([1-8])',str(eid))
        if not match: return None
        with self.lock:
            try: s=self.load(match[1])
            except ValueError: return None
            return next((copy.deepcopy(e) for e in s.get('supplement',{}).get('exercises',[]) if e['id']==eid),None)

    def audio(self,sid,eid):
        with self.lock:
            s=self.load(sid)
            e=next((e for e in s.get('supplement',{}).get('exercises',[]) if e['id']==eid),None)
            if not e or not e.get('audio') or e['audio']['status']!='ready': raise ValueError('音频尚未准备好。')
            return (self.directory/'audio'/sid/(e['id']+'.wav')).read_bytes()

    def retry_audio(self,sid):
        with self.lock:
            if self.busy: raise ValueError('教练正在回复，请稍后重试音频。')
            s=self.load(sid)
            if s['status']!='ended' or not s.get('supplement'): raise ValueError('尚无课后补充练习。')
            prepare_audio(s['supplement'],self.directory/'audio'/sid,self.synthesizer)
            self.save(s)
            return self.public(s)

    def learning_plan(self):
        with self.lock:
            date=day()
            sessions=sorted([read_json(p,{}) for p in self.directory.glob('*.json')],key=lambda s:s.get('updated_at',''),reverse=True)
            learned=sorted([s for s in sessions if participation(s)],key=lambda s:max(m['created_at'] for m in participation(s)),reverse=True)
            state=read_json(self.root/'study/state.json',{})
            current=lesson_progress(self.root,sessions)['current_lesson']
            attended=[s for s in sessions if participation(s,date)]
            today_supplements=[s for s in sessions if s.get('supplement',{}).get('learning_date')==date]
            previous=next(iter(sorted([s for s in sessions if s.get('supplement') and s['supplement']['learning_date']<date],key=lambda s:s['supplement']['created_at'],reverse=True)),None)
            review=copy.deepcopy(previous['supplement']['exercises'][:5]) if previous else [e for e in read_json(self.root/'study/library/exercises.json',[]) if e.get('group') in ('review','pending')]
            return {'date':date,'timezone':'Asia/Hong_Kong','lesson_id':current,'attended_today':bool(attended),
                    'current_classroom':self.public(learned[0],brief=True) if learned else None,
                    'active_today':any(s['status']=='active' for s in attended),
                    'supplements':[self.public(s,brief=True) for s in today_supplements],
                    'review_exercises':review,'review_source':'上次课堂补充题的延迟复习' if previous else '历史课堂薄弱点与未完成题',
                    'review_session_id':previous['id'] if previous else None}

    def context(self,s):
        library = read_json(self.root/'website/dist/data/library.json',{})
        lesson = next((l for l in library.get('lessons',[]) if l['id']==s['lesson_id']),None)
        if not lesson: raise ValueError('教材课次不存在。')
        context = {'captured_at':now(),'profile':read_json(self.root/'study/profile.json',{}),
                   'prior_assessment':read_json(self.root/'study/state.json',{}),'lesson':lesson,
                   'long_term_memory':self.memory(),
                   'vocabulary':[w for w in library.get('vocabulary',[]) if w['id'] in lesson['vocabulary_ids']],
                   'grammar':[g for g in library.get('grammar',[]) if g['id'] in lesson['grammar']],
                   'exercises':[e for e in library.get('exercises',[]) if e['id'] in lesson['exercises']],
                   'recent_classrooms':[x for x in self.list() if x['id']!=s['id']][:3]}
        snap = read_json(self.root/'study/anki/website-sync/latest.json',{})
        context['anki_snapshot'] = {k:snap.get(k) for k in ('captured_at','due_count','reviewed_count')}
        notes = snap.get('notes',{})
        context['anki_snapshot']['lesson_notes'] = [n for n in notes.values() if n.get('vocabulary',{}).get('lesson_number')==lesson['number']][:100]
        journal = self.root/'study/practice/website-responses.jsonl'
        if journal.exists():
            context['recent_website_answers'] = [json.loads(l) for l in journal.read_text().splitlines() if l.strip()][-30:]
        context['legacy_session_notes'] = [{'file':p.name,'text':p.read_text()[:14000]} for p in sorted((self.root/'study/sessions').glob('*.md'))[-2:]]
        context['lesson_progress'] = lesson_progress(self.root,[read_json(p,{}) for p in self.directory.glob('*.json')])
        context['daily_words'] = read_json(self.root/'study/daily-words'/(day()+'.json'),None)
        context['supplement_eligible'] = bool(participation(s,day(context['captured_at'])))
        skill=self.root/'skills/jp-listening-tts/SKILL.md'
        context['listening_tts_skill'] = skill.read_text() if skill.exists() else ''
        return context

    def request(self,data):
        if not isinstance(data,dict): raise ValueError('请求格式无效。')
        op = data.get('operation'); rid = data.get('request_id')
        if op not in ('create','message','finish','retry'): raise ValueError('未知课堂操作。')
        if not isinstance(rid,str) or not UUID.fullmatch(rid): raise ValueError('请求编号无效。')
        allowed = {'operation','request_id','session_id','lesson_id','message'}
        if set(data)-allowed: raise ValueError('请求包含不支持的字段。')
        with self.lock:
            if op == 'create':
                path = self.directory/(rid+'.json')
                if path.exists(): return self.public(self.load(rid))
                lesson_id = data.get('lesson_id','b01')
                lib = read_json(self.root/'website/dist/data/library.json',{})
                lesson = next((l for l in lib.get('lessons',[]) if l['id']==lesson_id),None)
                if not lesson: raise ValueError('请选择有效教材课次。')
                s = {'id':rid,'title':f'第 {lesson["number"]} 课 · 文字课堂','lesson_id':lesson_id,'created_at':now(),
                     'status':'active','cli_thread_id':None,'summary':'','stage':'准备开课','next_step':'','completed_activities':[],
                     'messages':[],'observations':[],'memory_events':[],'requests':[], 'prompt_version':'1.2'}
                kind='start'; text='开始本次文字课堂。依据学习进度说明目标和安排，再进入第一组复习。不要替学生作答。'
            else:
                s=self.load(data.get('session_id'))
                if rid in s['requests']: return self.public(s)
                if s['status']=='ended': raise ValueError('本次课堂已结束，请新建课堂。')
                if op=='retry':
                    if s.get('job',{}).get('status')!='error': raise ValueError('本轮无需重试。')
                    kind=s['job']['kind']; text=s['job']['text']
                elif op=='finish': kind='finish'; text='学生点击了结束课堂。根据真实记录总结本次学习、待复习项和下次起点，不在聊天正文继续提问；按系统规则生成独立存档的课后补充练习。'
                else:
                    kind='message'; text=data.get('message')
                    if not isinstance(text,str) or not 0<len(text.strip())<=8000: raise ValueError('请输入 1–8000 字的消息。')
                    text=text.strip()
                    if re.fullmatch(r'(?:下课(?:吧|了)?|结束(?:这次)?课堂|今天(?:就)?到这里(?:吧)?|累了[，,、\s]*休息了)[。！!\s]*',text): kind='finish'
            if self.busy or s.get('job',{}).get('status')=='running': raise ValueError('教练正在回复，请稍后再发送。')
            self.busy=True
            try:
                s['requests'].append(rid)
                message_id = s['job']['id'] if op=='retry' else rid
                if op!='retry': s['messages'].append({'id':message_id,'role':'user' if op=='message' else 'control','content':text,'created_at':now(),'kind':kind})
                s['job']={'id':message_id,'kind':kind,'text':text,'status':'running','error':None,'started_at':now()}
                self.save(s)
                threading.Thread(target=self.work,args=(s['id'],),daemon=True).start()
            except Exception: self.busy=False; raise
            return self.public(s)

    def work(self,sid):
        try:
            with self.lock: s=self.load(sid); turn=copy.deepcopy(s['job'])
            context=self.context(s)
            # Store the exact lesson inputs beside the transcript for reproducibility.
            with self.lock: atomic_json(self.directory/'context'/sid/(turn['id']+'.json'),context)
            output,thread_id,usage=self.runner(s,turn,context)
            if not isinstance(output,dict) or not all(isinstance(output.get(k),str) for k in ('reply','stage','summary','next_step')) or not output['reply'].strip(): raise ValueError('教练回复格式未通过校验。')
            if not isinstance(output.get('completed_activities'),list) or not all(isinstance(x,str) for x in output['completed_activities']): raise ValueError('课堂总结格式无效。')
            if not isinstance(output.get('observations'),list): raise ValueError('学习证据格式无效。')
            evidence={m['id']:m['content'] for m in s['messages'] if m['role']=='user'}
            verified=[]
            for o in output['observations']:
                if not isinstance(o,dict): continue
                if not all(isinstance(o.get(k),str) for k in ('evidence_message_id','quote','topic','evaluation','feedback')): continue
                if o['evaluation'] not in ('independent_correct','assisted_correct','self_corrected','needs_review','unknown'): continue
                if not o['quote'].strip() or o['quote'] not in evidence.get(o['evidence_message_id'],''): continue
                verified.append({**o,'recorded_at':now(),'review_status':'ai_assessed'})
            checks=validate_checks(output.get('lesson_checks',[]),s,now())
            memory_events=validate_updates(output.get('memory_updates',[]),s,turn,now())
            supplement=None
            if turn['kind']=='finish' and context['supplement_eligible']:
                supplement=make_supplement(output.get('supplementary_exercises'),s,now())
                supplement['learning_date']=day(context['captured_at'])
                prepare_audio(supplement,self.directory/'audio'/sid,self.synthesizer)
            with self.lock:
                s=self.load(sid); s['cli_thread_id']=thread_id
                s['messages'].append({'id':str(uuid.uuid4()),'role':'assistant','content':output['reply'],'created_at':now(),'in_reply_to':turn['id']})
                for key in ('stage','summary','next_step','completed_activities'): s[key]=output[key]
                known={(o['evidence_message_id'],o['topic'],o['quote']) for o in s['observations']}
                s['observations'] += [o for o in verified if (o['evidence_message_id'],o['topic'],o['quote']) not in known]
                known_checks={(c['evidence_message_id'],c['area'],c['phase']) for c in s.get('lesson_checks',[])}
                s.setdefault('lesson_checks',[]).extend(c for c in checks if (c['evidence_message_id'],c['area'],c['phase']) not in known_checks)
                prior_memory_ids={e['event_id'] for e in s.get('memory_events',[])}
                s.setdefault('memory_events',[]).extend(e for e in memory_events if e['event_id'] not in prior_memory_ids)
                s['last_memory_updates']=memory_events
                s['job'].update(status='done',error=None,usage=usage)
                if turn['kind']=='finish':
                    s.update(status='ended',ended_at=now())
                    if supplement: s['supplement']=supplement
                self.save(s)
        except Exception as exc:
            with self.lock:
                s=self.load(sid); s['job'].update(status='error',error=str(exc) if isinstance(exc,(RuntimeError,ValueError)) else '本轮暂未完成，消息已保存，请重试。')
                # Replay canonical messages in a fresh CLI thread after uncertainty, never --last.
                s['cli_thread_id']=None; self.save(s)
        finally:
            with self.lock:self.busy=False

CLASSROOM=Classroom()
