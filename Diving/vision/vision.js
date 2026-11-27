import {COLORS,escapeHTML as esc,format as f} from './charts.js?v=6';
import {createProfileView,download} from './profile-view.js?v=6';
import {t} from './language.js';
import {PythonEngine} from './engine.js';
const $=s=>document.querySelector(s), visual=document.documentElement.dataset.tool==='vision';
const constantGF=document.documentElement.dataset.tool==='constant-gf';
const planPage=document.documentElement.dataset.tool==='plan';
const form=$('#planner-form'),button=$('#calculate-plan'),status=$('#engine-status');
const fields=[...form.querySelectorAll('[name]')];
function readSettings(){
  return Object.fromEntries(fields.map(field=>[field.name,field.value]));
}
const defaults=readSettings();
const storageKey=constantGF?'dive-vision-constant-gf-v1':visual?'dive-vision-profile-v1':'dive-vision-plan-v1';
const DEFAULT_RATES={descent:18,ascent:10};
const sample=()=>({autoGases:[],useDefaultRates:true,settings:{...defaults},gases:[{id:'air',name:'Air',o2:21,he:0,size:11,pressure:200,switchDepth:0,enabled:true},...visual?[]:[{id:'ean50',name:'EAN50',o2:50,he:0,size:6,pressure:200,switchDepth:21,enabled:true}]],segments:[{depth:30,rate:DEFAULT_RATES.descent,gas:'air',kind:'descent'},{depth:30,duration:20,gas:'air',kind:'hold'},...visual?[{depth:5,rate:DEFAULT_RATES.ascent,gas:'air',kind:'ascent'},{depth:5,duration:3,gas:'air',kind:'hold'},{depth:0,rate:DEFAULT_RATES.ascent,gas:'air',kind:'ascent'}]:[]]});
let state=sample(),result=null,revision=0,busy=false,timingTimer=null,timingRequest=0;
try{const saved=JSON.parse(localStorage.getItem(storageKey));if(saved&&saved.settings&&Array.isArray(saved.gases)&&(planPage||saved.gases.length>0)&&saved.gases.length<=8&&Array.isArray(saved.segments)&&saved.segments.length>0&&saved.segments.length<=24)state=saved;}catch{}
// Older drafts contain only the manual inventory, even when Automatic mode was open.
if(!Array.isArray(state.autoGases))state.autoGases=[];
const engine=new PythonEngine(status,async()=>{setBusy(true);$('#retry-engine').hidden=true;const hydrated=await refreshTimings(true);setBusy(false);if(hydrated)form.requestSubmit();},()=>{setBusy(false);$('#retry-engine').hidden=false;});
const profileView=createProfileView(engine);
function save(){try{localStorage.setItem(storageKey,JSON.stringify(state));}catch{}}
function error(message=''){$('#form-error').textContent=message;$('#form-error').hidden=!message;}
function clear(){profileView.clear();result=null;renderStandardGases();document.querySelectorAll('[data-segment-time],[data-waypoint-travel],[data-waypoint-time],[data-gas-info]').forEach(x=>x.textContent='—');$('#plan-results').hidden=true;$('#compartment-grid').replaceChildren();$('#profile-caption').textContent=t('计算后查看深度、减压上限与气体变化。','Calculate to explore depth, ceilings and gas changes.');for(const id of ['depth','runtime','deco','tts'])$(`#metric-${id}`).textContent='—';}
function changed(){revision++;state.settings=readSettings();clear();error();save();if(engine.ready){clearTimeout(timingTimer);timingTimer=setTimeout(()=>refreshTimings(),180);}if(engine.ready&&!busy)status.textContent=t('参数已更新，请重新计算。','Inputs changed. Calculate again.');}
function input(value,min,max,field,index,kind,disabled=false){return `<input type="number" value="${esc(value??'')}" min="${min}" max="${max}" step="any" data-kind="${kind}" data-index="${index}" data-field="${field}" ${disabled?'readonly':''} ${field==='switchDepth'?'':'required'}>`;}
function gasOptions(selected){const gases=state.gases.filter(g=>g.enabled);return (!gases.some(g=>g.id===selected)?`<option value="" selected>${t('请选择有效气体','Select an enabled gas')}</option>`:'')+gases.map(g=>`<option value="${esc(g.id)}" ${g.id===selected?'selected':''}>${esc(g.name)}</option>`).join('');}
function renderGases(){
  $('#gas-list').innerHTML=editableGases().map((g,i)=>`<div class="gas-card ${g.enabled?'':'disabled'}"><div class="gas-heading"><span class="gas-marker" style="--gas-color:${COLORS[i]}"></span><input class="gas-name" aria-label="${t('气体名称','Gas name')} ${i+1}" type="text" maxlength="40" value="${esc(g.name)}" data-kind="gas" data-index="${i}" data-field="name" required><label><input type="checkbox" aria-label="${t('启用气体','Enable gas')} ${i+1}" data-kind="gas" data-index="${i}" data-field="enabled" ${g.enabled?'checked':''}>${t('启用','Use')}</label><button type="button" class="icon-button" data-remove-gas="${i}" aria-label="${t('删除气体','Remove gas')} ${i+1}">×</button></div><div class="gas-fields"><label>O₂ <span>%</span>${input(g.o2,1,100,'o2',i,'gas')}</label><label>He <span>%</span>${input(g.he,0,99,'he',i,'gas')}</label><label>${t('容量','Size')} <span>L</span>${input(g.size,1,50,'size',i,'gas')}</label><label>${t('初始压力','Start pressure')} <span>bar</span>${input(g.pressure,1,350,'pressure',i,'gas')}</label><label>${t('切换深度','Switch depth')} <span>m</span>${input(g.switchDepth,0,150,'switchDepth',i,'gas')}</label></div><div class="gas-derived" data-gas-info="${i}">—</div></div>`).join('');
}
function automaticSegments(){return state.useDefaultRates===true&&Array.isArray(state.waypoints);}
function bottomOnly(){return planPage && state.profileMode==='bottom';}
function editableGases(){return bottomOnly()?state.autoGases:state.gases;}
function renderStandardGases(){
  if(!planPage)return;
  const list=$('#standard-gas-result');
  list.replaceChildren();
  list.hidden=!bottomOnly()||result?.gasSource!=='generated';
  if(list.hidden)return;
  for(const gas of result.gases.filter(g=>g.used>0)){
    const item=document.createElement('li');
    const role=gas.id===result.bottomGas?t('底气','Bottom gas'):gas.travelGas?t('旅行气','Travel gas'):t('减压气','Deco gas');
    item.textContent=role+' · '+gas.name;
    list.append(item);
  }
}
function renderPlanningMode(){
  if(!planPage)return;
  const auto=bottomOnly();
  for(const [id,hidden] of [['bottom-inputs',!auto],['custom-inputs',auto]]){
    const pane=$('#'+id);pane.hidden=hidden;pane.disabled=hidden;
  }
  document.querySelectorAll('[data-profile-mode]').forEach(b=>b.setAttribute('aria-pressed',String((b.dataset.profileMode==='bottom')===auto)));
  const source=$('#auto-gas-source');
  source.hidden=!auto;
  if(!auto)return;
  source.textContent=state.autoGases.length
    ? t('本次规划使用下方启用的气体。清空气体列表即可恢复标准气。','This plan uses the enabled gases below. Clear the list to use standard gases.')
    : t('留空时按目标深度从 GUE、PATD 标准气中筛选。也可以在下方录入可用气体。','Leave empty to select from GUE and PATD standard mixes for the target depth, or enter available gases below.');
  if(!state.bottom){
    const rows=automaticSegments()?state.waypoints:state.segments;
    const depth=Math.max(0,...rows.map(row=>Number(row.depth)||0));
    const hold=rows.find((row,i)=>Number(row.depth)===depth&&(automaticSegments()||Number(rows[i-1]?.depth)===depth));
    state.bottom={depth:depth||30,duration:hold?.duration??20};
  }
  $('#bottom-depth').value=state.bottom.depth;
  $('#bottom-duration').value=state.bottom.duration;

}
function editingSegments(){return automaticSegments()?state.waypoints:state.segments;}
function syncHolds(){if(state.useDefaultRates===true)return;let previous=0;for(const segment of state.segments){if(visual&&segment.kind==='hold')segment.depth=previous;previous=Number(segment.depth);}}
function describeSegment(segment,fromDepth){
  const valid=fromDepth!==null&&String(segment.depth).trim()!==''&&Number.isFinite(Number(segment.depth));
  const depth=valid?Number(segment.depth):null;
  const inferred=valid?(depth>fromDepth?'descent':depth<fromDepth?'ascent':'hold'):'pending';
  const kind=visual&&segment.kind?segment.kind:inferred;
  const names={descent:t('下潜','Descent'),hold:t('停留','Hold'),ascent:t('上升','Ascent'),pending:t('待设定','Set depth')};
  const icons={descent:'↓',hold:'━',ascent:'↑',pending:'·'};
  const route=valid?(kind==='hold'?t(`保持在 ${f(depth)} m`,`Hold at ${f(depth)} m`):`${f(fromDepth)} m → ${f(depth)} m`):t('请先填写有效深度','Enter a valid depth');
  const durationLabel=kind==='hold'?t('停留时长','Hold time'):kind==='descent'?t('下潜耗时','Descent time'):kind==='ascent'?t('上升耗时','Ascent time'):t('分段耗时','Segment time');
  return {kind,depth,route,badge:`${icons[kind]} ${names[kind]}`,depthLabel:kind==='hold'?t('停留深度','Hold depth'):t('目标深度','Target depth'),durationLabel};
}
function segmentTimingField(segment,index,description){
  if(instantAscent() && description.kind==='ascent')return `<label>${t('上升耗时','Ascent time')} <span>min</span><input type="number" value="0" readonly></label>`;
  const moving=['ascent','descent'].includes(description.kind),automatic=moving&&state.useDefaultRates===true;
  return automatic?'':visual&&moving
      ?`<label>${segment.kind==='ascent'?t('上升速度','Ascent rate'):t('下潜速度','Descent rate')} <span>m/min</span>${input(segment.rate??'',.1,60,'rate',index,'segment')}</label>`
      :`<label><span class="segment-field-label" data-duration-label>${description.durationLabel}</span> <span>min</span>${input(segment.duration??'',.000001,180,'duration',index,'segment')}</label>`;
}
function refreshSegmentLabels(){
  if(state.useDefaultRates===true)return;
  let previous=0;
  state.segments.forEach((segment,index)=>{
    const description=describeSegment(segment,previous),card=$(`[data-segment-card="${index}"]`);
    previous=description.depth;
    if(!visual&&description.kind!=='pending')segment.kind=description.kind;
    if(!card)return;
    card.dataset.segmentKind=description.kind;
    card.querySelector('.segment-kind').textContent=description.badge;
    card.querySelector('.segment-route').textContent=description.route;
    card.querySelector('[data-depth-label]').textContent=description.depthLabel;
    const moving=['ascent','descent'].includes(description.kind),automatic=moving&&state.useDefaultRates===true;
    const timing=card.querySelector('[data-timing-field]');timing.hidden=automatic;timing.innerHTML=segmentTimingField(segment,index,description);
    card.querySelector('.segment-fields').classList.toggle('automatic',automatic);
    card.querySelector('.segment-timing').hidden=!(visual||automatic);
  });
}
function renderWaypoints(){
  $('#segment-list').innerHTML=state.waypoints.map((point,index)=>`<div class="segment-card" data-waypoint-card="${index}" data-segment-kind="hold"><div class="segment-heading"><strong>${t('分段','Segment')} ${String(index+1).padStart(2,'0')}</strong><div class="segment-actions"><button type="button" class="icon-button" data-move="${index}" data-direction="-1" aria-label="${t('上移分段','Move segment up')} ${index+1}" ${index===0?'disabled':''}>↑</button><button type="button" class="icon-button" data-move="${index}" data-direction="1" aria-label="${t('下移分段','Move segment down')} ${index+1}" ${index===state.waypoints.length-1?'disabled':''}>↓</button><button type="button" class="icon-button" data-remove-segment="${index}" aria-label="${t('删除分段','Remove segment')} ${index+1}">×</button></div></div><div class="segment-fields waypoint-fields"><label>${t('目标深度','Target depth')} <span>m</span>${input(point.depth,0,150,'depth',index,'waypoint')}</label><label>${t('停留时长','Hold time')} <span>min</span>${input(point.duration,0,180,'duration',index,'waypoint')}</label><label>${t('呼吸气体','Gas')}<select data-kind="waypoint" data-index="${index}" data-field="gas" required>${gasOptions(point.gas)}</select></label></div><p class="segment-timing">${t('自动移动','Automatic travel')} <output data-waypoint-travel="${index}">—</output> min · ${t('本段合计','Segment total')} <output data-waypoint-time="${index}">—</output> min</p></div>`).join('');
}
function renderTimings(response){
  if(bottomOnly())return;
  if(automaticSegments())(response.waypointTimings||[]).forEach((row,index)=>{
    const travel=$(`[data-waypoint-travel="${index}"]`),total=$(`[data-waypoint-time="${index}"]`);
    if(travel)travel.textContent=f(row.travelTime,2);if(total)total.textContent=f(row.totalTime,2);
  });
  else response.segments.forEach((segment,index)=>{const output=$(`[data-segment-time="${index}"]`);if(output)output.textContent=f(segment.duration,2);});
}
async function setDefaultRates(enabled){
  if(!engine.ready||busy){renderSegments();return;}
  const expected=revision;
  setBusy(true);error();
  try{
    // Converting editors must preserve usable finite travel times when the experiment is later turned off.
    const settings=instantAscent()?{...state.settings,ascentMode:'staged'}:state.settings;
    const response=await engine.call('segments',{...state,settings,mode:visual?'vision':'plan',useDefaultRates:true,waypoints:enabled?undefined:state.waypoints});
    if(expected!==revision)return;
    if(enabled){
      if(response.waypoints.length>12)throw new Error(t('默认速度模式最多支持 12 个目标深度。','Default speed mode supports up to 12 target depths.'));
      state.waypoints=response.waypoints;state.automaticEdited=false;
    }else{
      if(state.automaticEdited){
        if(!response.segments.length)throw new Error(t('请先设置移动深度或停留时长。','Enter a target depth or hold duration first.'));
        state.segments=response.segments;
      }
      delete state.waypoints;delete state.automaticEdited;
    }
    state.useDefaultRates=enabled;renderSegments();changed();
    clearTimeout(timingTimer);await refreshTimings();
  }catch(e){error(e.message);}
  finally{setBusy(false);$('#use-default-rates').checked=state.useDefaultRates===true;}
}
function renderSegments(){
  renderPlanningMode();
  if(bottomOnly())return;
  $('#use-default-rates').checked=state.useDefaultRates===true;
  const speedHint=$('#default-speed-summary');speedHint.hidden=state.useDefaultRates!==true;
  speedHint.textContent=visual?t('默认下潜 18 m/min · 默认上升 10 m/min','Default descent 18 m/min · Default ascent 10 m/min'):t(`使用主要参数：下潜 ${f(form.elements.descentRate.value)} m/min · 上升 ${f(form.elements.ascentRate.value)} m/min`,`Main settings: descent ${f(form.elements.descentRate.value)} m/min · ascent ${f(form.elements.ascentRate.value)} m/min`);
  if(instantAscent())speedHint.textContent=t(`下潜 ${f(form.elements.descentRate.value)} m/min · 上升移动 0 min`,`Descent ${f(form.elements.descentRate.value)} m/min · ascent travel 0 min`);
  if(state.useDefaultRates===true){
    if(automaticSegments())renderWaypoints();
    else $('#segment-list').innerHTML=`<p class="hint">${t('正在整理目标深度…','Preparing target depths…')}</p>`;
    return;
  }
  let previous=0;
  $('#segment-list').innerHTML=state.segments.map((segment,index)=>{
    const description=describeSegment(segment,previous);
    previous=description.depth;
    if((!visual||!segment.kind)&&description.kind!=='pending')segment.kind=description.kind;
    const moving=['ascent','descent'].includes(description.kind),automatic=moving&&state.useDefaultRates===true;
    const timingField=segmentTimingField(segment,index,description);
    return `<div class="segment-card" data-segment-card="${index}" data-segment-kind="${description.kind}"><div class="segment-heading"><div class="segment-identity"><strong>${t('分段','Segment')} ${String(index+1).padStart(2,'0')}</strong><span class="segment-kind">${description.badge}</span></div><div class="segment-actions"><button type="button" class="icon-button" data-move="${index}" data-direction="-1" aria-label="${t('上移分段','Move segment up')} ${index+1}" ${index===0?'disabled':''}>↑</button><button type="button" class="icon-button" data-move="${index}" data-direction="1" aria-label="${t('下移分段','Move segment down')} ${index+1}" ${index===state.segments.length-1?'disabled':''}>↓</button><button type="button" class="icon-button" data-remove-segment="${index}" aria-label="${t('删除分段','Remove segment')} ${index+1}">×</button></div></div><p class="segment-route">${description.route}</p><div class="segment-fields ${visual?'four':''} ${automatic?'automatic':''}">${visual?`<label>${t('类型','Type')}<select data-kind="segment" data-index="${index}" data-field="kind">${[['descent',t('下潜','Descent')],['hold',t('停留','Hold')],['ascent',t('上升','Ascent')]].map(([key,label])=>`<option value="${key}" ${segment.kind===key?'selected':''}>${label}</option>`).join('')}</select></label>`:''}<label><span class="segment-field-label" data-depth-label>${description.depthLabel}</span> <span>m</span>${input(segment.depth,0,150,'depth',index,'segment',visual&&segment.kind==='hold')}</label><div data-timing-field ${automatic?'hidden':''}>${timingField}</div><label>${t('呼吸气体','Gas')}<select data-kind="segment" data-index="${index}" data-field="gas" required>${gasOptions(segment.gas)}</select></label></div><p class="segment-timing" ${visual||automatic?'':'hidden'}>${t('本段耗时','Segment duration')} <output data-segment-time="${index}">—</output> min${moving?' · '+t('由深度与速度计算','from depth and speed'):''}</p></div>`;
  }).join('');
}
async function refreshTimings(hydrate=false){
  if(!engine.ready)return false;
  if(bottomOnly())return true;
  const expected=revision,id=++timingRequest;
  try{
    // Migrate stored durations at their original rates before applying instant travel.
    const migrateAtNormalRates=hydrate&&instantAscent()&&!automaticSegments()
      &&(typeof state.useDefaultRates!=='boolean'||state.segments.some(s=>s.kind==='ascent'&&s.duration==null&&s.rate!=null));
    const settings=migrateAtNormalRates?{...state.settings,ascentMode:'staged'}:state.settings;
    const response=await engine.call('segments',{segments:state.segments,waypoints:state.waypoints,settings,gases:state.gases,useDefaultRates:state.useDefaultRates,mode:visual?'vision':'plan'});
    if(expected!==revision||id!==timingRequest)return false;
    if(hydrate){
      if(typeof state.useDefaultRates!=='boolean'){
        // Preserve the effective travel times of old drafts with mixed per-row modes.
        // The new UI has a single mode; materialize old automatic rows when needed.
        response.segments.forEach((resolved,index)=>{const saved=state.segments[index];if(!response.useDefaultRates&&saved.useDefaultRate===true&&resolved.kind!=='hold'){saved.rate=resolved.rate;saved.duration=resolved.duration;}delete saved.useDefaultRate;});
        state.useDefaultRates=response.useDefaultRates;
      }
      if(!automaticSegments())response.segments.forEach((segment,index)=>{const saved=state.segments[index];if(visual&&segment.kind!=='hold'&&saved.rate==null)saved.rate=segment.rate;if(!visual&&saved.duration==null&&segment.duration>0)saved.duration=segment.duration;});
      if(state.useDefaultRates===true&&!state.waypoints)state.waypoints=response.waypoints;
      renderSegments();save();
    }
    if(migrateAtNormalRates||(automaticSegments()&&!response.waypointTimings))return refreshTimings();
    renderTimings(response);
    return true;
  }catch(e){if(hydrate&&expected===revision)error(e.message);return false;}
}
function renderGasInfo(){
  if(!result||result.gasSource==='generated')return;
  result.gasDetails.forEach((info,index)=>{const output=$(`[data-gas-info="${index}"]`);if(output)output.textContent=`N₂ ${f(info.n2,2)}% · ${t('底部 MOD','Working MOD')} ${f(info.mod)} m · ${t('减压 MOD','Deco MOD')} ${f(info.decoMod)} m`+(result.gases[index].travelGas?' · '+t('旅行气交接','Travel switch')+' '+f(result.gases[index].switchDepth,2)+' m':'');});
}
function instantAscent(){return planPage && form.elements.ascentMode.value==='instant';}
function updateRateInputs(){
  if(!planPage)return;
  for(const field of [form.elements.ascentRate,form.elements.decoAscentRate]){
    field.disabled=false;
    if(instantAscent()){
      if(!field.validity.valid)field.value=field.defaultValue;
      field.disabled=true;
    }
  }
}
function renderInputs(){fields.forEach(field=>{
    field.value=state.settings[field.name]??(field.name==='decoAscentRate'?state.settings.ascentRate:null)??defaults[field.name];
  });updateRateInputs();if(!state.settings.waterType){const density=Number(form.elements.density.value);form.elements.waterType.value=density===1?'fresh':density===1.03?'sea':'custom';}renderGases();renderSegments();}
