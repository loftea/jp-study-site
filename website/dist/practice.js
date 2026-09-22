const read=async url=>{const r=await fetch(url,{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'暂时无法读取');return d;};
const hkDay=stamp=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Hong_Kong',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(stamp));
const label=s=>s==='answer_viewed'?'看过参考答案':s==='transcript_viewed'?'看过听力原文':'本次未展示答案';
const attemptHTML=(a,{esc,ruby})=>`<p class="meta">${esc(new Date(a.answered_at).toLocaleString('zh-CN'))} · ${a.phase==='preclass'?'课前复习':'补充练习'} · ${label(a.support)}${a.exercise_type==='listening'?` · 播放 ${a.listening_plays||0} 次`:''}</p><p>你的回答：${esc(a.response)}</p><p>${a.result==='matches_reference'?'与参考答案一致':'已保存，待教练核对'}</p>`;

async function mountQuestions(root,items,phase,helpers,{date,onSaved}={}){
 const {esc,ruby}=helpers;
 let records;try{records=await read('/api/practice');}catch{if(root.isConnected)root.innerHTML='<p class="notice">作答记录暂未读取成功，请刷新后再练习。</p>';return;}
 if(!root.isConnected)return;
 root.innerHTML=items.map((e,i)=>`<section class="exercise" data-question="${esc(e.id)}"><span class="eyebrow">${String(i+1).padStart(2,'0')} · ${e.type==='listening'?'听力练习':'回忆与应用'}</span><p>${ruby(e.prompt)}</p>${e.type==='listening'?`<span class="pill">原创合成语音 · Kyoko</span>${e.audio?.status==='ready'?`<div class="actions"><audio hidden preload="none" src="${esc(e.audio.url)}"></audio><button class="button secondary small" data-play>播放听力 ▶</button><span class="meta" data-audio-time>尚未播放</span></div>`:'<p class="notice">音频暂不可用，请在所属课堂的补充练习中重试合成。</p>'}<details data-transcript class="details"><summary>查看听力原文（会标记为有原文提示）</summary><p class="prose" lang="ja">${ruby(e.transcript)}</p></details>`:''}<label class="meta" for="response-${esc(e.id)}">你的回答</label><textarea id="response-${esc(e.id)}" rows="2" maxlength="5000" class="answer-input" placeholder="先回忆，再核对；听力可按要求用中文答意。"></textarea><div class="actions"><button class="button small" data-submit>提交并保存</button><button class="button secondary small" data-answer>看参考答案</button></div><div data-feedback aria-live="polite"></div><details class="details" data-history><summary>已保存的作答（${records.filter(a=>a.exercise_id===e.id).length} 次）</summary><div data-attempts>${records.filter(a=>a.exercise_id===e.id).reverse().map(a=>attemptHTML(a,helpers)).join('')||'<p class="meta">尚未作答。</p>'}</div></details></section>`).join('');
 for(const [i,section] of [...root.querySelectorAll('[data-question]')].entries()){
  const e=items[i],completed=records.some(a=>a.exercise_id===items[i].id&&a.phase===phase&&hkDay(a.answered_at)===(date||hkDay(new Date().toISOString()))),key=`jp-exercise-${phase}-${date||hkDay(new Date().toISOString())}-${e.id}`;
  section.dataset.completed=String(completed);
  if(completed)section.insertAdjacentHTML('afterbegin','<p class="pill good" data-completed>今天已提交 · 可回看或复测</p>');
  let state;try{state=JSON.parse(localStorage.getItem(key)||'{}');}catch{state={};}
  const input=section.querySelector('textarea'),feedback=section.querySelector('[data-feedback]'),submit=section.querySelector('[data-submit]');
  const saveDraft=()=>localStorage.setItem(key,JSON.stringify(state));
  const support=()=>state.answer?'answer_viewed':state.transcript?'transcript_viewed':'no_answer_shown_in_this_attempt';
  input.value=state.draft||'';input.oninput=()=>{state.draft=input.value;saveDraft();};
  const reveal=()=>{state.answer=true;saveDraft();feedback.innerHTML=`<div class="feedback"><strong>教练参考答案</strong><p>${ruby(e.target)}</p><p>${ruby(e.explanation)}</p><p class="meta">原创题的 AI 参考答案；其他合理表达需由教练核对。</p></div>`;};
  section.querySelector('[data-answer]').onclick=reveal;
  section.querySelector('[data-history]').ontoggle=ev=>{if(ev.target.open&&records.some(a=>a.exercise_id===e.id)){state.answer=true;saveDraft();}};
  const transcript=section.querySelector('[data-transcript]');if(transcript)transcript.ontoggle=()=>{if(transcript.open){state.transcript=true;saveDraft();}};
  const audio=section.querySelector('audio');if(audio){
   const play=section.querySelector('[data-play]'),time=section.querySelector('[data-audio-time]');
   play.onclick=async()=>{if(!audio.paused){audio.pause();return;}try{await audio.play();}catch{time.textContent='播放失败，请重试或重新合成音频。';}};
   audio.onplay=()=>{state.plays=(state.plays||0)+1;saveDraft();play.textContent='暂停听力 ⏸';};
   audio.onpause=()=>{play.textContent='继续播放 ▶';};audio.onended=()=>{play.textContent='再听一次 ▶';};
   audio.ontimeupdate=()=>{time.textContent=`${Math.floor(audio.currentTime)} / ${Number.isFinite(audio.duration)?Math.ceil(audio.duration):'…'} 秒`;};
   audio.onerror=()=>{time.textContent='音频加载失败，请刷新后重试。';};
  }
  submit.onclick=async()=>{
   if(!input.value.trim()){feedback.textContent='请先填写你的回答。';return;}
   if(e.type==='listening'&&!state.plays&&!state.transcript&&!state.answer){feedback.textContent='请先播放音频，再回答问题。';return;}
   submit.disabled=true;
   try{
    const r=await fetch('/api/practice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({exercise_id:e.id,response:input.value.trim(),support:support(),phase,listening_plays:state.plays||0})});
    const data=await r.json();if(!r.ok)throw Error(data.error||'保存失败');records.push(data.record);
    reveal();feedback.innerHTML=`<p class="pill good">已保存到学习记录 · ${label(data.record.support)}</p>`+feedback.innerHTML;
    const history=section.querySelector('[data-history]');history.querySelector('summary').textContent=`已保存的作答（${records.filter(a=>a.exercise_id===e.id).length} 次）`;
    section.querySelector('[data-attempts]').innerHTML=records.filter(a=>a.exercise_id===e.id).slice().reverse().map(a=>attemptHTML(a,helpers)).join('');
    section.dataset.completed='true';
    if(!section.querySelector('[data-completed]'))section.insertAdjacentHTML('afterbegin','<p class="pill good" data-completed>今天已提交 · 可回看或复测</p>');
    onSaved?.(records);
   }catch(e){feedback.textContent='保存未成功，请保留回答后重试。'+e.message;}
   finally{submit.disabled=false;}
  };
 }
}

export async function mountSupplement(root,session,helpers){
 const {esc}=helpers;
 const pack=session.supplement;
 if(!pack){root.innerHTML=`<h2>补充练习</h2><p class="muted">${session.status==='ended'?'这次课堂没有保存补充练习。早期记录不会自动补写成已上课的内容。':'完成课堂后，点击“结束课堂并总结”，教练会生成含听力的补充练习。'}</p>`;return;}
 root.innerHTML=`<div class="section-heading" style="margin-top:0"><h2>课后补充练习</h2><span class="pill">已随课堂保存 · ${pack.exercises.length} 题</span></div><p class="meta">${esc(pack.learning_date)} · ${esc(pack.source)}。作答与提示情况单独记录，不自动判为掌握。</p>${pack.audio_status==='error'?'<p class="notice">题目已保存，部分音频合成失败。</p><button class="button secondary small" data-retry-audio>重试音频合成</button><p data-audio-status class="meta" role="status"></p>':''}<div data-supplement-questions></div>`;
 const retry=root.querySelector('[data-retry-audio]');if(retry)retry.onclick=async()=>{retry.disabled=true;root.querySelector('[data-audio-status]').textContent='正在本机合成，请稍候…';try{const r=await fetch('/api/classrooms/audio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:session.id})});const d=await r.json();if(!r.ok)throw Error(d.error);if(root.isConnected)mountSupplement(root,d,helpers);}catch(e){if(root.isConnected){root.querySelector('[data-audio-status]').textContent=e.message;retry.disabled=false;}}};
 await mountQuestions(root.querySelector('[data-supplement-questions]'),pack.exercises,'supplement',helpers);
}

export async function mountPractice(root,id,helpers){
 const {esc,ruby}=helpers;
 root.innerHTML='<p class="loading">正在读取练习安排…</p>';
 try{
  if(id&&id!=='review'){
   const s=await read('/api/classrooms?id='+encodeURIComponent(id));if(!root.isConnected)return;
   root.innerHTML=`<div class="page-head"><div><span class="eyebrow">CLASSROOM SUPPLEMENT</span><h1>${esc(s.title)} · 补充练习</h1><div class="actions"><a class="text-link" href="#classroom/${s.id}">查看完整对话 →</a><a class="text-link" href="#progress">学习记录 →</a><a class="text-link" href="#practice">今日练习 →</a></div></div></div><section class="panel" data-pack></section>`;
   await mountSupplement(root.querySelector('[data-pack]'),s,helpers);return;
  }
  const plan=await read('/api/learning-plan');if(!root.isConnected)return;
  root.innerHTML=`<div class="page-head"><div><span class="eyebrow">PRACTICE & RECALL</span><h1>重点练习</h1><p class="muted">课前回忆旧知识，课后做教材原题和本次课堂的补充题。</p></div></div><section class="panel"><span class="eyebrow">01 · TEXTBOOK</span><h2>课后练习</h2><p class="muted">当前学习：第 ${Number(plan.lesson_id.slice(1))} 课。打开教材对应的练习页，直接对照原页作答。</p><div class="actions"><a class="button" href="#textbook/${plan.lesson_id}">当前课的课后练习 →</a><a class="button secondary" href="#library">选择其他课次</a></div></section><section class="panel" id="preclass-review"><span class="eyebrow">02 · BEFORE CLASS</span><h2>复习练习</h2><p class="muted">上课前完成，约 5–10 分钟。来源：${esc(plan.review_source)}${plan.review_session_id?` · <a class="text-link" href="#classroom/${plan.review_session_id}">查看来源课堂</a>`:''}。</p><p class="meta" data-review-count></p><details class="details" data-review-expand><summary>展开课前复习（${plan.review_exercises.length} 题）</summary><div data-review-questions></div></details><div class="actions"><a class="button secondary" href="#classroom">复习后进入课堂 →</a></div></section><section class="panel"><span class="eyebrow">03 · AFTER CLASS</span><h2>补充练习</h2>${plan.supplements.length?plan.supplements.map(s=>`<div class="record"><h3>${esc(s.title)}</h3><p class="meta">今天下课时保存 · ${s.supplement_count} 道原创题，含听力</p><a class="button" href="#practice/${s.id}">开始补充练习 →</a></div>`).join(''):`<p class="notice">${plan.attended_today?'今天的课堂尚未生成补充练习。请完成课堂并点击“结束课堂并总结”。':'今天还没有上课。上课并结束课堂后，这里会显示教练准备的补充练习（含听力）。'}</p><a class="button secondary" href="#classroom">${plan.active_today?'继续课堂':'进入课堂'} →</a>`}<p class="meta">按香港日期 ${esc(plan.date)} 显示。往日补充练习保存在对应课堂的学习记录里。</p><a class="text-link" href="#progress">查看历史课堂与补充练习 →</a></section>`;
  const count=rows=>{if(root.isConnected)root.querySelector('[data-review-count]').textContent=`今天已提交 ${new Set(rows.filter(a=>a.phase==='preclass'&&hkDay(a.answered_at)===plan.date&&plan.review_exercises.some(e=>e.id===a.exercise_id)).map(a=>a.exercise_id)).size} / ${plan.review_exercises.length} 题 · 提交量不等于掌握量`;};
  count(await read('/api/practice'));
  await mountQuestions(root.querySelector('[data-review-questions]'),plan.review_exercises,'preclass',{esc,ruby},{date:plan.date,onSaved:count});
  if(id==='review'&&root.isConnected){root.querySelector('[data-review-expand]').open=true;(root.querySelector('[data-question][data-completed="false"]')||root.querySelector('#preclass-review')).scrollIntoView({block:'start'});}
 }catch(e){if(root.isConnected)root.innerHTML=`<p class="notice">${esc(e.message)}</p><a class="button secondary" href="#today">返回今日学习</a>`;}
}

export async function mountPreclassCard(root,{esc}){
 try{
  const [p,rows]=await Promise.all([read('/api/learning-plan'),read('/api/practice')]);if(!root.isConnected)return;
  const done=new Set(rows.filter(a=>a.phase==='preclass'&&hkDay(a.answered_at)===p.date&&p.review_exercises.some(e=>e.id===a.exercise_id)).map(a=>a.exercise_id)).size;
  root.innerHTML=`<div><span class="eyebrow">BEFORE YOUR LESSON</span><h2>上课前，再做一组复习</h2><p class="muted">Anki 到期复习之后，用 5–10 分钟回忆旧知识，再进入文字课堂。</p><p class="meta">${esc(p.review_source)} · 今天已提交 ${done} / ${p.review_exercises.length} 题</p></div><div class="actions"><a class="button" href="#practice/review">${done===p.review_exercises.length?'回看课前复习':'开始复习练习'} →</a><a class="button secondary" href="#classroom">进入课堂</a></div>`;
  return p;
 }catch{if(root.isConnected)root.innerHTML='<h2>课前复习</h2><p class="meta">暂时无法读取进度。</p><a class="text-link" href="#practice/review">打开复习练习 →</a>';}
}
