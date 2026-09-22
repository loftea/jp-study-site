"""Durable, classroom-bound exercises and local Japanese speech synthesis."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import copy, json, re, subprocess, tempfile, wave

HK = ZoneInfo('Asia/Hong_Kong')

def day(stamp=None):
    return (datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(HK) if stamp else datetime.now(HK)).date().isoformat()

def participation(session, date=None):
    """A learner message must have received a teacher response; opening alone isn't class."""
    replied = {m.get('in_reply_to') for m in session['messages'] if m['role']=='assistant'}
    return [m for m in session['messages'] if m['role']=='user' and m.get('kind')!='finish' and m['id'] in replied
            and (date is None or day(m['created_at'])==date)]

def synthesize(text, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jp-tts-') as tmp:
        source=Path(tmp)/'speech.txt'; aiff=Path(tmp)/'speech.aiff'; wav=Path(tmp)/'speech.wav'
        source.write_text(text, encoding='utf-8')
        subprocess.run(['/usr/bin/say','-v','Kyoko','-r','155','-f',str(source),'-o',str(aiff)],check=True,timeout=45,capture_output=True)
        subprocess.run(['/usr/bin/afconvert','-f','WAVE','-d','LEI16',str(aiff),str(wav)],check=True,timeout=20,capture_output=True)
        with wave.open(str(wav),'rb') as f:
            duration=f.getnframes()/f.getframerate()
            if duration<.2 or not any(f.readframes(f.getnframes())): raise ValueError('Empty speech')
            meta={'duration_seconds':round(duration,2),'sample_rate':f.getframerate(),'channels':f.getnchannels()}
        # Replace only after a complete, non-silent PCM file is available.
        stage=destination.with_suffix('.tmp'); stage.write_bytes(wav.read_bytes()); stage.replace(destination)
    return {**meta,'voice':'Kyoko','rate':155,'engine':'macOS say','source':'原创合成语音，非教材原音','audited_by_listening':False}

def make_supplement(items, session, stamp):
    if not isinstance(items,list) or not 3<=len(items)<=8: raise ValueError('下课补充练习应包含 3–8 题，请重试本轮。')
    evidence={m['id']:m['content'] for m in participation(session)}
    exercises=[]
    for i,item in enumerate(items):
        if not isinstance(item,dict): raise ValueError('补充练习格式无效。')
        for key,limit in {'prompt':1500,'target':1500,'explanation':2000,'topic':200,'transcript':2500,'tts_text':1500,'evidence_message_id':80,'quote':2000}.items():
            if not isinstance(item.get(key),str) or len(item[key])>limit: raise ValueError('补充练习字段无效。')
        if not all(item[k].strip() for k in ('prompt','target','explanation','topic','quote')): raise ValueError('补充练习缺少题目或依据。')
        if item['quote'] not in evidence.get(item['evidence_message_id'],''): raise ValueError('补充题没有引用本课堂真实学习内容。')
        if item.get('type') not in ('written','listening'): raise ValueError('补充题型无效。')
        if not isinstance(item.get('answers'),list) or not 1<=len(item['answers'])<=12 or not all(isinstance(a,str) and 0<len(a)<=1500 for a in item['answers']): raise ValueError('补充题参考答案无效。')
        if item['type']=='listening':
            if not item['transcript'].strip() or not item['tts_text'].strip(): raise ValueError('听力题缺少合成稿。')
            if not re.fullmatch(r'[ぁ-ゖァ-ヺー\s。、！？!?・「」『』…〜～]+',item['tts_text']): raise ValueError('听力合成稿须为假名和标点，不含汉字注音或指令。')
        elif item['transcript'] or item['tts_text']: raise ValueError('文字题不应包含听力稿。')
        exercises.append({**copy.deepcopy(item),'id':f"sup-{session['id']}-{i+1}",'session_id':session['id'],
                          'lesson_id':session['lesson_id'],'source_type':'classroom_supplement','source_id':session['id'],
                          'reference_status':'ai_generated','audio':{'status':'pending'} if item['type']=='listening' else None})
    if not any(e['type']=='listening' for e in exercises): raise ValueError('补充练习缺少听力题，请重试本轮。')
    return {'schema_version':1,'created_at':stamp,'learning_date':day(stamp),'lesson_id':session['lesson_id'],
            'source':'教练依据本课堂编写的原创补充练习','exercises':exercises}

def prepare_audio(supplement, directory, synthesizer=synthesize):
    for e in supplement['exercises']:
        if e['type']!='listening' or e['audio']['status']=='ready': continue
        try:
            metadata=synthesizer(e['tts_text'],Path(directory)/(e['id']+'.wav'))
            e['audio']={'status':'ready',**metadata,'url':f"/api/classrooms/audio?session_id={e['session_id']}&exercise_id={e['id']}"}
        except Exception:
            e['audio']={'status':'error','error':'本机语音合成未完成。题目已保存，可点击重试音频。'}
    supplement['audio_status']='ready' if all(e['audio']['status']=='ready' for e in supplement['exercises'] if e['audio']) else 'error'
    return supplement
