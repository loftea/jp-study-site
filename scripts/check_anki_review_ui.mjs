// Isolated UI polling regression. No browser, network, or real Anki reviews.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
let mutations=0,requests=[],timers=[],buttons=[];
class Node {
 constructor(){this.text='';this.html='';this.off=false;this.dataset={};this.isConnected=true;}
 get textContent(){return this.text} set textContent(v){mutations++;this.text=v}
 get innerHTML(){return this.html} set innerHTML(v){mutations++;this.html=v;
  if(this===nodes['#review-actions'])buttons=[...v.matchAll(/data-review="([^"]+)"(?: data-rating="([^"]+)")?/g)].map(m=>{const n=new Node();n.dataset={review:m[1],rating:m[2]};return n;});
  if(v.includes('<iframe'))this.firstElementChild={srcdoc:''};
 }
 get disabled(){return this.off} set disabled(v){mutations++;this.off=v}
 closest(){return this}
}
const nodes=Object.fromEntries(['#review-message','#native-card','#review-actions','#review-deck','#review-refresh'].map(id=>[id,new Node()]));
const host=new Node();host.querySelector=id=>nodes[id];host.querySelectorAll=()=>buttons;
const storage=new Map();
const context=vm.createContext({console,AbortSignal,crypto:{randomUUID:()=>`fake-${requests.length}`},
 sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 document:{hidden:false,addEventListener(){}},window:{addEventListener(){}},setInterval:fn=>timers.push(fn),
 fetch:(_url,opts)=>new Promise((resolve,reject)=>requests.push({body:JSON.parse(opts.body),resolve,reject}))});
const source=readFileSync(new URL('../website/dist/anki-review.js',import.meta.url),'utf8');
const module=new vm.SourceTextModule(source,{context});await module.link(()=>{});await module.evaluate();
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const question={state:'question',deck:'JP',card_id:1,token:'one',document:'question'};
const answer={...question,state:'answer',document:'answer',buttons:[1,2,3,4],intervals:['1m','1d','2d','3d']};
async function reply(data,ok=true){requests.at(-1).resolve({ok,json:async()=>structuredClone(data)});await settle();}
module.namespace.mountAnkiReview(host,()=>{});await reply(question);
// Normal polling must not alter DOM or disable controls, even with a slow reply.
const initial=mutations,frame=nodes['#native-card'].firstElementChild;
for(let i=0;i<4;i++){timers[0]();assert.equal(buttons[0].disabled,false);await reply(question);}
assert.equal(mutations,initial,'Unchanged polls caused visual DOM mutations');assert.equal(nodes['#native-card'].firstElementChild,frame);
// Clicking during a pending read is queued exactly once and locks only the action.
timers[0]();const count=requests.length;host.onclick({target:buttons[0]});assert.equal(buttons[0].disabled,true);
host.onclick({target:buttons[0]});assert.equal(requests.length,count);
await reply(question);assert.equal(requests.at(-1).body.operation,'reveal');await reply(answer);assert.equal(buttons.length,4);assert(buttons.every(b=>!b.disabled));
const stable=mutations;timers[0]();await reply(answer);assert.equal(mutations,stable);
// Offline status retains card & controls; it disables once, then restores on recovery.
const answerFrame=nodes['#native-card'].firstElementChild;timers[0]();requests.at(-1).reject(Error('offline'));await settle();
assert.equal(buttons.length,4);assert(buttons.every(b=>b.disabled));assert.equal(nodes['#native-card'].firstElementChild,answerFrame);
const failed=mutations;timers[0]();requests.at(-1).reject(Error('offline'));await settle();assert.equal(mutations,failed);
timers[0]();await reply(answer);assert(buttons.every(b=>!b.disabled));
// Grade triggered during a read still uses one request; pending receipt is polled, not retried.
timers[0]();host.onclick({target:buttons[2]});await reply(answer);
assert.equal(requests.at(-1).body.operation,'grade');assert.equal(requests.at(-1).body.rating,3);
await reply({current:{state:'saving'},receipt:{status:'pending'}});assert.equal(buttons.length,0);
timers[0]();assert(requests.at(-1).body.request_id);await reply({receipt:{status:'saved'},current:{...question,card_id:2,token:'two',document:'next'}});
assert.equal(requests.filter(r=>r.body.operation==='grade').length,1);assert.equal(storage.size,0);assert.equal(buttons[0].disabled,false);
// Finished screen is stable too.
timers[0]();await reply({state:'finished',message:'Done'});const done=mutations;timers[0]();await reply({state:'finished',message:'Done'});assert.equal(mutations,done);
console.log('PASS: silent polling, stable card/audio DOM, clicks during reads, duplicate-click lock, offline recovery, pending receipts, next card and finished state. All ratings simulated.');
