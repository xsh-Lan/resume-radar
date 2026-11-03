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
const plan=DATA.confirmation?.stage2;
const titles = {optimized:'优化后的简历',overview:'整体判断',modules:'模块诊断',reviews:'逐句审阅',questions:'待补充事项',requirements:'岗位要求对照',library:'经历示例库'};
let currentView='overview', activeReview='', filter='all', zoom=1, activeCase=null, caseTab='work';
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
function showView(view){currentView=view;for(const b of $$('[data-view]')){if(b.dataset.view===view)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}$('#view-title').textContent=titles[view];$('#view-eyebrow').textContent=view==='library'?'固定内容库':'本次评估';renderContent();$('#analysis-content').scrollTop=0;}
function highlightReview(id,scroll=true){
 activeReview=id;
 for(const marker of $$('.pdf-marker')){marker.classList.toggle('selected',marker.dataset.review===id);marker.hidden=marker.dataset.keep==='true'&&!$('#show-kept').checked&&marker.dataset.review!==id;}
 for(const card of $$('.review-card'))card.classList.toggle('selected',card.dataset.review===id);
 const markers=$$('.pdf-marker').filter(b=>b.dataset.review===id);
 if(scroll&&markers.length)markers[0].scrollIntoView({block:'center',inline:'nearest',behavior:'smooth'});
 return markers.length>0;
}
function selectReview(id,fromPdf=false){
 if(!reviewMap.has(id))return;
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
   marker.setAttribute('aria-label',marker.title);if(index===0)marker.append(node('span','marker-number',numbers.get(review.id)));frame.append(marker);
  });}
  frame.append(node('span','page-number',page.number+' / '+DATA.pages.length));host.append(frame);
 }
 const mapped=DATA.resume.units.filter(u=>DATA.locations[u.id]?.status==='matched').length;
 $('#mapping-summary').textContent=mapped===DATA.resume.units.length?'原文位置已全部关联':(DATA.resume.units.length-mapped)+' 处原文位置待核对';
}
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
 heading(body,'原文');paragraph(body,originalText(review),'quote-box');
 heading(body,review.decision==='needs_input'?'基于已知事实的保守表达':'修改后');
 const changed=review.text||(review.decision==='keep'?originalText(review):'暂不生成新表述，先核实事实。');paragraph(body,changed,'rewrite-box');
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
 for(const item of overview.assessment||[]){const row=node('div','assessment-row');const name=node('strong','',item.dimension);name.append(node('span','status-tag',labels[item.status]||item.status));row.append(name);paragraph(row,item.judgment);parent.append(row);}
 if(overview.fit_scope)paragraph(parent,overview.fit_scope,'source-basis');
 if(overview.eligibility)paragraph(parent,overview.eligibility,'source-basis');
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
 const groups=new Map(),shownDiagnoses=new Set();for(const r of reviews){const section=units.get(r.unit_ids[0])?.section||'基本信息';if(!groups.has(section))groups.set(section,[]);groups.get(section).push(r);}
 for(const [section,items] of groups){const group=node('section','module-group');group.append(node('h3','',section+' · '+items.filter(r=>r.decision!=='keep').length+' 处建议'));
  for(const id of new Set(items.flatMap(r=>r.diagnosis_ids))){if(shownDiagnoses.has(id))continue;shownDiagnoses.add(id);const d=diagnoses.get(id);if(!d)continue;const block=node('section','requirement-card');block.append(node('h3','',d.title||d.does_not_demonstrate));paragraph(block,d.demonstrates);paragraph(block,d.impact);paragraph(block,d.next_action);const related=items.filter(r=>r.diagnosis_ids.includes(id));for(const r of related)block.append(button('对照原文 #'+numbers.get(r.id),()=>selectReview(r.id),'locate-button'));group.append(block);}
  for(const r of items)group.append(reviewCard(r));parent.append(group);}
}
function renderRequirements(parent){
 paragraph(parent,'岗位要求以本次 JD 或已声明的方向依据为准；示例库不作为招聘门槛。','highlight-intro');
 for(const req of DATA.requirements){const card=node('section','requirement-card');const h=node('h3','',req.description);h.append(node('span','status-tag',labels[req.support]||req.support));card.append(h);paragraph(card,req.responsibility);paragraph(card,req.decision_depth);
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
 for(const c of found.slice(libraryPage*size,(libraryPage+1)*size)){const b=button('',()=>openCase(c.id),'library-result');b.append(node('strong','',c.dutyName),node('small','',c.roleName+' / '+c.directionName));results.append(b);}
 if(!found.length)results.append(node('p','empty-state','没有匹配案例。试试更具体的职责词，或清除筛选。'));
 if(found.length>size){const pager=node('div','library-pagination');const prev=button('上一页',()=>{libraryPage--;drawResults();});prev.disabled=libraryPage===0;const next=button('下一页',()=>{libraryPage++;drawResults();});next.disabled=(libraryPage+1)*size>=found.length;pager.append(prev,node('span','',(libraryPage+1)+' / '+Math.ceil(found.length/size)),next);results.append(pager);}}
 drawResults();
}
function renderContent(){const parent=$('#analysis-content');parent.replaceChildren();if(currentView==='overview')renderOverview(parent);else if(currentView==='modules')renderModules(parent);else if(currentView==='reviews'){paragraph(parent,'编号与 PDF 原件标记一致。展开一项即可查看原文、改写与对应建议。','highlight-intro');reviewList(parent,reviews);}else if(currentView==='questions'){const questions=reviews.filter(r=>r.question||r.decision==='needs_input');paragraph(parent,'补充事实后，回到 Codex 更新分析。未确认的内容不会写成既成成果。','highlight-intro');reviewList(parent,questions,false);}else if(currentView==='requirements')renderRequirements(parent);else if(currentView==='optimized'){paragraph(parent,DATA.run.final_text);parent.append(button('复制完整简历',()=>copyText(DATA.run.final_text),'primary-button'));}else renderLibrary(parent);}
function openCase(id){activeCase=LIB.cases[id];if(!activeCase)return;caseTab='work';$('#case-title').textContent=activeCase.dutyName;$('#case-meta').textContent=activeCase.roleName+' / '+activeCase.directionName+' / '+activeCase.id;renderCase();$('#case-dialog').showModal();}
function caseSections(){const c=activeCase,p=c.project;if(caseTab==='work')return [['工作经历',[c.workExperience.introduction,...c.workExperience.bullets]]];if(caseTab==='cstar')return [['项目名称',p.title],...Object.entries(p.cstar).map(([key,value])=>[({C:'C · 背景',S:'S · 情境',T:'T · 任务',A:'A · 行动',R:'R · 结果'})[key]||key,value])];return [['项目名称',p.title],...Object.entries(p.natural).map(([key,value])=>[({background:'项目背景',responsibilities:'本人职责',coreWork:'核心工作',results:'项目结果'})[key]||key,value])];}
function renderCase(){for(const b of $$('[data-case-tab]')){b.classList.toggle('active',b.dataset.caseTab===caseTab);b.setAttribute('aria-pressed',String(b.dataset.caseTab===caseTab));}const host=$('#case-body');host.replaceChildren();addNotice(host,activeCase.notice||'固定教学示例，仅用于表达参考；其中事实、规模和结果不属于你的经历。');for(const [title,content]of caseSections()){host.append(node('h3','',title));if(Array.isArray(content)){const ul=node('ul');for(const text of content)ul.append(node('li','',text));host.append(ul);}else paragraph(host,content);}}
if(plan?.sentence_review===false){const tab=$('[data-view=reviews]');tab.textContent='经历审阅';titles.reviews='经历审阅';}
if(DATA.run.mode==='general')$('[data-view=requirements]').hidden=true;
if(DATA.run.final_text&&(!plan||plan.optimized_resume)){const tab=button('优化后的简历',()=>showView('optimized'));tab.dataset.view='optimized';$('.main-nav').append(tab);}
for(const b of $$('[data-view]'))b.addEventListener('click',()=>showView(b.dataset.view));
$('.brand').addEventListener('click',event=>{event.preventDefault();showView('overview');});
$('#show-kept').addEventListener('change',()=>highlightReview(activeReview,false));
function setZoom(value){zoom=Math.max(.7,Math.min(1.8,value));$('#pdf-pages').style.width=(zoom*100)+'%';$('#zoom-value').textContent=Math.round(zoom*100)+'%';$('#zoom-out').disabled=zoom<=.7;$('#zoom-in').disabled=zoom>=1.8;}
$('#zoom-out').addEventListener('click',()=>setZoom(zoom-.1));$('#zoom-in').addEventListener('click',()=>setZoom(zoom+.1));
$('#close-case').addEventListener('click',()=>$('#case-dialog').close());$('#case-dialog').addEventListener('click',e=>{if(e.target===$('#case-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
for(const b of $$('[data-case-tab]'))b.addEventListener('click',()=>{caseTab=b.dataset.caseTab;renderCase();});
$('#copy-case').addEventListener('click',()=>copyText(caseSections().map(([title,value])=>title+'\n'+(Array.isArray(value)?value.join('\n'):value)).join('\n\n')));
$('#target-name').textContent=DATA.run.target||'按简历探索方向';$('#filename').textContent=DATA.filename;$('#page-count').textContent=DATA.pages.length+' 页 · 原文件排版';if($('#review-count'))$('#review-count').textContent=reviews.length;
renderPdf();showView('overview');
