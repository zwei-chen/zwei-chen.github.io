import {COLORS,escapeHTML as esc,format as f,createCharts,timeAxisTicks} from './charts.js';
import {t} from './language.js';
import {PythonEngine} from './engine.js';
const $=s=>document.querySelector(s), visual=document.documentElement.dataset.tool==='vision';
const form=$('#planner-form'),button=$('#calculate-plan'),status=$('#engine-status');
const fields=[...form.querySelectorAll('[name]')],defaults=Object.fromEntries(fields.map(x=>[x.name,x.value]));
const storageKey=visual?'dive-vision-profile-v1':'dive-vision-plan-v1';
const DEFAULT_RATES={descent:18,ascent:10};
const sample=()=>({settings:{...defaults},gases:[{id:'air',name:'Air',o2:21,he:0,size:11,pressure:200,switchDepth:0,enabled:true},...visual?[]:[{id:'ean50',name:'EAN50',o2:50,he:0,size:6,pressure:200,switchDepth:21,enabled:true}]],segments:[{depth:30,rate:DEFAULT_RATES.descent,gas:'air',kind:'descent'},{depth:30,duration:20,gas:'air',kind:'hold'},...visual?[{depth:5,rate:DEFAULT_RATES.ascent,gas:'air',kind:'ascent'},{depth:5,duration:3,gas:'air',kind:'hold'},{depth:0,rate:DEFAULT_RATES.ascent,gas:'air',kind:'ascent'}]:[]]});
let state=sample(),result=null,revision=0,busy=false,playTimer=null,timingTimer=null,timingRequest=0;
try{const saved=JSON.parse(localStorage.getItem(storageKey));if(saved&&saved.settings&&Array.isArray(saved.gases)&&saved.gases.length>0&&saved.gases.length<=8&&Array.isArray(saved.segments)&&saved.segments.length>0&&saved.segments.length<=12)state=saved;}catch{}
const charts=createCharts($('#profile-chart'),$('#tissue-chart'),$('#chart-legend'),selectPoint);
const engine=new PythonEngine(status,async()=>{setBusy(true);$('#retry-engine').hidden=true;const needsTiming=visual||state.segments.some(segment=>segment.duration==null);const hydrated=!needsTiming||await refreshTimings(true);setBusy(false);if(hydrated)form.requestSubmit();},()=>{setBusy(false);$('#retry-engine').hidden=false;});
function save(){try{localStorage.setItem(storageKey,JSON.stringify(state));}catch{}}
function error(message=''){$('#form-error').textContent=message;$('#form-error').hidden=!message;}
function stopPlay(){clearInterval(playTimer);playTimer=null;$('#play-profile').textContent=t('▶ 播放','▶ Play');}
function clear(){stopPlay();result=null;document.querySelectorAll('[data-segment-time],[data-gas-info]').forEach(x=>x.textContent='—');charts.clear();$('#plan-results').hidden=true;$('#compartment-grid').replaceChildren();$('#profile-caption').textContent=t('计算后查看深度、减压上限与气体变化。','Calculate to explore depth, ceilings and gas changes.');for(const id of ['depth','runtime','deco','tts'])$(`#metric-${id}`).textContent='—';$('#time-cursor').disabled=true;$('#minute-ticks').replaceChildren();$('#cursor-time').textContent='—';$('#cursor-info').textContent=t('计算后拖动时间轴查看组织负荷。','Calculate, then explore tissue loading with the timeline.');$('#export-chart').disabled=true;$('#play-profile').disabled=true;}
function changed(){revision++;state.settings=Object.fromEntries(fields.map(x=>[x.name,x.value]));clear();error();save();if(visual&&engine.ready){clearTimeout(timingTimer);timingTimer=setTimeout(()=>refreshTimings(),180);}if(engine.ready&&!busy)status.textContent=t('参数已更新，请重新计算。','Inputs changed. Calculate again.');}
function input(value,min,max,field,index,kind,disabled=false){return `<input type="number" value="${esc(value)}" min="${min}" max="${max}" step="any" data-kind="${kind}" data-index="${index}" data-field="${field}" ${disabled?'readonly':''} required>`;}
function gasOptions(selected){const gases=state.gases.filter(g=>g.enabled);return (!gases.some(g=>g.id===selected)?`<option value="" selected>${t('请选择有效气体','Select an enabled gas')}</option>`:'')+gases.map(g=>`<option value="${esc(g.id)}" ${g.id===selected?'selected':''}>${esc(g.name)}</option>`).join('');}
function renderGases(){
  $('#gas-list').innerHTML=state.gases.map((g,i)=>`<div class="gas-card ${g.enabled?'':'disabled'}"><div class="gas-heading"><span class="gas-marker" style="--gas-color:${COLORS[i]}"></span><input class="gas-name" aria-label="${t('气体名称','Gas name')} ${i+1}" type="text" maxlength="40" value="${esc(g.name)}" data-kind="gas" data-index="${i}" data-field="name" required><label><input type="checkbox" aria-label="${t('启用气体','Enable gas')} ${i+1}" data-kind="gas" data-index="${i}" data-field="enabled" ${g.enabled?'checked':''}>${t('启用','Use')}</label><button type="button" class="icon-button" data-remove-gas="${i}" aria-label="${t('删除气体','Remove gas')} ${i+1}">×</button></div><div class="gas-fields"><label>O₂ <span>%</span>${input(g.o2,1,100,'o2',i,'gas')}</label><label>He <span>%</span>${input(g.he,0,99,'he',i,'gas')}</label><label>${t('容量','Size')} <span>L</span>${input(g.size,1,50,'size',i,'gas')}</label><label>${t('初始压力','Start pressure')} <span>bar</span>${input(g.pressure,1,350,'pressure',i,'gas')}</label><label>${t('切换深度','Switch depth')} <span>m</span>${input(g.switchDepth,0,150,'switchDepth',i,'gas')}</label></div><div class="gas-derived" data-gas-info="${i}">—</div></div>`).join('');
}
function syncHolds(){let previous=0;for(const segment of state.segments){if(visual&&segment.kind==='hold')segment.depth=previous;previous=Number(segment.depth);}}
function renderSegments(){
  let previous=0;
  $('#segment-list').innerHTML=state.segments.map((segment,index)=>{
    if(!segment.kind)segment.kind=Number(segment.depth)>previous?'descent':Number(segment.depth)<previous?'ascent':'hold';
    previous=Number(segment.depth);
    const moving=visual&&segment.kind!=='hold';
    const timingField=moving
      ?`<label>${segment.kind==='ascent'?t('上升速度','Ascent rate'):t('下潜速度','Descent rate')} <span>m/min</span>${input(segment.rate??'',.1,60,'rate',index,'segment')}</label>`
      :`<label>${visual?t('停留时长','Hold time'):t('耗时','Duration')} <span>min</span>${input(segment.duration??'',.1,180,'duration',index,'segment')}</label>`;
    return `<div class="segment-card"><div class="segment-heading"><strong>${t('分段','Segment')} ${String(index+1).padStart(2,'0')}</strong><div class="segment-actions"><button type="button" class="icon-button" data-move="${index}" data-direction="-1" aria-label="${t('上移分段','Move segment up')} ${index+1}" ${index===0?'disabled':''}>↑</button><button type="button" class="icon-button" data-move="${index}" data-direction="1" aria-label="${t('下移分段','Move segment down')} ${index+1}" ${index===state.segments.length-1?'disabled':''}>↓</button><button type="button" class="icon-button" data-remove-segment="${index}" aria-label="${t('删除分段','Remove segment')} ${index+1}">×</button></div></div><div class="segment-fields ${visual?'four':''}">${visual?`<label>${t('类型','Type')}<select data-kind="segment" data-index="${index}" data-field="kind">${[['descent',t('下潜','Descent')],['hold',t('停留','Hold')],['ascent',t('上升','Ascent')]].map(([key,label])=>`<option value="${key}" ${segment.kind===key?'selected':''}>${label}</option>`).join('')}</select></label>`:''}<label>${t('目标深度','Target depth')} <span>m</span>${input(segment.depth,0,150,'depth',index,'segment',visual&&segment.kind==='hold')}</label>${timingField}<label>${t('呼吸气体','Gas')}<select data-kind="segment" data-index="${index}" data-field="gas" required>${gasOptions(segment.gas)}</select></label></div>${visual?`<p class="segment-timing">${t('本段耗时','Segment duration')} <output data-segment-time="${index}">—</output> min${moving?' · '+t('由深度与速度计算','from depth and speed'):''}</p>`:''}</div>`;
  }).join('');
}
async function refreshTimings(hydrate=false){
  if(!engine.ready||(!visual&&!hydrate))return false;
  const expected=revision,id=++timingRequest;
  try{
    const response=await engine.call('segments',{segments:state.segments});
    if(expected!==revision||id!==timingRequest)return false;
    if(hydrate){
      response.segments.forEach((segment,index)=>{const saved=state.segments[index];if(visual&&segment.kind!=='hold'&&saved.rate==null)saved.rate=segment.rate;if(!visual&&saved.duration==null)saved.duration=segment.duration;});
      renderSegments();save();
    }
    response.segments.forEach((segment,index)=>{const output=$(`[data-segment-time="${index}"]`);if(output)output.textContent=f(segment.duration,2);});
    return true;
  }catch(e){if(hydrate&&expected===revision)error(e.message);return false;}
}
function renderGasInfo(){
  if(!result)return;
  result.gasDetails.forEach((info,index)=>{const output=$(`[data-gas-info="${index}"]`);if(output)output.textContent=`N₂ ${f(info.n2,2)}% · ${t('底部 MOD','Working MOD')} ${f(info.mod)} m · ${t('减压 MOD','Deco MOD')} ${f(info.decoMod)} m`;});
}
function renderInputs(){fields.forEach(x=>x.value=state.settings[x.name]??defaults[x.name]);if(!state.settings.waterType){const density=Number(form.elements.density.value);form.elements.waterType.value=density===1?'fresh':density===1.03?'sea':'custom';}renderGases();renderSegments();}
form.addEventListener('input',event=>{const x=event.target;if(x.name==='waterType'&&x.value!=='custom')form.elements.density.value=x.value==='fresh'?'1':'1.03';if(x.name==='density')form.elements.waterType.value=Number(x.value)===1?'fresh':Number(x.value)===1.03?'sea':'custom';if(x.dataset.kind){(x.dataset.kind==='gas'?state.gases:state.segments)[Number(x.dataset.index)][x.dataset.field]=x.type==='checkbox'?x.checked:x.value;}if(x.id==='altitude'){state.settings.altitude=x.value;save();}else changed();});
form.addEventListener('change',event=>{const x=event.target;if(x.dataset.kind==='gas'){renderSegments();if(x.type==='checkbox')renderGases();}if(x.dataset.kind==='segment'&&['kind','depth'].includes(x.dataset.field)){const segment=state.segments[Number(x.dataset.index)];if(x.dataset.field==='kind'){segment.rate=segment.kind==='hold'?null:DEFAULT_RATES[segment.kind];if(segment.kind==='hold'&&segment.duration==null)segment.duration=10;}syncHolds();renderSegments();save();clearTimeout(timingTimer);if(engine.ready)timingTimer=setTimeout(()=>refreshTimings(),180);}});
form.addEventListener('click',event=>{const b=event.target.closest('button');if(!b)return;
  if(b.dataset.addGas){if(state.gases.length>=8)return error(t('最多 8 种气体。','Up to 8 gases are supported.'));const preset={air:['Air',21,0,0],ean50:['EAN50',50,0,21],oxygen:['Oxygen',100,0,6],trimix:['Trimix 21/35',21,35,0]}[b.dataset.addGas];state.gases.push({id:crypto.randomUUID(),name:preset[0],o2:preset[1],he:preset[2],switchDepth:preset[3],size:11,pressure:200,enabled:true});renderGases();renderSegments();changed();}
  else if(b.dataset.removeGas!==undefined){if(state.gases.length===1)return error(t('请至少保留一种气体。','Keep at least one gas.'));state.gases.splice(Number(b.dataset.removeGas),1);renderGases();renderSegments();changed();}
  else if(b.dataset.removeSegment!==undefined){if(state.segments.length===1)return error(t('请至少保留一个分段。','Keep at least one segment.'));state.segments.splice(Number(b.dataset.removeSegment),1);syncHolds();renderSegments();changed();}
  else if(b.dataset.move!==undefined){const i=Number(b.dataset.move),j=i+Number(b.dataset.direction);[state.segments[i],state.segments[j]]=[state.segments[j],state.segments[i]];syncHolds();renderSegments();changed();}
});
$('#add-segment').addEventListener('click',()=>{if(state.segments.length>=12)return error(t('最多 12 个分段。','Up to 12 segments are supported.'));const p=state.segments.at(-1);state.segments.push({depth:p.depth,duration:10,gas:p.gas,kind:'hold'});renderSegments();changed();});
$('#reset-example').addEventListener('click',()=>{state=sample();$('#altitude').value=0;renderInputs();changed();if(engine.ready&&!busy){setBusy(true);refreshTimings(true).then(ok=>{setBusy(false);if(ok)form.requestSubmit();});}});
$('#use-default-rates')?.addEventListener('click',()=>{for(const segment of state.segments){if(segment.kind!=='hold')segment.rate=DEFAULT_RATES[segment.kind];}renderSegments();changed();});
function setBusy(value){busy=value;button.disabled=!engine.ready||value;$('#cancel-calculate').hidden=!value;form.setAttribute('aria-busy',String(value));}
form.addEventListener('submit',async event=>{event.preventDefault();if(!engine.ready||busy)return;syncHolds();state.settings=Object.fromEntries(fields.map(x=>[x.name,x.value]));const expected=revision;error();clear();setBusy(true);status.textContent=t('正在计算组织负荷…','Calculating tissue loading…');
  try{const computed=await engine.call(visual?'visualize':'plan',state);if(revision!==expected){status.textContent=t('参数已更新，请重新计算。','Inputs changed. Calculate again.');return;}result=computed;renderResult();save();status.textContent=t('计算完成，拖动时间轴查看各时刻。','Complete. Explore each moment with the timeline.');}
  catch(e){if(revision===expected)error(e.message);}
  finally{setBusy(false);}
});
$('#retry-engine').addEventListener('click',()=>{$('#retry-engine').hidden=true;engine.start();});
$('#cancel-calculate').addEventListener('click',()=>{revision++;engine.fail(t('本次计算已取消，可重新加载。','Calculation cancelled. Reload when ready.'));});
function phase(row){if(row.phase==='switch')return row.decompression?t('减压换气','Deco gas switch'):t('切换气体','Gas switch');if(row.phase==='deco')return t('减压停留','Deco stop');if(row.phase==='safety')return t('附加停留','Optional stop');if(row.phase==='ascent')return t('自动上升','Auto ascent');return row.depth>row.fromDepth?t('下潜','Descent'):row.depth<row.fromDepth?t('上升','Ascent'):t('停留','Hold');}
function renderResult(){const s=result.summary;renderGasInfo();result.segments.forEach((segment,index)=>{const output=$(`[data-segment-time="${index}"]`);if(output)output.textContent=f(segment.duration,2);});
  for(const [key,value] of Object.entries({depth:s.maxDepth,runtime:s.runtime,deco:visual?s.maxGF99:s.decoTime,tts:visual?s.endDepth:s.tts}))$(`#metric-${key}`).textContent=f(value);
  $('#metric-cns').textContent=s.cns===null?t('超出估算范围','Out of range'):f(s.cns)+' %';$('#metric-otu').textContent=f(s.otu);$('#metric-ppo2').textContent=f(s.maxPPO2,2)+' bar';
  $('#profile-caption').textContent=visual?`GF ${f(result.settings.gfLow,0)}/${f(result.settings.gfHigh,0)} · ${t('按分段速度模拟','Simulated at per-segment speeds')}`:`GF ${f(result.settings.gfLow,0)}/${f(result.settings.gfHigh,0)} · ${s.firstStop===null?t('无强制减压停留','No mandatory deco stops'):t('首次减压停留','First deco stop')+' '+f(s.firstStop)+' m'}`;
  $('#plan-results').hidden=false;$('#export-chart').disabled=false;$('#play-profile').disabled=false;
  $('#plan-warnings').innerHTML=result.warnings.map(w=>`<p class="warning">${esc(w.message)}</p>`).join('');
  const gases=Object.fromEntries(result.gases.map(g=>[g.id,g]));
  $('#schedule-body').innerHTML=result.schedule.map(row=>`<tr class="${row.decompression?'deco':''}"><td>${phase(row)}</td><td>${f(row.depth)}</td><td>${f(row.duration,2)}</td><td>${f(row.runtime,2)}</td><td><span class="gas-pill">${esc(gases[row.gas].name)}</span></td></tr>`).join('');
  $('#gas-summary').innerHTML=result.gases.filter(g=>g.enabled).map(g=>{const info=result.gasDetails.find(x=>x.id===g.id);return `<div class="gas-use"><strong>${esc(g.name)} <small>O₂ ${f(g.o2)}% / He ${f(g.he)}%</small></strong><span class="${g.remaining<result.settings.reserve?'low':''}">${t('余压','Remaining')} ${f(g.remaining)} bar</span><small>${t('用量','Used')} ${f(g.used,0)} L · ${t('容量','Size')} ${f(g.size)} L</small><small>MOD ${f(info.mod)} m</small><div class="gas-bar" aria-label="${t('气瓶剩余压力比例','Remaining cylinder pressure')}"><span style="width:${Math.max(0,Math.min(100,g.remaining/g.pressure*100))}%;--gas-color:${COLORS[result.gases.indexOf(g)]}"></span></div></div>`;}).join('');
  renderTimeline();charts.setData(result);selectPoint(result.minuteIndices.at(-1));
}
function selectPoint(index){if(!result)return;const p=result.points[index],gas=result.gases.find(g=>g.id===p.gas);$('#time-cursor').value=String(p.time);$('#time-cursor').dataset.position=String(result.minuteIndices.indexOf(index));$('#time-cursor').setAttribute('aria-valuetext',`${f(p.time,2)} ${t('分钟','minutes')}`);$('#cursor-time').textContent=`${f(p.time,2)} / ${f(result.summary.runtime,2)} min`;
  $('#cursor-info').innerHTML=`<span>${t('深度','Depth')} <strong>${f(p.depth)} m</strong></span><span>${t('气体','Gas')} <strong>${esc(gas.name)}</strong></span><span>PPO₂ <strong>${f(p.ppo2,2)} bar</strong></span><span class="${p.gf99>100?'low':''}" title="${t('当前深度的主导腔隔梯度','Leading compartment gradient at the current depth')}">GF99 <strong>${f(p.gf99)}%</strong></span><span title="${t('以当前组织负荷直接到水面时的梯度','Surface gradient with the current tissue loading')}">${t('水面 GF','SurfGF')} <strong>${f(p.surfaceGF)}%</strong></span>`;
  const leading=p.gf99>0?p.tissueGF.indexOf(Math.max(...p.tissueGF)):-1;
  $('#compartment-grid').innerHTML=p.tissueGF.map((value,i)=>`<div class="compartment ${i===leading?'leading':''} ${value>100?'over':''}"><span>${String(i+1).padStart(2,'0')}${i===leading?' ●':''}</span><strong>${f(value)}<small>%</small></strong></div>`).join('');charts.select(index);
}
function renderTimeline(){
  if(!result)return;
  const end=result.points.at(-1).time,slider=$('#time-cursor');
  slider.disabled=false;slider.max=String(end);
  const width=$('#minute-ticks').clientWidth;
  $('#minute-ticks').innerHTML=timeAxisTicks(end,width).map(time=>{
    const position=nearestMinute(time);
    return `<button type="button" class="minute-tick ${time===0?'first':''}" data-minute-position="${position}" style="left:${time/end*100}%" aria-label="${f(time,2)} ${t('分钟','minutes')}">${f(time,2)}</button>`;
  }).join('');
}
function selectMinute(position){if(!result)return;position=Math.max(0,Math.min(result.minuteIndices.length-1,position));selectPoint(result.minuteIndices[position]);}
function nearestMinute(time){let best=0;for(let i=1;i<result.minuteIndices.length;i++)if(Math.abs(result.points[result.minuteIndices[i]].time-time)<Math.abs(result.points[result.minuteIndices[best]].time-time))best=i;return best;}
$('#time-cursor').addEventListener('input',e=>{if(!result)return;stopPlay();selectMinute(nearestMinute(Number(e.target.value)));});
$('#time-cursor').addEventListener('keydown',e=>{
  if(!result)return;const position=Number(e.target.dataset.position);
  const positions={ArrowLeft:position-1,ArrowDown:position-1,ArrowRight:position+1,ArrowUp:position+1,PageDown:position-5,PageUp:position+5,Home:0,End:result.minuteIndices.length-1};
  if(e.key in positions){e.preventDefault();stopPlay();selectMinute(positions[e.key]);}
});
$('#minute-ticks').addEventListener('click',e=>{const tick=e.target.closest('[data-minute-position]');if(!tick)return;stopPlay();selectMinute(Number(tick.dataset.minutePosition));});
$('#play-profile').addEventListener('click',()=>{
  if(playTimer)return stopPlay();if(!result)return;
  if(Number($('#time-cursor').dataset.position)>=result.minuteIndices.length-1)selectMinute(0);
  $('#play-profile').textContent=t('Ⅱ 暂停','Ⅱ Pause');
  playTimer=setInterval(()=>{const next=Number($('#time-cursor').dataset.position)+1;if(!result||next>=result.minuteIndices.length)return stopPlay();selectMinute(next);},500);
});
for(const b of document.querySelectorAll('[data-chart]'))b.addEventListener('click',()=>{document.querySelectorAll('[data-chart]').forEach(x=>x.setAttribute('aria-selected',String(x===b)));charts.setMode(b.dataset.chart);});
const chartResize=new ResizeObserver(()=>{charts.redraw();renderTimeline();});chartResize.observe($('#profile-chart'));chartResize.observe($('#timeline-scroll'));addEventListener('themechange',()=>charts.redraw());
function download(contents,name,type){const url=URL.createObjectURL(new Blob([contents],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function rows(){const gases=Object.fromEntries(result.gases.map(g=>[g.id,g.name]));return [[t('阶段','Phase'),t('深度(m)','Depth(m)'),t('耗时(min)','Duration(min)'),t('累计(min)','Runtime(min)'),t('气体','Gas')],...result.schedule.map(r=>[phase(r),r.depth,r.duration,r.runtime,gases[r.gas]])];}
$('#copy-plan').addEventListener('click',async()=>{if(!result)return;try{await navigator.clipboard.writeText('Dive Vision · '+t('学习模拟','Learning simulation')+'\n'+rows().map(r=>r.join('\t')).join('\n')+'\n'+result.warnings.map(w=>w.message).join('\n'));$('#copy-plan').textContent=t('已复制 ✓','Copied ✓');setTimeout(()=>$('#copy-plan').textContent=t('复制计划','Copy plan'),2000);}catch{error(t('剪贴板不可用，请使用导出 CSV。','Clipboard unavailable. Use Export CSV.'));}});
$('#export-plan').addEventListener('click',()=>{if(!result)return;const cell=x=>'"'+String(x).replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';download('\uFEFF'+[[t('学习模拟，实际潜水前须独立核对。','Learning simulation. Independently verify before real diving.')],...rows(),...result.warnings.map(w=>[w.message])].map(r=>r.map(cell).join(',')).join('\r\n'),'Dive-Vision-plan.csv','text/csv;charset=utf-8');});
$('#export-chart').addEventListener('click',()=>{const svg=$('#profile-chart svg');if(svg)download(svg.outerHTML,'Dive-Vision-profile.svg','image/svg+xml');});
const modelButton=document.createElement('button');modelButton.type='button';modelButton.className='text-button';modelButton.id='model-help';modelButton.textContent=t('模型说明','Model notes');$('.page-heading').append(modelButton);modelButton.addEventListener('click',()=>$('#model-dialog').showModal());$('#close-model').addEventListener('click',()=>$('#model-dialog').close());
$('#altitude-convert').addEventListener('click',async()=>{const expected=revision,altitude=$('#altitude').value;try{const r=await engine.call('environment',{altitude});if(expected!==revision||altitude!==$('#altitude').value)return;form.elements.surfacePressure.value=r.surfacePressure.toFixed(5);changed();}catch(e){if(expected===revision&&altitude===$('#altitude').value)error(e.message);}});
addEventListener('pagehide',()=>{save();stopPlay();});renderInputs();engine.start();
