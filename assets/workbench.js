'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const LIB = window.RADAR_LIBRARY;
const labels = {keep:'保留',rewrite:'建议改写',merge:'建议合并',compress:'建议压缩',drop:'建议删除',needs_input:'待补充事实',direct:'有直接依据',transferable:'可迁移',partial:'部分支持',unknown:'尚不能判断',missing:'已确认缺口',conflicting:'材料冲突',met:'基本达标',unmet:'不符合'};
const units = new Map(DATA.resume.units.map(x => [x.id,x]));
const diagnoses = new Map(DATA.diagnoses.map(x => [x.id,x]));
const evidence = new Map(DATA.evidence.map(x => [x.id,x]));
const reviews = [...DATA.reviews].sort((a,b) => Math.min(...a.unit_ids.map(id=>units.get(id).start))-Math.min(...b.unit_ids.map(id=>units.get(id).start)));
const reviewMap = new Map(reviews.map(x => [x.id,x]));
const numbers = new Map(reviews.map((x,i)=>[x.id,i+1]));
const plan=DATA.confirmation?.outputs||DATA.confirmation?.stage2;
const titles = {optimized:'优化后的简历',overview:'整体判断',modules:'模块诊断',reviews:'逐句审阅',questions:'待补充事实',requirements:'岗位要求对照',jobs:'岗位推荐',library:'产品简历库'};
let currentView='overview', activeReview='', filter='all', zoom=1, activeCase=null, caseTab='work';
let moduleFilter='*', selectedJob='', jobTier='all';
const availableJobs=()=> (DATA.run.job_matches||[]).filter(m=>DATA.sources.some(s=>s.id===m.source_id&&s.metadata&&s.metadata.availability!=='closed'));
const jobNumber=m=>String(availableJobs().findIndex(x=>x.source_id===m.source_id)+1).padStart(2,'0');
const itemNumber=(prefix,index)=>prefix+String(index+1).padStart(2,'0')+' · ';
const moduleOf=review=>units.get(review.unit_ids[0])?.section||'基本信息';
const moduleNames=[...new Set(reviews.map(moduleOf))];
const moduleReviews=()=>moduleFilter==='*'?reviews:reviews.filter(r=>moduleOf(r)===moduleFilter);
let libraryQuery='', libraryRole='', libraryPage=0, toastTimer;
const storageKey='resume-radar:'+DATA.documentHash+':'+(DATA.run.target||'');
let states={};
try { states=JSON.parse(localStorage.getItem(storageKey)||'{}'); } catch { states={}; }
if(!states || typeof states!=='object' || Array.isArray(states)) states={};
const signature=r=>JSON.stringify([r.text,r.reason,r.question,r.decision]);
const stateOf=r=>states[r.id]?.signature===signature(r)?states[r.id].value:'pending';
function node(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
function paragraph(parent,text,cls=''){if(text)parent.append(node('p',cls,text));}
function heading(parent,title){parent.append(node('h4','',title));}
function button(text,handler,cls=''){const b=node('button',cls,text);b.type='button';b.addEventListener('click',handler);return b;}
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,3200);}
async function copyText(text){try{await navigator.clipboard.writeText(text);toast('已复制');}catch{const area=node('textarea');area.value=text;document.body.append(area);area.select();const ok=document.execCommand('copy');area.remove();toast(ok?'已复制':'复制失败，请选中文字后复制');}}
function rectangles(review){return review.unit_ids.flatMap(id=>DATA.locations[id]?.rects||[]);}
function originalText(review){return review.unit_ids.map(id=>units.get(id)?.text||'').join('\n');}
function shortTitle(review){const text=review.capability||review.reason||originalText(review);return text.length>58?text.slice(0,58)+'…':text;}
function addNotice(parent,text){paragraph(parent,text,'notice');}
function sectionLabel(parent,title,description){const h=node('div','section-label');h.append(node('h3','',title));if(description)h.append(node('small','',description));parent.append(h);}
function renderModuleNav(){
 const host=$('#module-nav');host.hidden=!['modules','reviews','jobs'].includes(currentView);host.replaceChildren();if(host.hidden)return;
 if(currentView==='jobs'){host.setAttribute('aria-label','按推荐难度筛选');for(const [value,label] of [['all','全部'],['priority','优先尝试'],['stretch','需要补强'],['verify','先核实条件']]){const count=availableJobs().filter(m=>value==='all'||m.tier===value).length;const b=button(label+' '+count,()=>{jobTier=value;renderModuleNav();renderContent();$('#analysis-content').scrollTop=0;});b.setAttribute('aria-pressed',String(jobTier===value));host.append(b);}return;}host.setAttribute('aria-label','选择简历模块');
 for(const [value,label] of [['*','全部'],...moduleNames.map(name=>[name,name])]){
  const b=button(label,()=>{moduleFilter=value;for(const item of host.querySelectorAll('button'))item.setAttribute('aria-pressed',String(item.dataset.module===value));renderContent();$('#analysis-content').scrollTop=0;const first=moduleReviews()[0];if(value!=='*'&&first)highlightReview(first.id,true);});
  b.dataset.module=value;b.setAttribute('aria-pressed',String(value===moduleFilter));host.append(b);
 }
}
function showView(view){currentView=view;for(const b of $$('[data-view]')){if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}$('#view-title').textContent=titles[view];$('#view-eyebrow').textContent=view==='library'?'固定内容库':'本次评估';renderModuleNav();renderContent();$('#analysis-content').scrollTop=0;}
function highlightReview(id,scroll=true){
 activeReview=id;
 for(const marker of $$('.pdf-marker')){marker.classList.toggle('selected',marker.dataset.review===id);marker.hidden=marker.dataset.keep==='true'&&!$('#show-kept').checked&&marker.dataset.review!==id;}
 for(const frame of $$('.pdf-page'))layoutPagePins(frame);
 for(const card of $$('.review-card'))card.classList.toggle('selected',card.dataset.review===id);
 const markers=$$('.pdf-marker').filter(b=>b.dataset.review===id);
 if(scroll&&markers.length)markers[0].scrollIntoView({block:'center',inline:'nearest',behavior:'smooth'});
 return markers.length>0;
}
function selectReview(id,fromPdf=false){
 if(!reviewMap.has(id))return;
 if(moduleFilter!=='*'&&moduleOf(reviewMap.get(id))!==moduleFilter)moduleFilter=moduleOf(reviewMap.get(id));
 activeReview=id;filter='all';showView('reviews');highlightReview(id,!fromPdf);
 const card=document.getElementById('review-'+id);
 if(card){card.open=true;requestAnimationFrame(()=>card.scrollIntoView({block:'nearest',behavior:'smooth'}));}
}
function renderPdf(){
 const host=$('#pdf-pages');
 for(const page of DATA.pages){
  const frame=node('div','pdf-page');frame.id='pdf-page-'+page.number;frame.style.aspectRatio=page.width+'/'+page.height;
  const img=node('img');img.src=page.image;img.alt='简历原件，第 '+page.number+' 页';img.width=Math.round(page.width*1.8);img.height=Math.round(page.height*1.8);img.decoding='async';if(page.number>2)img.loading='lazy';frame.append(img);
  for(const review of reviews){const rects=rectangles(review);rects.forEach((box,index)=>{
   if(box.page!==page.number)return;
   const [x0,y0,x1,y1]=box.rect;
   const marker=button('',()=>selectReview(review.id,true),'pdf-marker');marker.dataset.review=review.id;marker.dataset.keep=String(review.decision==='keep');marker.hidden=review.decision==='keep';
   marker.style.left=(x0*100)+'%';marker.style.top=(y0*100)+'%';marker.style.width=((x1-x0)*100)+'%';marker.style.height=((y1-y0)*100)+'%';
   marker.title='#'+numbers.get(review.id)+' '+(labels[review.decision]||review.decision)+'：'+shortTitle(review);
   marker.setAttribute('aria-label',marker.title);frame.append(marker);
  });}
  frame.annotationItems=reviews.flatMap(review=>{const boxes=rectangles(review).filter(b=>b.page===page.number);return boxes.length?[{review,y:Math.min(...boxes.map(b=>b.rect[1]))}]:[];});
  frame.append(node('span','page-number',page.number+' / '+DATA.pages.length));host.append(frame);
 }
 const observer=new ResizeObserver(entries=>{for(const entry of entries)layoutPagePins(entry.target);});
 for(const frame of $$('.pdf-page'))observer.observe(frame);
 const mapped=DATA.resume.units.filter(u=>DATA.locations[u.id]?.status==='matched').length;
 $('#mapping-summary').textContent=mapped===DATA.resume.units.length?'原文位置已全部关联':(DATA.resume.units.length-mapped)+' 处原文位置待核对';
}
function layoutPagePins(frame){
 const items=frame.annotationItems.filter(item=>item.review.decision!=='keep'||$('#show-kept').checked||item.review.id===activeReview).sort((a,b)=>a.y-b.y);
 const height=frame.getBoundingClientRect().height;if(height<=0)return;
 const signature=items.map(i=>i.review.id).join('|')+':'+Math.round(height);
 if(frame.pinSignature===signature){for(const pin of frame.querySelectorAll('.pdf-pin'))pin.classList.toggle('selected',pin.reviewIds.includes(activeReview));return;}
 frame.pinSignature=signature;
 for(const pin of frame.querySelectorAll('.pdf-pin,.pin-options'))pin.remove();
 const groups=items.map(item=>[item]);
 const gap=22,capacity=Math.max(1,Math.floor((height-2)/gap));
 // At small PDF sizes, combine the nearest anchors into an explicit choice menu.
 while(groups.length>capacity){let closest=0,distance=Infinity;for(let i=0;i<groups.length-1;i++){const d=groups[i+1][0].y-groups[i].at(-1).y;if(d<distance){distance=d;closest=i;}}groups.splice(closest,2,[...groups[closest],...groups[closest+1]]);}
 const maxTop=Math.max(0,height-20);
 const tops=groups.map(group=>Math.max(0,Math.min(maxTop,group[0].y*height-2)));
 for(let i=1;i<tops.length;i++)tops[i]=Math.max(tops[i],tops[i-1]+gap);
 for(let i=tops.length-1;i>=0;i--)tops[i]=Math.min(tops[i],i===tops.length-1?maxTop:tops[i+1]-gap);
 groups.forEach((group,index)=>{
  const first=group[0].review,ids=group.map(item=>item.review.id);
  const pin=button('',()=>group.length===1?selectReview(first.id,true):openPinChoices(frame,pin,group),'pdf-pin');
  pin.reviewIds=ids;pin.dataset.review=first.id;pin.dataset.keep=String(group.every(item=>item.review.decision==='keep'));pin.style.top=tops[index]+'px';pin.classList.toggle('selected',ids.includes(activeReview));
  const label='#'+numbers.get(first.id)+(group.length>1?' 附近'+group.length+'处建议，展开选择':' '+shortTitle(first));
  pin.title=label;pin.setAttribute('aria-label',label);if(group.length>1){pin.setAttribute('aria-haspopup','true');pin.setAttribute('aria-expanded','false');}
  pin.append(node('span','marker-number',numbers.get(first.id)+(group.length>1?'+':'')));frame.append(pin);
 });
}
function closePinChoices(restore=false){for(const panel of $$('.pin-options')){const trigger=panel.pinTrigger;panel.remove();trigger?.setAttribute('aria-expanded','false');if(restore&&trigger?.isConnected)trigger.focus();}}
function openPinChoices(frame,trigger,group){
 const wasOpen=trigger.getAttribute('aria-expanded')==='true';closePinChoices();if(wasOpen)return;
 const panel=node('div','pin-options');panel.setAttribute('role','group');panel.setAttribute('aria-label','选择附近的审阅位置');panel.pinTrigger=trigger;
 panel.style.top=Math.max(0,Math.min(parseFloat(trigger.style.top),frame.clientHeight-150))+'px';
 for(const item of group)panel.append(button('#'+numbers.get(item.review.id)+' '+shortTitle(item.review),()=>{closePinChoices(true);selectReview(item.review.id,true);}));
 panel.append(button('关闭位置选择',()=>closePinChoices(true)));frame.append(panel);trigger.setAttribute('aria-expanded','true');panel.querySelector('button').focus();
}
document.addEventListener('pointerdown',event=>{if(!event.target.closest('.pdf-pin,.pin-options'))closePinChoices();});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&$('.pin-options')){event.preventDefault();closePinChoices(true);}});
function locateButton(review){
 const boxes=rectangles(review), allMatched=review.unit_ids.every(id=>DATA.locations[id]?.status==='matched');
 const b=button(boxes.length?'定位原文 · 第 '+[...new Set(boxes.map(b=>b.page))].join('、')+' 页':'原文位置待核对',()=>{if(!highlightReview(review.id))toast('这条原文未能可靠定位，请对照下方原文核查。');},'locate-button');
 if(!allMatched)b.title='部分原文位置待核对';
 return b;
}
function exampleLinks(parent,review){
 const links=DATA.links.filter(x=>x.review_id===review.id);
 if(links.length){heading(parent,'对应经历示例');for(const link of links){const example=LIB.cases[link.case_id];const b=button(example.dutyName+' ↗',()=>openCase(link.case_id),'case-link');b.append(node('small','',link.reason));parent.append(b);paragraph(parent,'适用条件：'+link.conditions,'source-basis');}}
 else if(DATA.libraryApplicable && ['rewrite','merge','needs_input','compress'].includes(review.decision)){
  paragraph(parent,'未关联到经过核对的适用案例。可浏览固定库，按实际职责选择参考。','source-basis');
  parent.append(button('查阅固定示例库',()=>showView('library'),'case-link'));
 }
}
function reviewCard(review){
 const card=node('details','review-card'+(activeReview===review.id?' selected':''));card.id='review-'+review.id;card.dataset.review=review.id;
 card.open=activeReview===review.id;
 const summary=node('summary');summary.append(node('span','review-number',String(numbers.get(review.id)).padStart(2,'0')));
 const title=node('span','review-title');title.append(node('strong','',shortTitle(review)));title.append(node('span','status-tag '+review.decision,labels[review.decision]||review.decision));if(stateOf(review)!=='pending')title.append(node('small','',stateOf(review)==='done'?'  已处理':'  已忽略'));summary.append(title);
 summary.addEventListener('click',()=>highlightReview(review.id,true));card.append(summary);
 const body=node('div','review-body');body.append(locateButton(review));
 if(!review.unit_ids.every(id=>DATA.locations[id]?.status==='matched'))addNotice(body,'部分原文未能唯一定位。请以这里保留的原句与 PDF 原件核对。');
 if(!review.unit_ids.every(id=>DATA.locations[id]?.status==='matched')){heading(body,'待核对原句');paragraph(body,originalText(review),'quote-box');}
 heading(body,review.decision==='needs_input'?'基于已知事实的保守表达':'修改后');
 const changed=review.text||(review.decision==='keep'?'保留原句，见左侧高亮。':'暂无可确认的改写，相关未知见待补充事实。');paragraph(body,changed,'rewrite-box');
 if(review.text)body.append(button('复制修改后文字',()=>copyText(review.text)));
 heading(body,'原因与建议');paragraph(body,review.reason);
 if(review.question){heading(body,'需要你补充');paragraph(body,review.question);}
 exampleLinks(body,review);
 const actions=node('div','status-actions');actions.append(button(stateOf(review)==='done'?'恢复待处理':'标记已处理',()=>setState(review,stateOf(review)==='done'?'pending':'done')),button(stateOf(review)==='ignored'?'恢复待处理':'忽略此项',()=>setState(review,stateOf(review)==='ignored'?'pending':'ignored')));body.append(actions);
 paragraph(body,'处理标记只保存在当前浏览器，不会修改 PDF 或自动更新诊断。','storage-note');
 card.append(body);return card;
}
function setState(review,value){states[review.id]={value,signature:signature(review)};let saved=true;try{localStorage.setItem(storageKey,JSON.stringify(states));}catch{saved=false;}renderContent();toast(saved?'处理状态已保存':'当前浏览器无法保存，标记仅在本次页面中有效');}
function reviewList(parent,items,withFilters=true){
 if(withFilters){const bar=node('div','filter-bar');for(const [key,text]of [['all','全部'],['issues','待优化'],['needs_input','待补充'],['done','已处理'],['ignored','已忽略']])bar.append(button(text,()=>{filter=key;renderContent();},filter===key?'active':''));parent.append(bar);}
 let chosen=items.filter(r=>filter==='all'||(filter==='issues'&&r.decision!=='keep'&&stateOf(r)==='pending')||(filter==='needs_input'&&(r.decision==='needs_input'||r.question))||stateOf(r)===filter);
 if(!withFilters)chosen=items;
 if(!chosen.length)parent.append(node('p','empty-state','当前没有这类事项。'));
 for(const review of chosen)parent.append(reviewCard(review));
}
function renderOverview(parent){
 const overview=DATA.run.report_overview||{};
 paragraph(parent,overview.headline||'本次简历判断','lead');
 const block=node('div','summary-block');paragraph(block,overview.introduction||DATA.run.summary);parent.append(block);
 for(const [index,item] of (overview.assessment||[]).entries()){const row=node('div','assessment-row');const name=node('strong','',itemNumber('A',index)+item.dimension);name.append(node('span','status-tag',labels[item.status]||item.status));row.append(name);paragraph(row,item.judgment);parent.append(row);}
 if(overview.fit_scope)paragraph(parent,overview.fit_scope,'source-basis');
 if(overview.eligibility)paragraph(parent,overview.eligibility,'source-basis');
 if(DATA.run.target&&DATA.run.mode!=='general')renderJobMatches(parent,true);
 sectionLabel(parent,'优先处理',DATA.diagnoses.length+' 项诊断');
 const priority=overview.priorities?.length?overview.priorities:DATA.diagnoses.filter(d=>d.priority==='high').slice(0,3).map(d=>({title:d.does_not_demonstrate,text:d.next_action,diagnosis_ids:[d.id]}));
 if(!priority.length)paragraph(parent,'没有标为高优先级的问题。可进入逐句审阅查看所有处理项。');
 for(const [index,item] of priority.entries()){const related=reviews.find(r=>r.diagnosis_ids.some(id=>item.diagnosis_ids?.includes(id)));const entry=button('',()=>related?selectReview(related.id):showView('modules'),'priority-item');entry.append(node('span','priority-number',index+1));const copy=node('span');copy.append(node('strong','',item.title));paragraph(copy,item.text);entry.append(copy);parent.append(entry);}
 if(DATA.run.role_options?.length){sectionLabel(parent,'方向建议');for(const option of DATA.run.role_options){const block=node('div','direction-link');block.append(node('strong','',option.role));paragraph(block,option.rationale);const ids=option.recommended_jd_source_ids||option.jd_source_ids||[];for(const id of ids.slice(0,2)){const source=DATA.sources.find(s=>s.id===id);const meta=source?.metadata;if(!meta||meta.availability==='closed')continue;try{const url=new URL(meta.url);if(!['http:','https:'].includes(url.protocol))continue;const a=node('a','',meta.title+' · '+meta.company+(meta.availability==='unknown'?'（状态未核实）':''));a.href=url.href;a.target='_blank';a.rel='noopener';block.append(a);}catch{}}
 parent.append(block);}}
 if(DATA.run.market_search?.limitations)addNotice(parent,DATA.run.market_search.limitations);
 sectionLabel(parent,'开始对照');paragraph(parent,'点击简历中的编号，查看同一位置的诊断、修改建议和经历参考。','highlight-intro');parent.append(button('查看全部逐句审阅',()=>showView('reviews'),'primary-button'));
}
function renderModules(parent){
 const groups=new Map(),shownDiagnoses=new Set();for(const r of moduleReviews()){const section=moduleOf(r);if(!groups.has(section))groups.set(section,[]);groups.get(section).push(r);}
 for(const [section,items] of groups){const group=node('section','module-group');group.append(node('h3','',section+' · '+items.filter(r=>r.decision!=='keep').length+' 处建议'));
  for(const id of new Set(items.flatMap(r=>r.diagnosis_ids))){if(shownDiagnoses.has(id))continue;shownDiagnoses.add(id);const d=diagnoses.get(id);if(!d)continue;const block=node('section','requirement-card');block.append(node('h3','',itemNumber('D',DATA.diagnoses.indexOf(d))+(d.title||d.does_not_demonstrate)));paragraph(block,d.demonstrates);paragraph(block,d.impact);paragraph(block,d.next_action);const related=items.filter(r=>r.diagnosis_ids.includes(id));for(const r of related)block.append(button('对照原文 #'+numbers.get(r.id),()=>selectReview(r.id),'locate-button'));group.append(block);}
  if(!items.some(r=>r.diagnosis_ids.length))paragraph(group,'本模块没有单独的结构或证据诊断；文字调整见逐句审阅。'); group.append(button('查看本模块逐句审阅',()=>{moduleFilter=section;showView('reviews');}));parent.append(group);}
}
function questionItems(){
 const items=[],seen=new Set();
 function add(title,text,related){if(!text||seen.has(text))return;seen.add(text);items.push({title,text,related});}
 for(const r of reviews)if(r.question||r.decision==='needs_input')add(shortTitle(r),r.question||r.reason,[r]);
 for(const d of DATA.diagnoses)if(d.gap_type==='evidence_missing'||d.question)add(d.title||d.does_not_demonstrate,d.question||d.next_action,reviews.filter(r=>r.diagnosis_ids.includes(d.id)));
 for(const e of DATA.evidence)if(['unclear','conflicting'].includes(e.status))add('证据待核对',e.action+'：现有材料尚不足以确认，请补充责任范围、阶段或依据。',reviews.filter(r=>r.evidence_ids.includes(e.id)));
 return items;
}
function renderQuestions(parent){
 const items=questionItems();
 for(const [index,item] of items.entries()){const card=node('section','requirement-card');card.append(node('h3','',itemNumber('F',index)+item.title));paragraph(card,item.text);for(const r of item.related)card.append(button('查看逐句项 #'+numbers.get(r.id),()=>selectReview(r.id)));parent.append(card);}
 if(!items.length)paragraph(parent,'本次已检查逐句审阅、诊断中的事实缺项及不明确或冲突的证据，未记录需要额外补充的事实。这仅表示现有材料足以支持本次保守表述，不代表经历已获外部核实；如发现遗漏，可回到 Codex 补充并更新分析。','empty-state');
}
function jobLink(parent,source){
 try{const url=new URL(source.metadata.url);if(!['http:','https:'].includes(url.protocol))return;const a=node('a','job-source primary-button','查看真实岗位 ↗');a.href=url.href;a.target='_blank';a.rel='noopener';parent.append(a);}catch{}
}
function showJobDetails(id){selectedJob=id;showView('requirements');}
function renderJobMatches(parent,compact=false){
 const rank={priority:0,stretch:1,verify:2};
 const matches=compact?[...availableJobs()].sort((a,b)=>rank[a.tier]-rank[b.tier]).slice(0,3):(DATA.run.job_matches||[]);
 if(compact)sectionLabel(parent,'真实岗位匹配','基于已读取的岗位与本份简历');
 else paragraph(parent,'难度表示当前简历与岗位任务的差距，不是录用概率。岗位状态以记录读取时为准，投递前请复核。','highlight-intro');
 const tiers=[['priority','优先尝试'],['stretch','需要补强'],['verify','先核实条件']];
 let total=0;
 for(const [tier,label] of tiers){const items=matches.filter(m=>m.tier===tier).filter(m=>DATA.sources.find(s=>s.id===m.source_id)?.metadata?.availability!=='closed');if(!items.length||(!compact&&jobTier!=='all'&&tier!==jobTier))continue;if(!compact)sectionLabel(parent,label+' · '+items.length+' 岗位');
 for(const m of items){const source=DATA.sources.find(s=>s.id===m.source_id);if(!source?.metadata)continue;total++;const meta=source.metadata,card=node('section','job-match');card.append(node('h3','',itemNumber('J',Number(jobNumber(m))-1)+meta.company+' · '+meta.title));paragraph(card,label+' · '+meta.location+' · '+(meta.availability==='open'?'页面可投递，名额待复核':'状态或条件待核实'),'source-basis');paragraph(card,m.judgment);if(!compact){heading(card,'已有支持');paragraph(card,m.strengths);heading(card,'主要差距与准备');paragraph(card,m.gaps);paragraph(card,'读取日期：'+meta.retrieved_at,'source-basis');}card.append(button('查看岗位要求与匹配详情',()=>showJobDetails(m.source_id),'locate-button'));if(!compact)jobLink(card,source);parent.append(card);}}
 if(!total)paragraph(parent,availableJobs().length?'当前筛选下没有岗位，可切换其他难度。':'尚无经过逐岗评估的可推荐岗位。已读取的岗位可在岗位要求中查看；不会仅凭职位名称自动分配难度。','empty-state');
 const closed=matches.filter(m=>DATA.sources.find(s=>s.id===m.source_id)?.metadata?.availability==='closed');if(!compact&&closed.length)paragraph(parent,'已排除 '+closed.length+' 个下线岗位，不列入投递推荐。','source-basis');
 if(compact)parent.append(button('查看全部 '+availableJobs().length+' 个推荐岗位',()=>showView('jobs')));
}
function renderRequirements(parent){
 const choices=DATA.sources.filter(s=>['jd','jd_sample'].includes(s.kind));
 if(choices.length){const select=node('select','job-select');select.setAttribute('aria-label','选择岗位要求');const all=node('option','','全部岗位要求');all.value='';select.append(all);for(const source of choices){const o=node('option','',(source.metadata?.company||'用户提供')+' · '+(source.metadata?.title||source.id));o.value=source.id;select.append(o);}select.value=selectedJob;select.addEventListener('change',()=>{selectedJob=select.value;renderContent();});parent.append(select);}
 if(selectedJob){const source=choices.find(s=>s.id===selectedJob),match=(DATA.run.job_matches||[]).find(m=>m.source_id===selectedJob);if(source){heading(parent,source.metadata?.title||'岗位详情');if(match){paragraph(parent,match.judgment);heading(parent,'已有支持');paragraph(parent,match.strengths);heading(parent,'主要差距');paragraph(parent,match.gaps);}paragraph(parent,'来源摘录（仅保留与本次诊断相关的要求）','source-basis');paragraph(parent,source.text);if(source.metadata)jobLink(parent,source);}}

 paragraph(parent,'岗位要求以本次 JD 或已声明的方向依据为准；示例库不作为招聘门槛。','highlight-intro');
 for(const req of DATA.requirements){if(selectedJob){const match=(DATA.run.job_matches||[]).find(m=>m.source_id===selectedJob);const belongs=req.source_unit_ids?.some(id=>DATA.sources.find(s=>s.id===selectedJob)?.units.some(u=>u.id===id));if(!belongs&&!match?.requirement_ids?.includes(req.id))continue;}const card=node('section','requirement-card');const h=node('h3','',itemNumber('R',DATA.requirements.indexOf(req))+req.description);h.append(node('span','status-tag',labels[req.support]||req.support));card.append(h);paragraph(card,req.responsibility);paragraph(card,req.decision_depth);
 const linked=[...new Set((req.evidence_ids||[]).map(id=>evidence.get(id)?.unit_id).filter(Boolean))];
 for(const uid of linked){const review=reviews.find(r=>r.unit_ids.includes(uid));if(review)card.append(button('对照原文 #'+numbers.get(review.id),()=>selectReview(review.id),'locate-button'));}
 paragraph(card,req.basis_note||({jd:'依据：用户提供的 JD',sample_jd:'依据：已读取的招聘样本',role_standard:'依据：方向级参考标准',hypothesis:'依据：待确认的方向假设'}[req.basis]||''),'source-basis');parent.append(card);}
}
function renderLibrary(parent){
 paragraph(parent,'按职责查阅完整经历与项目表达。案例用于理解写法，不能替代你的真实经历。','highlight-intro');
 if(!DATA.libraryApplicable)addNotice(parent,'当前目标不属于产品经理。此库仅覆盖产品经理细分岗位，下面的案例供主动查阅，不作为本次诊断的推荐案例。');
 const controls=node('div','library-controls');const input=node('input');input.type='search';input.placeholder='搜索岗位、方向或职责';input.setAttribute('aria-label','搜索固定示例库');input.value=libraryQuery;
 const select=node('select');select.setAttribute('aria-label','筛选案例岗位');const all=node('option','','全部产品经理岗位');all.value='';select.append(all);for(const role of LIB.roles){const option=node('option','',role.name);option.value=role.id;select.append(option);}select.value=libraryRole;
 const results=node('div');let timer;input.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>{libraryQuery=input.value;libraryPage=0;drawResults();},120);});select.addEventListener('change',()=>{libraryRole=select.value;libraryPage=0;drawResults();});controls.append(input,select);parent.append(controls,results);
 function drawResults(){results.replaceChildren();const terms=libraryQuery.toLowerCase().trim().split(/\s+/).filter(Boolean);const found=Object.values(LIB.cases).filter(c=>(!libraryRole||c.roleId===libraryRole)&&terms.every(t=>(c.roleName+' '+c.directionName+' '+c.dutyName+' '+c.project.title).toLowerCase().includes(t)));const size=12;libraryPage=Math.min(libraryPage,Math.max(0,Math.ceil(found.length/size)-1));results.append(node('div','library-count','找到 '+found.length+' 组 · 固定库共 '+DATA.libraryCount+' 组'));
 for(const c of found.slice(libraryPage*size,(libraryPage+1)*size)){const b=button('',()=>openCase(c.id),'library-result');b.append(node('strong','',itemNumber('C',Object.values(LIB.cases).indexOf(c))+c.dutyName),node('small','',c.roleName+' / '+c.directionName));results.append(b);}
 if(!found.length)results.append(node('p','empty-state','没有匹配案例。试试更具体的职责词，或清除筛选。'));
 if(found.length>size){const pager=node('div','library-pagination');const prev=button('上一页',()=>{libraryPage--;drawResults();});prev.disabled=libraryPage===0;const next=button('下一页',()=>{libraryPage++;drawResults();});next.disabled=(libraryPage+1)*size>=found.length;pager.append(prev,node('span','',(libraryPage+1)+' / '+Math.ceil(found.length/size)),next);results.append(pager);}}
 drawResults();
}
function renderContent(){const parent=$('#analysis-content');parent.replaceChildren();if(currentView==='overview')renderOverview(parent);else if(currentView==='modules')renderModules(parent);else if(currentView==='reviews'){paragraph(parent,'编号与 PDF 原件标记一致。展开一项查看改写与编辑理由，原文在左侧高亮；模块层面的判断见模块诊断。','highlight-intro');reviewList(parent,moduleReviews());}else if(currentView==='questions'){const questions=reviews.filter(r=>r.question||r.decision==='needs_input');paragraph(parent,'补充事实后，回到 Codex 更新分析。未确认的内容不会写成既成成果。','highlight-intro');renderQuestions(parent);}else if(currentView==='jobs')renderJobMatches(parent);else if(currentView==='requirements')renderRequirements(parent);else if(currentView==='optimized'){paragraph(parent,DATA.run.final_text);parent.append(button('复制完整简历',()=>copyText(DATA.run.final_text),'primary-button'));}else renderLibrary(parent);}
function openCase(id){activeCase=LIB.cases[id];if(!activeCase)return;caseTab='work';$('#case-title').textContent=activeCase.dutyName;$('#case-meta').textContent=activeCase.roleName+' / '+activeCase.directionName+' / '+activeCase.id;renderCase();$('#case-dialog').showModal();}
function caseSections(){const c=activeCase,p=c.project;if(caseTab==='work')return [['工作经历',[c.workExperience.introduction,...c.workExperience.bullets]]];if(caseTab==='cstar')return [['项目名称',p.title],...Object.entries(p.cstar).map(([key,value])=>[({C:'C · 背景',S:'S · 情境',T:'T · 任务',A:'A · 行动',R:'R · 结果'})[key]||key,value])];return [['项目名称',p.title],...Object.entries(p.natural).map(([key,value])=>[({background:'项目背景',responsibilities:'本人职责',coreWork:'核心工作',results:'项目结果'})[key]||key,value])];}
function renderCase(){for(const b of $$('[data-case-tab]')){b.classList.toggle('active',b.dataset.caseTab===caseTab);b.setAttribute('aria-pressed',String(b.dataset.caseTab===caseTab));}const host=$('#case-body');host.replaceChildren();addNotice(host,activeCase.notice||'固定教学示例，仅用于表达参考；其中事实、规模和结果不属于你的经历。');for(const [title,content]of caseSections()){host.append(node('h3','',title));if(Array.isArray(content)){const ul=node('ul');for(const text of content)ul.append(node('li','',text));host.append(ul);}else paragraph(host,content);}}
if(plan?.sentence_review===false){const tab=$('[data-view=reviews]');tab.textContent='经历审阅';titles.reviews='经历审阅';}
if(DATA.run.mode==='general'&&!DATA.sources.some(s=>['jd','jd_sample'].includes(s.kind)))$('[data-view=requirements]').hidden=true;
if(DATA.run.final_text&&(!plan||plan.optimized_resume)){const tab=button('优化后的简历',()=>showView('optimized'));tab.dataset.view='optimized';$('.main-nav').append(tab);}
for(const b of $$('[data-view]'))b.addEventListener('click',()=>showView(b.dataset.view));
$('.brand').addEventListener('click',event=>{event.preventDefault();showView('overview');});
$('#show-kept').addEventListener('change',()=>highlightReview(activeReview,false));
function setZoom(value){zoom=Math.max(.7,Math.min(1.8,value));$('#pdf-pages').style.width=(zoom*100)+'%';$('#zoom-value').textContent=Math.round(zoom*100)+'%';$('#zoom-out').disabled=zoom<=.7;$('#zoom-in').disabled=zoom>=1.8;}
$('#zoom-out').addEventListener('click',()=>setZoom(zoom-.1));$('#zoom-in').addEventListener('click',()=>setZoom(zoom+.1));
$('#close-case').addEventListener('click',()=>$('#case-dialog').close());$('#case-dialog').addEventListener('click',e=>{if(e.target===$('#case-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
for(const b of $$('[data-case-tab]'))b.addEventListener('click',()=>{caseTab=b.dataset.caseTab;renderCase();});
$('#copy-case').addEventListener('click',()=>copyText(caseSections().map(([title,value])=>title+'\n'+(Array.isArray(value)?value.join('\n'):value)).join('\n\n')));
$('#target-name').textContent=DATA.run.target||(DATA.run.mode==='general'?'通用简历诊断':'按简历探索方向');$('#target-name').title=$('#target-name').textContent;$('#filename').textContent=DATA.filename;$('#filename').title=DATA.filename;$('#page-count').textContent=DATA.pages.length+' 页 · 原文件排版';if($('#review-count'))$('#review-count').textContent=reviews.length;
const navCounts={overview:(DATA.run.report_overview?.priorities||[]).length,modules:DATA.diagnoses.filter(d=>reviews.some(r=>r.diagnosis_ids.includes(d.id))).length,reviews:reviews.length,questions:questionItems().length,requirements:DATA.requirements.length,jobs:availableJobs().length,library:DATA.libraryCount,optimized:DATA.run.final_text?1:0};
const navLabels={requirements:'岗位要求',optimized:'优化全文'};
for(const tab of $$('.main-nav [data-view]')){const view=tab.dataset.view;tab.replaceChildren(node('span','nav-label',navLabels[view]||titles[view]));if(view!=='library')tab.append(node('span','nav-count',navCounts[view]??0));tab.title=view==='library'?'产品简历库':({overview:'优先处理事项',modules:'诊断项',reviews:'逐句审阅项',questions:'待补充事实项',requirements:'已拆解要求',jobs:'可推荐岗位（不含下线）',optimized:'优化全文'}[view]||'内容')+'：'+(navCounts[view]??0);}

renderPdf();showView('overview');
