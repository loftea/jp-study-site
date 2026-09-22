export function mountDailyPreparation(root,{esc}){
 let revision='',timer;
 const refresh=async()=>{
  if(!root.isConnected){document.removeEventListener('visibilitychange',onVisible);clearTimeout(timer);return;}
  try{
   const r=await fetch('/api/daily-preparation',{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error);
   if(!root.isConnected)return;
   const next=d.source_fingerprint+d.generated_at;
   if(next!==revision){revision=next;
    // Guidance mixes Chinese prose and Japanese words; keep explicit parenthetical readings.
    root.innerHTML=`<span class="pill">${esc(d.date)} · 第 ${Number(d.lesson_id.slice(1))} 课</span><h2>${esc(d.headline)}</h2><p class="muted">${esc(d.guidance)}</p><div class="actions"><a class="button" href="#review">先完成 Anki 到期复习 →</a><a class="button secondary" href="#classroom">进入文字课堂</a><a class="button secondary" href="#lesson/${esc(d.lesson_id)}/basic_text">打开第 ${Number(d.lesson_id.slice(1))} 课</a></div><p class="meta" style="margin:16px 0 0">${d.mode==='coach_prepared'?'教练已准备':'按学习记录自动整理'} · 更新于 ${esc(new Date(d.generated_at).toLocaleString('zh-CN',{timeZone:'Asia/Hong_Kong'}))}（香港时间）<br>最近学习依据：${esc(d.last_learning_date||'暂无实际作答记录')}${d.source_session_id?` · <a class="text-link" href="#classroom/${esc(d.source_session_id)}">查看来源课堂</a>`:''}<br>准备安排不计作已上课；没有新学习记录时保留未完成内容。</p><p class="meta" data-preparation-status role="status"></p>`;
   }else{const status=root.querySelector('[data-preparation-status]');if(status)status.textContent='';}
  }catch(e){if(root.isConnected){const status=root.querySelector('[data-preparation-status]');if(status)status.textContent='暂未更新，以上为上次安排。';else root.innerHTML=`<h2>今日学习安排</h2><p class="notice">${esc(e.message||'暂时无法读取最新学习记录。')}</p><a class="text-link" href="#review">先完成 Anki 到期复习 →</a>`;}}
  finally{clearTimeout(timer);if(root.isConnected)timer=setTimeout(()=>document.hidden?refreshLater():refresh(),60000);}
 };
 const refreshLater=()=>{if(root.isConnected)timer=setTimeout(refresh,60000);else document.removeEventListener('visibilitychange',onVisible);};
 const onVisible=()=>{if(!document.hidden)refresh();};
 document.addEventListener('visibilitychange',onVisible);refresh();
}
