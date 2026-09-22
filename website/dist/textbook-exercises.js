let catalogPromise;
const labels={I1:'练习Ⅰ · 1　句型替换',I3:'练习Ⅰ · 3　会话替换',I4:'练习Ⅰ · 4　看图会话',I6:'练习Ⅰ · 6　肯否定问答',II1:'练习Ⅱ · 1　填空',II2:'练习Ⅱ · 2　选择',II4:'练习Ⅱ · 4　词语组句',II5:'练习Ⅱ · 5　中译日'};
export async function mountTextbookExercises(root,lesson,{esc,ruby,localAPI}){
 root.innerHTML='<p class="loading">正在读取教材练习…</p>';
 try{
  catalogPromise ||= fetch('data/textbook-exercises.json').then(r=>{if(!r.ok)throw Error('data unavailable');return r.json()});
  const data=await catalogPromise;if(!root.isConnected)return;
  const book=data.lessons[lesson.id];
  if(!book){root.innerHTML='<p class="notice">这份初级下 EPUB 没有完整的课后练习，当前也没有对应扫描原书。原题待补充；下方仍可做已准备的补充练习。</p>';return;}
  let history=[];try{history=localAPI?await(await fetch('/api/practice')).json():JSON.parse(localStorage.getItem('jp-practice')||'[]');}catch{}
  if(!root.isConnected)return;
  const actual=data.exercises.filter(e=>book.question_ids.includes(e.id));
  const groups=[...new Set(actual.map(e=>e.section))];let page=book.pages[0],group=groups[0],mode='pages';
  const positionKey='jp-textbook-position-'+lesson.id;
  try{const pos=JSON.parse(localStorage.getItem(positionKey)||'{}');page=book.pages.find(p=>p.page===pos.page)||page;group=groups.includes(pos.group)?pos.group:group;mode=pos.mode==='questions'&&actual.length?'questions':'pages';}catch{}

  const revealed=new Set(history.filter(e=>book.question_ids.includes(e.exercise_id)).map(e=>e.exercise_id));
  for(const e of actual){try{if(localStorage.getItem('jp-reference-seen-'+e.id))revealed.add(e.id);}catch{}}
  function markRevealed(id){revealed.add(id);try{localStorage.setItem('jp-reference-seen-'+id,'1');}catch{}}
  const last=id=>history.filter(e=>e.exercise_id===id).at(-1);
  function draft(e){try{return localStorage.getItem('jp-draft-'+e.id)??last(e.id)?.response??'';}catch{return last(e.id)?.response??'';}}
  function form(e){const old=last(e.id);return `<section class="exercise textbook-question"><p class="textbook-prompt">${ruby(e.prompt).replace(/\n/g,'<br>')}</p><label class="meta" for="tb-${e.id}">${e.source_type==='textbook_scan_exercise'?'按原书题号填写，例如“1（1）……”':'你的回答'}</label><textarea id="tb-${e.id}" data-draft="${e.id}" class="answer-input" rows="${e.source_type==='textbook_scan_exercise'?6:e.response_type==='open_dialogue'?4:2}" placeholder="先自己作答，草稿会保留在本浏览器。">${esc(draft(e))}</textarea><div class="actions"><button class="button small" data-tb-save="${e.id}">${e.source_type==='textbook_scan_exercise'?'保存本页回答':'保存并核对'}</button>${e.reference_status==='coach_prepared_not_official_key'?`<button class="button secondary small" data-tb-reveal="${e.id}">查看参考表达</button>`:''}</div><div id="tb-result-${e.id}" class="meta" aria-live="polite">${old?'已有保存记录 · '+esc(new Date(old.answered_at).toLocaleString('zh-CN')):''}</div></section>`;}
  function render(){
   try{localStorage.setItem(positionKey,JSON.stringify({page:page.page,group,mode}));}catch{}
   const questions=mode==='questions'?actual.filter(e=>e.section===group):[data.exercises.find(e=>e.id===page.response_id)];
   const shown=mode==='questions'?book.pages.find(p=>p.page===questions[0].source_page):page;
   root.innerHTML=`<div class="section-heading"><h2>教材原题</h2><span class="pill">第 ${book.number} 课 · ${book.pages.length} 页</span></div><p class="muted">直接阅读《标日》初级上第二版 PDF 原页，图表和排版保留原样。在下方按题号填写回答即可。</p><div class="toolbar">${actual.length?`<label for="tb-mode">练习方式</label><select class="select" id="tb-mode"><option value="pages" ${mode==='pages'?'selected':''}>PDF 原页作答</option><option value="questions" ${mode==='questions'?'selected':''}>已整理的逐题练习（${actual.length} 题）</option></select>`:''}${mode==='questions'?`<label for="tb-group">题组</label><select class="select" id="tb-group">${groups.map(g=>`<option value="${g}" ${g===group?'selected':''}>${labels[g]||esc(g)}</option>`).join('')}</select>`:`<label for="tb-page">PDF 页码</label><select class="select" id="tb-page">${book.pages.map(p=>`<option value="${p.page}" ${p.page===page.page?'selected':''}>PDF 第 ${p.page} 页</option>`).join('')}</select><button class="button secondary small" data-tb-step="-1" ${page===book.pages[0]?'disabled':''}>上一页</button><button class="button secondary small" data-tb-step="1" ${page===book.pages.at(-1)?'disabled':''}>下一页</button>`}</div><details class="textbook-source details" ${mode==='pages'||group==='I4'?'open':''}><summary>PDF 原页 · 第 ${shown.page} 页</summary><a class="text-link" href="${shown.image}" target="_blank" rel="noopener">放大查看原页 ↗</a><img class="textbook-scan" src="${shown.image}" alt="《标日》初级上第${book.number}课练习，扫描第${shown.page}页" loading="lazy">${group==='I4'&&mode==='questions'?`<p class="meta">跨页会话例句见下一页。</p><img class="textbook-scan" src="${book.pages[1].image}" alt="看图会话的跨页例句" loading="lazy">`:''}</details><p class="source-note">教材听力题的对应录音尚未接入，先做文字与图文题。</p><div>${questions.map(form).join('')}</div><p class="meta">保存的是实际回答与题目来源。开放会话、原页作答及其他合理表达由教练核对，不会自动算作已掌握。</p>`;
   root.querySelector('#tb-mode')?.addEventListener('change',e=>{mode=e.target.value;render()});
   root.querySelector('#tb-group')?.addEventListener('change',e=>{group=e.target.value;render()});
   root.querySelector('#tb-page')?.addEventListener('change',e=>{page=book.pages.find(p=>p.page===Number(e.target.value));render()});
   root.querySelectorAll('[data-tb-step]').forEach(b=>b.onclick=()=>{const next=book.pages.indexOf(page)+Number(b.dataset.tbStep);if(book.pages[next]){page=book.pages[next];render();}});
   root.querySelectorAll('[data-draft]').forEach(t=>t.oninput=()=>{try{localStorage.setItem('jp-draft-'+t.dataset.draft,t.value);}catch{}});
   root.querySelectorAll('[data-tb-reveal]').forEach(b=>b.onclick=()=>{const e=data.exercises.find(x=>x.id===b.dataset.tbReveal);markRevealed(e.id);root.querySelector('#tb-result-'+e.id).innerHTML=`<div class="feedback">参考表达（教练编写）：<br>${ruby(e.target)}<br>${ruby(e.explanation)}<p class="meta">已看参考，本题后续提交记为有提示。</p></div>`;});
   root.querySelectorAll('[data-tb-save]').forEach(b=>b.onclick=async()=>{
    const e=data.exercises.find(x=>x.id===b.dataset.tbSave),response=root.querySelector('#tb-'+e.id).value.trim(),feedback=root.querySelector('#tb-result-'+e.id);
    if(!response){feedback.textContent='请先填写回答。';return;}
    b.disabled=true;const entry={exercise_id:e.id,response,support:revealed.has(e.id)?'answer_viewed':'no_answer_shown_in_this_attempt'};
    try{
     let record;
     if(localAPI){const r=await fetch('/api/practice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(entry)});if(!r.ok)throw Error('save failed');record=(await r.json()).record;}
     else{record={...entry,prompt:e.prompt,target:e.target,result:'needs_teacher_review',source_type:e.source_type,source_page:e.source_page,answered_at:new Date().toISOString()};const rows=JSON.parse(localStorage.getItem('jp-practice')||'[]');rows.push(record);localStorage.setItem('jp-practice',JSON.stringify(rows));}
     history.push(record);const matched=record.result==='matches_reference';
     feedback.innerHTML=`<div class="feedback ${matched?'correct':''}"><strong>${localAPI?'已保存到学习库':'已保存到本浏览器'} · ${matched?'与参考一致':'待教练核对'}</strong>${e.reference_status==='coach_prepared_not_official_key'?`<p>参考表达（教练编写）：<br>${ruby(e.target)}</p><p>${ruby(e.explanation)}</p>`:'<p>已保留你的原始回答与 PDF 页码，待课后核对。</p>'}<span class="meta">${entry.support==='answer_viewed'?'有提示':'提交前未在此题展示参考'} · 不自动更新掌握状态</span></div>`;
     // Submitting also exposes the reference; subsequent attempts are assisted.
     if(e.reference_status==='coach_prepared_not_official_key')markRevealed(e.id);
    }catch{feedback.textContent='保存未成功，回答仍保留在输入框和本浏览器草稿中，请重试。';}
    finally{b.disabled=false;}
   });
  }
  render();
 }catch{catalogPromise=null;if(root.isConnected)root.innerHTML='<p class="notice">教材练习暂未读取成功，请重新进入本课。</p>';}
}
