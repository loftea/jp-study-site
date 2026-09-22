import {escapeText as esc} from './annotated-text.js';
const labels={done:'已完成',in_progress:'进行中',pending:'待完成',unknown:'待核对',locked:'待上课',learning:'学习中',retest:'待复测',completed:'已完成',not_started:'尚未开始'};
const category={new:'新学',recovery:'恢复',consolidation:'巩固'};
async function read(url){const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(15000)});const d=await r.json();if(!r.ok)throw Error(d.error||'暂时无法读取');return d;}
function wordsHTML(w,full){
 const counts=Object.keys(category).map(k=>`${category[k]} ${w.items.filter(x=>x.category===k).length}`).join(' · ');
 return `<div class="section-heading"><h2>今日词单</h2>${full?'':'<a class="text-link" href="#words/daily">展开全部 →</a>'}</div><p>${esc(w.date)} · ${w.items.length} / ${w.target} 词项 · ${counts}</p><p class="meta">${esc(w.notice)}${w.missing?` 可用词不足预算 ${w.missing} 项，请在课堂确认；不会自动越课凑数。`:''}<br>新学表示卡片未学，不推断你从未学过；生成清单不计作完成。${w.captured_at?` 卡片状态核对于 ${esc(new Date(w.captured_at).toLocaleString('zh-CN',{timeZone:'Asia/Hong_Kong'}))}（香港时间）。`:''}</p><div class="daily-word-grid">${w.items.slice(0,full?30:6).map(x=>`<article class="daily-word"><span class="pill">${category[x.category]}</span><h3 lang="ja"><ruby>${esc(x.word)}<rt>${esc(x.reading)}</rt></ruby></h3><p>${esc(x.meaning)}</p>${x.binding_status==='verified'?`<button class="play" data-audio="/api/anki/audio?note_id=${x.note_id}" aria-label="播放${esc(x.word)}的 Anki 音频">▶</button>`:''}<p class="meta">第 ${x.lesson_number} 课 · ${x.binding_status!=='verified'?'卡片已移除或暂停':!w.fresh?'状态待同步':x.reviewed_today?'Anki 当日已复习':x.is_due?'Anki 到期':'按课堂安排学习'}</p>${full?`<details><summary class="meta">选择依据与卡片</summary><p class="meta">${esc(x.reason)}<br>笔记 ${x.note_id}<br>卡片 ${x.card_ids.join('、')}</p></details>`:''}</article>`).join('')}</div><div class="actions"><a class="button secondary" href="#review">打开 Anki 练习 →</a></div>`;
}
function tasksHTML(t){return `<div class="section-heading"><h2>今天的学习任务</h2><span class="meta">${esc(t.date)}</span></div><div class="task-grid">${t.steps.map((s,i)=>`<a class="task-item" href="${esc(s.href)}"><span class="pill ${s.status==='done'?'good':''}">${labels[s.status]}</span><h3>${i+1}. ${esc(s.title)}</h3><p class="meta">${esc(s.detail)}</p></a>`).join('')}</div><div class="actions">${t.next?`<a class="button" href="${esc(t.next.href)}">继续下一步：${esc(t.next.title)} →</a>`:'<span class="pill good">今天的任务已提交完成</span>'}</div><p class="meta">按真实复习队列、作答与课堂记录计算。提交完成不等于掌握；课堂与练习草稿会保留。</p>`;}
function progressHTML(p){const current=p.lessons.find(l=>l.lesson_id===p.current_lesson);return `<h2>还有什么待做</h2><p>当前第 ${current.number} 课 · <span class="pill">${labels[current.status]}</span></p><p>${esc(current.next_step||'继续当前课的教学与练习，逐步补齐真实学习证据。')}</p><p class="meta">尚需通过隔日复测：${current.pending_areas.join('、')||'本课已通过复测'}。结束一次课堂不等于完成一课。</p><div class="actions"><a class="button" href="${current.session_id?'#classroom/'+current.session_id:'#classroom'}">查看当前课堂 →</a><a class="button secondary" href="#today">继续今日任务 →</a></div><details class="details"><summary>查看 48 课进度与判定依据</summary><p class="meta">词汇、句型、阅读、听力、运用五项均需有练习证据，并在之后日期独立复测正确。教练判断引用真实作答。</p><div class="lesson-state-grid">${p.lessons.map(l=>`<a class="pill ${l.status==='completed'?'good':''}" href="#lesson/${l.lesson_id}/basic_text">${l.number} · ${labels[l.status]}</a>`).join('')}</div>${current.evidence.length?`<details><summary>当前课的证据</summary>${current.evidence.map(c=>`<p class="meta">${esc(c.answered_at)} · ${esc(c.area)} / ${esc(c.phase)} / ${esc(c.evaluation)}<br>“${esc(c.quote)}” <a href="#classroom/${esc(c.session_id)}">来源对话</a></p>`).join('')}</details>`:''}</details>`;}
export function mountWorkflow(root,mode='today'){
 let timer,revision='',busy=false;
 async function refresh(){
  if(!root.isConnected||busy)return;busy=true;
  try{const d=await read('/api/study-workflow');if(!root.isConnected)return;
   const w=JSON.parse(JSON.stringify(d));delete w.tasks.updated_at;delete w.progress.computed_at;
   // Card check timestamps don't change layout every polling cycle.
   delete w.words.captured_at;delete w.words.verified_at;w.words.items.forEach(x=>delete x.verified_at);
   const next=JSON.stringify(w);if(next!==revision){revision=next;root.innerHTML=mode==='words'?wordsHTML(d.words,true):mode==='progress'?progressHTML(d.progress):tasksHTML(d.tasks)+wordsHTML(d.words,false);}
   const counter=document.querySelector('#lesson-completed-count');if(counter)counter.textContent=d.progress.completed_count+' / 48';
   const status=root.querySelector('[data-workflow-error]');if(status)status.remove();
  }catch(e){if(root.isConnected&&!root.querySelector('[data-workflow-error]'))root.insertAdjacentHTML('beforeend',`<p class="notice" data-workflow-error>最新任务暂未更新：${esc(e.message)}。已保存的数据保留，恢复连接后自动重试。</p>`);}
  finally{busy=false;clearTimeout(timer);if(root.isConnected)timer=setTimeout(refresh,30000);}
 }
 root.innerHTML='<p class="meta">正在核对今天的词单与学习任务…</p>';refresh();
}
export function mountServiceStatus(root){
 let timer,previous='';
 async function refresh(){
  if(!root.isConnected)return;
  try{const s=await read('/api/system/status');if(!root.isConnected)return;const b=s.backup;
   const html=`<span class="pill good">服务在线</span> <span class="meta">${s.managed?'后台守护 · 服务退出后自动恢复':'手动运行'}</span><details><summary class="meta">运行与备份状态</summary><p class="meta">${b.last_success?'最近备份：'+esc(new Date(b.last_success).toLocaleString('zh-CN')):'尚无成功备份'}${b.error?'<br>备份异常：'+esc(b.error):''}<br>守护进程运行期间自动恢复服务；重新登录后请启动学习网站。每日备份学习记录和课堂；Anki 数据由 Anki 自身管理。备份保存在本机，不能防止整块硬盘损坏。</p></details>`;
   if(html!==previous){root.innerHTML=html;previous=html;}
  }catch{previous='';if(root.isConnected)root.innerHTML='<span class="pill warn">网站服务暂时离线</span><p class="meta">正在重试连接。后台托管会尝试恢复；若持续离线，请让教练检查服务。不要重复提交。</p>';}
  finally{clearTimeout(timer);if(root.isConnected)timer=setTimeout(refresh,20000);}
 }refresh();
}

export async function mountLessonStatus(root,id){
 try{const p=await read('/api/lesson-progress');if(!root.isConnected)return;const l=p.lessons.find(x=>x.lesson_id===id);root.textContent=labels[l.status];root.classList.toggle('good',l.status==='completed');}catch{if(root.isConnected)root.textContent='进度暂未读取';}
}
