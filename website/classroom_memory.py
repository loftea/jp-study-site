"""Durable, evidence-linked classroom memory, derived from committed session events."""
import hashlib

KINDS={'preference','goal','difficulty','next_step'}

def validate_updates(updates,session,turn,recorded_at):
    if not isinstance(updates,list) or len(updates)>12:raise ValueError('记忆更新格式无效。')
    evidence={m['id']:m['content'] for m in session['messages'] if m['role']=='user'}
    accepted=[]
    for i,u in enumerate(updates):
        if not isinstance(u,dict):continue
        if not all(isinstance(u.get(k),str) for k in ('operation','kind','key','content','evidence_message_id','quote')):continue
        if u['operation'] not in ('upsert','forget') or u['kind'] not in KINDS:continue
        if not 0<len(u['key'].strip())<=80 or len(u['content'])>1000:continue
        if u['operation']=='upsert' and not u['content'].strip():continue
        if not u['quote'].strip() or u['quote'] not in evidence.get(u['evidence_message_id'],''):continue
        memory_id=hashlib.sha256((u['kind']+':'+u['key'].strip()).encode()).hexdigest()[:24]
        accepted.append({**u,'key':u['key'].strip(),'memory_id':memory_id,'event_id':f'{session["id"]}:{turn["id"]}:{i}',
                         'session_id':session['id'],'recorded_at':recorded_at,'source':'classroom_agent'})
    return accepted

def project_memory(sessions):
    events=[e for s in sessions for e in s.get('memory_events',[])]
    events.sort(key=lambda e:(e['recorded_at'],e['event_id']))
    items={};seen=set()
    for event in events:
        if event['event_id'] in seen:continue
        seen.add(event['event_id'])
        items[event['memory_id']]={**event,'active':event['operation']=='upsert'}
    return {'schema_version':1,'items':sorted((x for x in items.values() if x['active']),key=lambda x:x['recorded_at'],reverse=True),
            'forgotten':[{'kind':x['kind'],'key':x['key'],'recorded_at':x['recorded_at']} for x in items.values() if not x['active']],
            'event_count':len(seen),'updated_at':events[-1]['recorded_at'] if events else None}
