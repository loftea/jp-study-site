export async function mountReviewCalendar(root,{esc}){
 const localDay=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Hong_Kong',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 let selected=localDay,month=localDay.slice(0,7),data=null,timer,revision='';
 const dayKey=n=>`${month}-${String(n).padStart(2,'0')}`;
 const shift=amount=>{const [y,m]=month.split('-').map(Number);const d=new Date(Date.UTC(y,m-1+amount,1));month=d.toISOString().slice(0,7);selected=month===(data?.today||localDay).slice(0,7)?data?.today||localDay:month+'-01';render();};
 function render(){
  if(!root.isConnected)return;
  const today=data?.today||localDay,[year,mon]=month.split('-').map(Number),count=new Date(Date.UTC(year,mon,0)).getUTCDate(),offset=(new Date(Date.UTC(year,mon-1,1)).getUTCDay()+6)%7;
  const entries=Object.entries(data?.days||{}).filter(([date])=>date.startsWith(month)&&date<=today);
  const days=entries.filter(([,d])=>d.reviews>0).length,total=entries.reduce((sum,[,d])=>sum+d.reviews,0);
  const actual=data?.has_snapshot,d=data?.days?.[selected],future=selected>today;
  root.innerHTML=`<div class="section-heading" style="margin-top:0"><h2>背单词日历</h2><a class="text-link" href="#review">去复习 →</a></div><div class="calendar-nav"><button class="calendar-arrow" id="calendar-prev" aria-label="上个月">‹</button><strong>${year} 年 ${mon} 月</strong><button class="calendar-arrow" id="calendar-next" aria-label="下个月" ${month>=today.slice(0,7)?'disabled':''}>›</button></div><div class="calendar-week" aria-hidden="true">${['一','二','三','四','五','六','日'].map(x=>`<span>${x}</span>`).join('')}</div><div class="calendar-days">${'<span></span>'.repeat(offset)}${Array.from({length:count},(_,i)=>{const key=dayKey(i+1),item=data?.days?.[key],n=item?.cards||0,level=n>=40?4:n>=20?3:n>=10?2:n>0?1:0;const label=key>today?'未到日期':!actual?'数据未同步':n?`复习 ${n} 张卡片，${item.reviews} 次作答`:'无复习记录';return `<button class="calendar-day level-${level} ${selected===key?'selected':''} ${key===today?'today':''}" data-day="${key}" ${key>today?'disabled':''} aria-label="${key}，${label}" aria-pressed="${selected===key}"><span>${i+1}</span><small>${key>today?'':!actual?'—':n||'·'}</small></button>`;}).join('')}</div><div class="calendar-legend"><span>少</span>${[0,1,2,3,4].map(n=>`<i class="level-${n}"></i>`).join('')}<span>多 · 按复习卡片数</span></div><p class="calendar-month-total">${actual?`本月学习 <strong>${days}</strong> 天 · 作答 <strong>${total}</strong> 次`:'正在等待 Anki 复习记录'}</p><div class="calendar-detail" aria-live="polite"><strong>${esc(selected)}${selected===today?' · 今天':''}</strong><p>${future?'尚未到这一天。':!actual?'打开本机 Anki 后自动读取。':d?`复习 <b>${d.cards}</b> 张不同卡片 · 作答 <b>${d.reviews}</b> 次<br>答题计时 ${d.seconds<60?d.seconds+' 秒':(d.seconds/60).toFixed(1)+' 分钟'}`:'这一天暂无复习记录。'}</p></div><p class="meta calendar-sync">${data?.connected?'已同步 Anki':actual?'Anki 未连接 · 显示上次同步':'Anki 暂未连接'}${data?.captured_at?' · '+esc(new Date(data.captured_at).toLocaleString('zh-CN',{timeZone:'Asia/Hong_Kong'})):''}</p><p class="meta">按香港时间自然日统计当前 JP 牌组及子牌组。卡片数不是新增词数；答题计时不等于完整学习时长。</p><p class="meta">每日词项预算含恢复与巩固，计划量与实际掌握量分开；目标按个人学习情况调整。</p>`;
  root.querySelector('#calendar-prev').onclick=()=>shift(-1);root.querySelector('#calendar-next').onclick=()=>shift(1);
  root.querySelectorAll('[data-day]').forEach(b=>b.onclick=()=>{selected=b.dataset.day;render();});
 }
 async function refresh(){
  if(!root.isConnected)return;
  try{const r=await fetch('/api/anki/calendar',{cache:'no-store'});if(!r.ok)throw Error();const next=await r.json();const rev=JSON.stringify(next);data=next;if(rev!==revision){revision=rev;render();}}
  catch{data={...(data||{}),connected:false};render();}
  if(root.isConnected)timer=setTimeout(refresh,30000);
 }
 render();await refresh();
}
