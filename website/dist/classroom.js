import {mountSupplement} from './practice.js';
const api='/api/classrooms';
const stamp=x=>new Date(x).toLocaleString('zh-CN');
const memoryKind=k=>({preference:'学习偏好',goal:'学习目标',difficulty:'待巩固',next_step:'下次起点'})[k]||'学习记忆';
const status=s=>s.status==='ended'?'已结束':s.job?.status==='running'?'教练回复中':s.job?.status==='error'?'等待重试':'进行中';
async function request(body){const r=await fetch(api,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok){const e=Error(d.error||'请求失败');e.definitive=r.status>=400&&r.status<500;throw e;}return d;}
export async function mountClassroom(root,id,{esc,ruby,lessons}){
 let timer,session,revision='',loading=false;
 const alive=()=>root.isConnected;
 const rich=text=>ruby(text).replace(/\*\*([^\n]+?)\*\*/g,'<strong>$1</strong>').replace(/^#{1,4} (.+)$/gm,'<strong class="class-text-heading">$1</strong>').replace(/\[([^\]\n]+)\]\((#(?:lesson|textbook)\/b\d{2})\)/g,'<a class="text-link" href="$2">$1</a>');
 root.innerHTML='<p class="loading">正在读取课堂…</p>';
 function notice(message){if(alive())root.querySelector('#class-notice').textContent=message;}
 function pendingKey(){return 'jp-class-pending-'+(id||'create');}
 async function action(operation,extra={}){
  if(loading)return; loading=true; notice('正在保存…');updateControls();
  let command;
  try{
   // Reuse the same request ID after a transport failure. A second click cannot double-send.
   command=JSON.parse(sessionStorage.getItem(pendingKey())||'null');
   if(!command){command={operation,request_id:crypto.randomUUID(),...(id?{session_id:id}:{}),...extra};sessionStorage.setItem(pendingKey(),JSON.stringify(command));}
   const d=await request(command);sessionStorage.removeItem(pendingKey());
   if(!id){location.hash='#classroom/'+d.id;return;}
   if(command.operation==='message'){localStorage.removeItem('jp-class-draft-'+id);root.querySelector('#class-message').value='';}
   session=d;drawSession();notice('消息已保存。教练正在回复…');schedule();
  }catch(e){if(e.definitive)sessionStorage.removeItem(pendingKey());notice(e.message+(e.definitive?'':' 若是连接中断，再点一次会恢复同一请求。'));}
  finally{loading=false;updateControls();}
 }
 function updateControls(){
  if(!alive())return;
  const pending=!!sessionStorage.getItem(pendingKey());
  root.querySelectorAll('[data-class-action]').forEach(b=>b.disabled=loading||session?.job?.status==='running'||(b.dataset.classAction!=='retry'&&session?.job?.status==='error')||session?.status==='ended');
  const input=root.querySelector('#class-message');if(input)input.disabled=loading||session?.status==='ended';
  if(pending&&!loading)notice('有一条请求等待确认。再次点击操作按钮将恢复该请求，不会重复发送。');
 }
 function drawSession(){
  if(!alive())return;
  const rev=JSON.stringify([session.updated_at,session.job?.status]);
  if(rev===revision)return;revision=rev;
  root.querySelector('#class-title').textContent=session.title;
  root.querySelector('#class-status').textContent=status(session);
  root.querySelector('#class-stage').textContent=session.stage||'准备开课';
  const list=root.querySelector('#class-messages');
  const nearBottom=list.scrollHeight-list.scrollTop-list.clientHeight<100;
  list.innerHTML=session.messages.map(m=>`<article class="class-message ${m.role}"><div class="meta">${m.role==='user'?'你':m.role==='assistant'?'日语教练':'课堂事件'} · ${esc(stamp(m.created_at))}</div><div class="class-message-text">${m.role==='assistant'?rich(m.content):m.role==='control'?(m.kind==='finish'?'结束课堂并生成总结':'开始课堂'):esc(m.content)}</div></article>`).join('');
  if(nearBottom)list.scrollTop=list.scrollHeight;
  root.querySelector('#class-retry').hidden=session.job?.status!=='error';
  root.querySelector('#class-form').hidden=session.status==='ended';
  if(session.status==='ended')root.querySelector('#class-help').textContent='这次课堂已归档，可随时回看完整对话。继续学习请到“我的课堂”新建课堂。';
  root.querySelector('#class-memory').innerHTML=(session.memory_updates||[]).length?`<details class="details"><summary>本轮已保存 ${(session.memory_updates||[]).length} 项记忆更新</summary>${session.memory_updates.map(m=>`<p class="meta">${esc(memoryKind(m.kind))} · ${esc(m.key)}<br>${m.operation==='forget'?'已从有效记忆中移除':rich(m.content)}</p>`).join('')}</details>`:'';
  root.querySelector('#class-summary').innerHTML=session.summary?`<h3>${session.status==='ended'?'课堂总结':'本次学习小结'}</h3><div class="class-message-text">${rich(session.summary)}</div><p style="margin-top:16px"><strong>下次起点：</strong>${rich(session.next_step)}</p><p class="meta">AI 根据实际对话整理；会话结束不代表整课已掌握。</p>`:'';
  mountSupplement(root.querySelector('#class-supplement'),session,{esc,ruby});
  notice(session.job?.status==='error'?session.job.error:session.job?.status==='running'?'消息已保存，教练正在回复。切换页面或刷新不会丢失记录。':session.status==='ended'?'本次课堂已结束，完整对话与总结已保存。':'对话已保存。');
  updateControls();
 }
 function schedule(){clearTimeout(timer);if(alive()&&session?.job?.status==='running')timer=setTimeout(poll,1800);}
 async function poll(){if(!alive())return;try{const r=await fetch(api+'?id='+encodeURIComponent(id),{cache:'no-store'});if(!r.ok)throw Error('课堂暂时读取失败');session=await r.json();drawSession();}catch(e){notice(e.message+'，稍后自动重连。');}schedule();}
 try{
  if(!id){
   const r=await fetch(api);if(!r.ok)throw Error('请通过本机学习网站打开课堂。');const data=await r.json();if(!alive())return;
   root.innerHTML=`<div class="page-head"><div><span class="eyebrow">YOUR JAPANESE CLASSROOM</span><h1>和教练上课</h1><p class="muted">一节课，一段持续的对话。文字讲解与练习，全程保存。</p></div></div><section class="panel"><h2>开始一节新课</h2><p>先完成 Anki 到期复习和<a class="text-link" href="#practice/review">课前复习练习</a>，再选择教材课次。教练会结合已有学习记录安排复习和讲解。</p><div class="toolbar"><label for="class-lesson">教材课次</label><select id="class-lesson" class="select">${lessons.map(l=>`<option value="${l.id}">第 ${l.number} 课 · ${esc(l.title_raw)}</option>`).join('')}</select><button class="button" id="class-new" data-class-action="create">开始新课堂</button></div><p class="meta">文字消息及所选教材、学习记录会交给已登录的本机 Codex CLI，使用该账号的 Codex 额度。课堂不会代你操作 Anki。</p><p id="class-notice" role="status" class="meta">${data.cli_available?'Codex CLI 已找到':'未找到 Codex CLI，请先安装并登录'}</p></section><div class="section-heading"><h2>我的课堂</h2></div><div class="class-session-list">${data.sessions.length?data.sessions.map(s=>`<a class="panel class-session" href="#classroom/${s.id}"><span class="pill">${status(s)}</span><h3>${esc(s.title)}</h3><p class="meta">${esc(stamp(s.created_at))} · ${s.user_answer_count} 条学生消息</p><p>${esc(s.summary||'已建立课堂，等待开始。')}</p><span class="text-link">${s.status==='ended'?'查看完整记录':'继续课堂'} →</span></a>`).join(''):'<p class="empty">还没有网站课堂。开始后，每次对话都会出现在这里。</p>'}</div>`;
   root.querySelector('#class-new').onclick=()=>action('create',{lesson_id:root.querySelector('#class-lesson').value});updateControls();return;
  }
  root.innerHTML=`<div class="page-head"><div><div class="actions" style="margin-top:0"><a class="text-link" href="#progress">← 学习记录</a><a class="text-link" href="#classroom">我的课堂</a></div><h1 id="class-title">文字课堂</h1><span id="class-status" class="pill"></span> <span id="class-stage" class="meta"></span></div><a class="button secondary" id="class-book" href="#library">打开教材</a></div><section class="panel classroom-panel"><h2>完整课堂对话</h2><p class="meta">按时间顺序保留你的原始回答和教练回复，可滚动回看。</p><div id="class-messages" class="class-messages" aria-label="课堂对话"></div><p id="class-notice" class="meta" role="status"></p><form id="class-form"><label for="class-message">你的回答或问题</label><textarea id="class-message" class="answer-input" rows="4" maxlength="8000" placeholder="直接回答，或告诉教练哪里需要多讲一点。"></textarea><div class="actions"><button class="button" data-class-action="message" type="submit">发送</button><button type="button" class="button secondary" id="class-finish" data-class-action="finish">结束课堂并总结</button><button type="button" class="button secondary" id="class-retry" data-class-action="retry" hidden>重试本轮</button></div></form><div id="class-memory" aria-live="polite"></div><p id="class-help" class="meta" style="margin-top:14px">刷新后可继续同一对话。暂时离开无需结束课堂。语音跟读和模拟仍在 App 对话中进行。</p></section><section id="class-summary" class="panel"></section><section id="class-supplement" class="panel"></section>`;
  const input=root.querySelector('#class-message');input.value=localStorage.getItem('jp-class-draft-'+id)||'';input.oninput=()=>localStorage.setItem('jp-class-draft-'+id,input.value);
  root.querySelector('#class-form').onsubmit=e=>{e.preventDefault();if(!input.value.trim()){notice('先输入你的回答或问题。');return;}action('message',{message:input.value});};
  root.querySelector('#class-finish').onclick=()=>{if(input.value.trim()){notice('输入框还有未发送的内容，请先发送或清空，再结束课堂。');return;}action('finish');};root.querySelector('#class-retry').onclick=()=>action('retry');
  await poll();if(session&&alive())root.querySelector('#class-book').href='#lesson/'+session.lesson_id;
 }catch(e){if(alive())root.innerHTML=`<p class="notice">${esc(e.message)}</p><a class="button secondary" href="#classroom">返回课堂列表</a>`;}
}
export async function classroomRecords(root,{esc}){
 const read=async url=>{const r=await fetch(url);if(!r.ok)throw Error('unavailable');return r.json();};
 const [live,legacy]=await Promise.allSettled([read(api),read('data/legacy-classrooms.json')]);
 if(!root.isConnected)return;
 const sessions=live.status==='fulfilled'?live.value.sessions:[];
 const historical=legacy.status==='fulfilled'?legacy.value:[];
 const rows=[...sessions,...historical].sort((a,b)=>(b.created_at||b.date).localeCompare(a.created_at||a.date));
 root.innerHTML=rows.map(s=>{
  const old=s.record_kind==='legacy_summary';
  const meta=old?`${s.date_label} · ${s.status_label} · 历史摘要`:`${stamp(s.created_at)} · ${status(s)} · ${s.user_answer_count} 条学生消息`;
  return `<div class="record"><span class="meta">${esc(meta)}</span><h3>${old?esc(s.title):`<a href="#classroom/${s.id}">${esc(s.title)}</a>`}</h3><p class="class-record-summary">${esc(s.summary||'对话进行中，尚未生成学习小结。')}</p>${s.scores?.length?`<div class="score-row">${s.scores.map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}${s.note?`<p class="meta" style="margin-top:14px">${esc(s.note)}</p>`:''}${s.next_step?`<p class="meta">下次起点：${esc(s.next_step)}</p>`:''}${old?'<p class="meta">早期课堂保留学习摘要，暂无完整对话回放。</p>':`<div class="actions"><a class="button secondary small" href="#classroom/${s.id}">查看完整对话 →</a>${s.supplement_count?`<a class="button secondary small" href="#practice/${s.id}">补充练习 · ${s.supplement_count} 题 →</a>`:''}</div>`}</div>`;
 }).join('');
 if(!rows.length&&live.status==='fulfilled'&&legacy.status==='fulfilled')root.innerHTML='<p class="muted">还没有课堂记录。开始课堂后，这里会保存总结和完整对话。</p>';
 if(live.status==='rejected')root.innerHTML+='<p class="meta">网站课堂暂未读取成功，已保留可用历史记录；请稍后刷新。</p>';
 if(legacy.status==='rejected')root.innerHTML+='<p class="meta">早期学习摘要暂未读取成功，请稍后刷新。</p>';
 return sessions;
}

export async function mountClassroomMemory(root,{esc}){
 root.innerHTML='<h2>教练的长期记忆</h2><p class="meta">正在读取…</p>';
 try{
  const r=await fetch('/api/classrooms/memory',{cache:'no-store'});if(!r.ok)throw Error();const data=await r.json();if(!root.isConnected)return;
  root.innerHTML=`<h2>教练的长期记忆</h2><p class="meta">每次下课总结时，教练会自动整理并保存有依据的新记忆，供后续课堂读取，无需逐条提醒。你也可以随时要求更正或忘记某条记忆。</p>${data.items.length?`<div class="class-memory-list">${data.items.map(m=>`<section class="class-memory-item"><span class="pill">${esc(memoryKind(m.kind))}</span><h3>${esc(m.key)}</h3><p>${esc(m.content)}</p><details class="details"><summary>查看记忆依据</summary><p class="meta">${esc(stamp(m.recorded_at))}</p><p class="meta">你的原话：${esc(m.quote)}</p><a class="text-link" href="#classroom/${m.session_id}">查看来源课堂 →</a></details></section>`).join('')}</div>`:'<p class="muted">尚未新增长期记忆。教练仍会读取已保存的学习档案；每次下课会自动检查并保存有依据的新偏好、薄弱点和下次起点。</p>'}`;
 }catch{if(root.isConnected)root.innerHTML='<h2>教练的长期记忆</h2><p class="meta">暂未读取成功，请稍后刷新。</p>';}
}