form.addEventListener('input',event=>{const x=event.target;
  if(x.name==='ascentMode'){updateRateInputs();renderSegments();changed();return;}
  if(x.id==='bottom-depth'||x.id==='bottom-duration'){
    state.bottom[x.id==='bottom-depth'?'depth':'duration']=x.value;changed();return;
  }
  if(x.id==='use-default-rates'){setDefaultRates(x.checked);return;}if(x.name==='waterType'&&x.value!=='custom')form.elements.density.value=x.value==='fresh'?'1':'1.03';if(x.name==='density')form.elements.waterType.value=Number(x.value)===1?'fresh':Number(x.value)===1.03?'sea':'custom';if(x.dataset.kind){(x.dataset.kind==='gas'?editableGases():x.dataset.kind==='waypoint'?state.waypoints:state.segments)[Number(x.dataset.index)][x.dataset.field]=x.type==='checkbox'?x.checked:x.value;}if(x.dataset.kind==='waypoint')state.automaticEdited=true;if(x.dataset.kind==='segment'&&x.dataset.field==='depth')refreshSegmentLabels();if(['ascentRate','descentRate'].includes(x.name))renderSegments();if(x.id==='altitude'){state.settings.altitude=x.value;save();}else changed();});
form.addEventListener('change',event=>{const x=event.target;if(x.dataset.kind==='gas'){renderSegments();if(x.type==='checkbox')renderGases();}if(x.dataset.kind==='segment'&&['kind','depth'].includes(x.dataset.field)){const segment=state.segments[Number(x.dataset.index)];if(x.dataset.field==='kind'){segment.rate=segment.kind==='hold'?null:DEFAULT_RATES[segment.kind];if(segment.kind==='hold'&&segment.duration==null)segment.duration=10;}syncHolds();renderSegments();save();clearTimeout(timingTimer);if(engine.ready)timingTimer=setTimeout(()=>refreshTimings(),180);}});
form.addEventListener('click',event=>{const b=event.target.closest('button');if(!b)return;
  if(b.dataset.profileMode){
    state.profileMode=b.dataset.profileMode;renderGases();renderSegments();changed();
    if(!bottomOnly()&&engine.ready&&state.useDefaultRates&&!state.waypoints)refreshTimings(true);
    return;
  }
  if(b.dataset.addGas){if(editableGases().length>=8)return error(t('最多 8 种气体。','Up to 8 gases are supported.'));const preset={air:['Air',21,0,0],ean50:['EAN50',50,0,21],oxygen:['Oxygen',100,0,6],trimix:['Trimix 21/35',21,35,0]}[b.dataset.addGas];editableGases().push({id:crypto.randomUUID(),name:preset[0],o2:preset[1],he:preset[2],switchDepth:preset[3],size:11,pressure:200,enabled:true});renderGases();renderSegments();changed();}
  else if(b.dataset.removeGas!==undefined){if(!planPage&&state.gases.length===1)return error(t('请至少保留一种气体。','Keep at least one gas.'));editableGases().splice(Number(b.dataset.removeGas),1);renderGases();renderSegments();changed();}
  else if(b.dataset.removeSegment!==undefined){const rows=editingSegments();if(rows.length===1)return error(t('请至少保留一个分段。','Keep at least one segment.'));rows.splice(Number(b.dataset.removeSegment),1);if(automaticSegments())state.automaticEdited=true;syncHolds();renderSegments();changed();}
  else if(b.dataset.move!==undefined){const rows=editingSegments(),i=Number(b.dataset.move),j=i+Number(b.dataset.direction);[rows[i],rows[j]]=[rows[j],rows[i]];if(automaticSegments())state.automaticEdited=true;syncHolds();renderSegments();changed();}
});
$('#add-segment').addEventListener('click',()=>{const rows=editingSegments(),limit=automaticSegments()?12:24;if(rows.length>=limit)return error(t(`最多 ${limit} 个分段。`,`Up to ${limit} segments are supported.`));const p=rows.at(-1);rows.push({depth:p.depth,duration:10,gas:p.gas,...automaticSegments()?{}:{kind:'hold'}});if(automaticSegments())state.automaticEdited=true;renderSegments();changed();});
$('#reset-example').addEventListener('click',()=>{state=sample();$('#altitude').value=0;renderInputs();changed();if(engine.ready&&!busy){setBusy(true);refreshTimings(true).then(ok=>{setBusy(false);if(ok)form.requestSubmit();});}});
function setBusy(value){busy=value;button.disabled=!engine.ready||value;$('#use-default-rates').disabled=!engine.ready||value;$('#add-segment').disabled=!engine.ready||value;$('#cancel-calculate').hidden=!value;form.setAttribute('aria-busy',String(value));}
form.addEventListener('submit',async event=>{event.preventDefault();if(!engine.ready||busy)return;syncHolds();state.settings=readSettings();const expected=revision;error();clear();setBusy(true);status.textContent=t('正在计算组织负荷…','Calculating tissue loading…');
  try{const request=bottomOnly()
      ? {profileMode:'bottom',bottom:state.bottom,settings:state.settings,gases:state.autoGases}
      : state;
    const computed=await engine.call(visual?'visualize':constantGF?'constant_gf':'plan',request);if(revision!==expected){status.textContent=t('参数已更新，请重新计算。','Inputs changed. Calculate again.');return;}result=computed;renderResult();save();status.textContent=t('计算完成，拖动时间轴查看各时刻。','Complete. Explore each moment with the timeline.');}
  catch(e){
    if(revision===expected){
      if(engine.ready)status.textContent=t('本次计算未完成。','Calculation did not complete.');
      error(e.message);
    }
  }
  finally{setBusy(false);}
});
$('#retry-engine').addEventListener('click',()=>{$('#retry-engine').hidden=true;engine.start();});
$('#cancel-calculate').addEventListener('click',()=>{revision++;engine.fail(t('本次计算已取消，可重新加载。','Calculation cancelled. Reload when ready.'));});
function phase(row){if(result?.settings.ascentMode==='instant' && row.duration===0 && row.depth<row.fromDepth)return t('瞬移上升','Instant ascent');if(row.phase==='gf_ascent')return constantGF?t('连续上升','Continuous ascent'):t('站间上升','Ascent leg');if(row.phase==='switch')return row.decompression?t('减压换气','Deco gas switch'):t('切换气体','Gas switch');if(row.phase==='deco')return t('减压停留','Deco stop');if(row.phase==='safety')return t('附加停留','Optional stop');if(row.phase==='ascent')return t('自动上升','Auto ascent');return row.depth>row.fromDepth?t('下潜','Descent'):row.depth<row.fromDepth?t('上升','Ascent'):t('停留','Hold');}
function renderResult(){const s=result.summary;renderStandardGases();renderGasInfo();renderTimings(result);
  const adaptive=['variable','constant'].includes(result.settings.ascentMode);
  const showPeak=constantGF||visual;
  $('#metric-deco-label').textContent=showPeak?t('最高 GF99','Peak GF99'):t('减压停留','Deco stops');
  $('#metric-deco-unit').textContent=showPeak?'%':t('分钟 · min','minutes · min');
  $('#arrival-gf-heading').hidden=!adaptive;
  $('#leg-rate-heading').hidden=!adaptive;
  for(const [key,value] of Object.entries({depth:s.maxDepth,runtime:s.runtime,deco:showPeak?s.maxGF99:s.decoTime,tts:visual?s.endDepth:s.tts}))$(`#metric-${key}`).textContent=f(value);
  $('#metric-cns').textContent=s.cns===null?t('超出估算范围','Out of range'):f(s.cns)+' %';$('#metric-otu').textContent=f(s.otu);$('#metric-ppo2').textContent=f(s.maxPPO2,2)+' bar';
  $('#profile-caption').textContent=visual?`GF ${f(result.settings.gfLow,0)}/${f(result.settings.gfHigh,0)} · ${(state.useDefaultRates?t('按默认速度连接目标深度','Target depths connected at default speeds'):t('按分段速度模拟','Simulated at per-segment speeds'))}`:`GF ${f(result.settings.gfLow,0)}/${f(result.settings.gfHigh,0)} · ${s.firstStop===null?t('无强制减压停留','No mandatory deco stops'):t('首次减压停留','First deco stop')+' '+f(s.firstStop)+' m'}`;
  if(constantGF)$('#profile-caption').textContent='GF '+f(result.settings.gfLow)+'/'+f(result.settings.gfHigh)+' · '+t('沿减压上限连续上升','Continuous ceiling ascent');
  else if(result.settings.ascentMode==='instant')$('#profile-caption').textContent=t('瞬移上升（测试）','Instant ascent (simulation)')+' · GF '+f(result.settings.gfLow)+'/'+f(result.settings.gfHigh);
  else if(adaptive)$('#profile-caption').textContent='GF '+f(result.settings.gfLow)+'/'+f(result.settings.gfHigh)+' · '+t('站间变速上升','Variable ascent between stations');
  $('#plan-results').hidden=false;$('#export-chart').disabled=false;$('#play-profile').disabled=false;
  $('#plan-warnings').innerHTML=result.warnings.map(w=>`<p class="warning">${esc(w.message)}</p>`).join('');
  const gases=Object.fromEntries(result.gases.map(g=>[g.id,g]));
  $('#schedule-body').innerHTML=result.schedule.map(row=>`<tr class="${row.decompression?'deco':''}"><td>${phase(row)}</td><td>${f(row.depth)}</td><td>${f(row.duration,2)}</td><td>${f(row.runtime,2)}</td><td><span class="gas-pill">${esc(gases[row.gas].name)}</span></td>${adaptive?`<td>${row.meanAscentRate==null?'—':f(row.meanAscentRate,2)}</td><td>${row.targetGF==null?'—':f(row.arrivalGF,1)+'% / '+f(row.targetGF,1)+'%'}</td>`:''}</tr>`).join('');
  $('#gas-summary').innerHTML=result.gases.filter(g=>g.enabled&&(result.gasSource!=='generated'||g.used>0)).map(g=>{const info=result.gasDetails.find(x=>x.id===g.id);return `<div class="gas-use"><strong>${esc(g.name)} <small>O₂ ${f(g.o2)}% / He ${f(g.he)}%</small></strong><span class="${g.remaining<result.settings.reserve?'low':''}">${t('余压','Remaining')} ${f(g.remaining)} bar</span><small>${t('用量','Used')} ${f(g.used,0)} L · ${t('容量','Size')} ${g.cylinderCount?g.cylinderCount+' × ':''}${f(g.size)} L</small><small>MOD ${f(info.mod)} m</small><div class="gas-bar" aria-label="${t('气瓶剩余压力比例','Remaining cylinder pressure')}"><span style="width:${Math.max(0,Math.min(100,g.remaining/g.pressure*100))}%;--gas-color:${COLORS[result.gases.indexOf(g)]}"></span></div></div>`;}).join('');
  profileView.setData(result);
}
function rows(){const adaptive=['variable','constant'].includes(result.settings.ascentMode);const gases=Object.fromEntries(result.gases.map(g=>[g.id,g.name]));return [[t('阶段','Phase'),t('深度(m)','Depth(m)'),t('耗时(min)','Duration(min)'),t('累计(min)','Runtime(min)'),t('气体','Gas'),...adaptive?[t('平均上升速度 (m/min)','Mean ascent (m/min)'),'GF99 (%)',t('目标 GF (%)','Target GF (%)')]:[]],...result.schedule.map(r=>[phase(r),r.depth,r.duration,r.runtime,gases[r.gas],...adaptive?[r.meanAscentRate??'',r.arrivalGF??'',r.targetGF??'']:[]])];}
$('#copy-plan').addEventListener('click',async()=>{if(!result)return;try{await navigator.clipboard.writeText('Dive Vision · '+t('学习模拟','Learning simulation')+'\n'+rows().map(r=>r.join('\t')).join('\n')+'\n'+result.warnings.map(w=>w.message).join('\n'));$('#copy-plan').textContent=t('已复制 ✓','Copied ✓');setTimeout(()=>$('#copy-plan').textContent=t('复制计划','Copy plan'),2000);}catch{error(t('剪贴板不可用，请使用导出 CSV。','Clipboard unavailable. Use Export CSV.'));}});
$('#export-plan').addEventListener('click',()=>{if(!result)return;const cell=x=>'"'+String(x).replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';download('\uFEFF'+[[t('学习模拟，实际潜水前须独立核对。','Learning simulation. Independently verify before real diving.')],...rows(),...result.warnings.map(w=>[w.message])].map(r=>r.map(cell).join(',')).join('\r\n'),'Dive-Vision-plan.csv','text/csv;charset=utf-8');});
const modelButton=document.createElement('button');modelButton.type='button';modelButton.className='text-button';modelButton.id='model-help';modelButton.textContent=t('模型说明','Model notes');$('.page-heading').append(modelButton);modelButton.addEventListener('click',()=>$('#model-dialog').showModal());$('#close-model').addEventListener('click',()=>$('#model-dialog').close());
$('#altitude-convert').addEventListener('click',async()=>{const expected=revision,altitude=$('#altitude').value;try{const r=await engine.call('environment',{altitude});if(expected!==revision||altitude!==$('#altitude').value)return;form.elements.surfacePressure.value=r.surfacePressure.toFixed(5);changed();}catch(e){if(expected===revision&&altitude===$('#altitude').value)error(e.message);}});
addEventListener('pagehide',save);renderInputs();engine.start();
