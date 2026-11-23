import {PythonEngine} from './engine.js';
import {createProfileView} from './profile-view.js';
import {t} from './language.js';
import {escapeHTML as esc, format as f} from './charts.js';

const $ = selector => document.querySelector(selector);
const form = $('#cc-form');
const calculate = $('#calculate-cc');
const status = $('#engine-status');

const main = $('#cc-main-result');
const emergency = $('#cc-bailout-result');
const error = $('#cc-error');
const storageKey = 'dive-vision-cc-plan-v1';
const presets = {air:[21,0,''], trimix:[18,45,''], ean50:[50,0,21], oxygen:[100,0,6]};
function cylinder(preset) {
  const [o2,he,switchDepth] = presets[preset];
  return {o2, he, switchDepth, size:11, pressure:200};
}
let cylinders = [cylinder('air'), cylinder('ean50')];
let revision = 0;
let busy = false;
const caption = $('#profile-caption');
const initialCaption = caption.textContent;
let currentPlan = null;
try {
  const draft = JSON.parse(localStorage.getItem(storageKey));
  if (Array.isArray(draft?.cylinders) && draft.cylinders.length <= 8 && draft.cylinders.every(g=>g && typeof g==='object')) {
    cylinders = draft.cylinders;
    if (draft.fields?.setpoint && !draft.fields.setpointHigh) {
      const old = Number(draft.fields.setpoint);
      if (old >= .7 && old <= 1.6) draft.fields.setpointHigh = old;
      else if (old >= .4 && old < .7) Object.assign(draft.fields,{setpointLow:old,spSwitch:'low'});
    }
    if (draft.fields?.spSwitch === 'low' && !('setpointDeco' in draft.fields)) draft.fields.setpointDeco = '';
    for (const [name,value] of Object.entries(draft.fields || {})) {
      const field = form.elements.namedItem(name);
      if (field) field.value = value;
    }
  }
} catch {}

const gasFields = [
  ['o2','O₂','%',1,100], ['he','He','%',0,99],
  ['size',t('容量','Size'),'L',1,50], ['pressure',t('初始压力','Start pressure'),'bar',1,350],
  ['switchDepth',t('切换深度','Switch depth'),'m',0,150]
];
function renderCylinders() {
  $('#cc-cylinders').innerHTML = cylinders.map((gas,index) => {
    const label=t('应急气瓶','Bailout cylinder')+' '+(index+1);
    const fields=gasFields.map(([key,name,unit,min,max])=>`<label>${name} <span>${unit}</span><input data-field="${key}" type="number" step="any" min="${min}" max="${max}" value="${esc(gas[key]??'')}"></label>`).join('');
    return `<div class="gas-card" data-index="${index}"><div class="section-heading"><strong>${label}</strong>
      <button type="button" class="icon-button" data-remove="${index}" aria-label="${t('删除','Remove')} ${label}">×</button></div><div class="gas-fields">${fields}</div></div>`;
  }).join('');
  form.querySelectorAll('[data-mix]').forEach(btn=>btn.disabled=cylinders.length>=8);
}
function syncSwitchDepth() {
  const enabled = form.elements.spSwitch.value === 'descent';
  $('#sp-depth-field').hidden = !enabled;
  form.elements.spDepth.disabled = !enabled;
}
function invalidate() {
  revision++;
  error.hidden = true;
  main.hidden = emergency.hidden = true;
  currentPlan = null;
  profileView.clear();
  caption.textContent = initialCaption;
  updateBranchButtons('cc');
  syncSwitchDepth();
  if(engine.ready) status.textContent=t('输入已更新，请重新计算。','Inputs changed. Calculate again.');
  try {localStorage.setItem(storageKey,JSON.stringify({fields:Object.fromEntries(new FormData(form)),cylinders}));} catch {}
}
form.addEventListener('input', ({target})=>{
  if(target.dataset.field) cylinders[Number(target.closest('[data-index]').dataset.index)][target.dataset.field]=target.value;
  invalidate();
});
form.addEventListener('click',event=>{
  const btn=event.target.closest('button');
  if(!btn)return;
  if(btn.dataset.mix) cylinders.push(cylinder(btn.dataset.mix));
  else if(btn.dataset.remove!==undefined) cylinders.splice(Number(btn.dataset.remove),1);
  else return;
  renderCylinders();
  invalidate();
});

function timeSummary(data) {
  return `<p class="cc-metrics"><span>${t('出水时间','Surface runtime')} <strong>${f(data.surfaceTime,2)} min</strong></span>
    <span>TTS <strong>${f(data.tts,2)} min</strong></span><span>${t('减压停留','Deco stops')} <strong>${f(data.decoTime,2)} min</strong></span></p>`;
}
const phases = {descent:t('下潜','Descent'),hold:t('底部停留','Bottom hold'),ascent:t('上升','Ascent'),deco:t('减压停留','Deco stop'),switch:t('换气','Gas switch')};
function schedule(data,names) {
  const rows=data.schedule.map(row=>`<tr><td>${phases[row.phase]}</td><td>${f(row.depth,2)}</td><td>${f(row.duration,2)}</td><td>${f(row.runtime,2)}</td><td>${row.setpoint != null ? 'CC · '+f(row.setpoint,2)+' bar' : esc(names[row.gas]||row.gas)}</td></tr>`).join('');
  return `<div class="table-wrap"><table><thead><tr><th>${t('阶段','Phase')}</th><th>${t('深度','Depth')} (m)</th><th>${t('耗时','Duration')} (min)</th><th>${t('累计','Runtime')} (min)</th><th>${t('气体','Gas')}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
const branchButtons = [...document.querySelectorAll('[data-profile-view]')];
function updateBranchButtons(view) {
  for (const button of branchButtons) {
    button.disabled = !currentPlan || (button.dataset.profileView === 'bailout' && !currentPlan.bailout.available);
    button.setAttribute('aria-pressed',String(button.dataset.profileView === view));
  }
}
function showProfile(view) {
  const {cc,bailout} = currentPlan;
  const onLoop = view === 'cc';
  const data = onLoop ? cc : bailout;
  const points = onLoop ? cc.profilePoints : [
    ...cc.profilePoints.filter(p=>p.time < bailout.startTime - 1e-8), ...bailout.profilePoints
  ];
  const minutes = new Map();
  points.forEach((point,i)=>{
    const minute = Math.round(point.time);
    if (Math.abs(point.time-minute)<1e-8) minutes.set(minute,i);
  });
  const minuteIndices = [...minutes.values()];
  if (minuteIndices.at(-1)!==points.length-1) minuteIndices.push(points.length-1);
  const comparison = bailout.available && {
    label:onLoop?'OC bailout':t('CC 主计划','CC main plan'),
    points:onLoop?bailout.profilePoints:cc.profilePoints.filter(p=>p.time >= bailout.startTime - 1e-8)
  };
  const gas = cc.inventory[0];
  const loopLabel = gas.he ? 'CC · Tx'+f(gas.o2)+'/'+f(gas.he) : 'CC · '+t('稀释气','Diluent')+' O₂ '+f(gas.o2)+'%';
  updateBranchButtons(view);
  caption.textContent = (onLoop?t('CC 主计划','CC main plan'):'OC bailout')+' · GF '+f(data.settings.gfLow)+'/'+f(data.settings.gfHigh);
  profileView.setData({mode:'plan',points,minuteIndices,settings:data.settings,loopSettings:cc.settings,
    gases:onLoop?cc.inventory:[...cc.inventory,...bailout.inventory],loopId:gas.id,loopLabel,comparison,
    summary:{runtime:data.surfaceTime,maxDepth:Math.max(...points.map(p=>p.depth)),
      maxGF99:Math.max(...points.map(p=>p.gf99))}});
}
for (const button of branchButtons) button.addEventListener('click',()=>showProfile(button.dataset.profileView));
function render(result) {
  currentPlan=result;
  const {cc,bailout:bo}=result;
  showProfile('cc');
  main.innerHTML=`<h2>${t('CC 主计划','CC main plan')}</h2>${timeSummary(cc)}
    <p class="hint">PPO₂ Low / High / Deco ${f(cc.setpointLow,2)} / ${f(cc.setpointHigh,2)} / ${f(cc.settings.setpointDeco ?? cc.bottomSetpoint,2)} bar · ${t('底部稀释气 pO₂','Diluent pO₂ at depth')} ${f(cc.diluentPPO2,2)} bar · ${t('水面模拟回路 pO₂','Modeled surface loop pO₂')} ${f(cc.surfaceLoopPPO2,2)} bar</p>
    ${cc.diluentPPO2>cc.bottomSetpoint?`<p class="warning">${t('底部稀释气氧分压高于设定点。冲洗回路时会偏离此恒定设定点模拟。','Diluent pO₂ at depth exceeds the setpoint. A diluent flush would depart from this constant-setpoint simulation.')}</p>`:''}
    ${schedule(cc,{})}`;
  main.hidden=false;
  emergency.innerHTML='<h2>OC bailout</h2>';
  emergency.hidden=false;
  if(!bo.available) {
    emergency.insertAdjacentHTML('beforeend',`<p class="warning">${esc(bo.reason)}</p>`);
    return;
  }
  const branch=t('切换时刻','Bailout runtime')+' '+f(bo.startTime,2)+' min · '+f(bo.startDepth,2)+' m · '+esc(bo.initialGas);
  const low=bo.gases.some(g=>g.shortfall>0);
  const gasUsage=bo.gases.map(g=>`<tr><td>${esc(g.name)}</td><td>${f(g.used,0)}</td><td>${f(g.remaining,1)}</td><td class="${g.shortfall>0?'low':''}">${f(g.shortfall,1)}</td></tr>`).join('');
  emergency.insertAdjacentHTML('beforeend',`<p>${branch}</p>${low?`<p class="warning">${t('所填气瓶无法覆盖此上升的耗气量和预留量。下表列出各瓶缺口。','The cylinders do not cover this ascent and the specified reserve. See each shortfall below.')}</p>`:''}
    ${timeSummary(bo)}${schedule(bo,Object.fromEntries(bo.gases.map(g=>[g.id,g.name])))}
    <h3>${t('应急气量','Bailout gas')}</h3><div class="table-wrap"><table><thead><tr><th>${t('气瓶','Cylinder')}</th><th>${t('用量','Used')} (L)</th><th>${t('预计余压','End pressure')} (bar)</th><th>${t('含预留缺口','Shortfall incl. reserve')} (L)</th></tr></thead><tbody>${gasUsage}</tbody></table></div>`);
}
const engine = new PythonEngine(status,()=>{
  calculate.disabled=false;
  $('#retry-engine').hidden=true;
  form.requestSubmit();
},()=>{calculate.disabled=true;$('#retry-engine').hidden=false;});
const profileView = createProfileView(engine);
function namedCylinder(g,index){
  const label=Number(g.he)>0?`Tx${g.o2}/${g.he}`:Number(g.o2)===21?'Air':Number(g.o2)===100?'O₂':`EAN${g.o2}`;
  return {...g,id:'bo-'+index,name:`[${index+1}] ${label}`};
}
form.addEventListener('submit',async(event)=>{
  event.preventDefault();
  if(!engine.ready||busy)return;
  const expected=revision, fields=Object.fromEntries(new FormData(form));
  const {depth,duration,diluentO2,diluentHe,setpointLow,setpointHigh,setpointDeco,spSwitch,spDepth,fo2Limit,bailoutTime,bailoutSCR,...settings}=fields;
  busy=true; calculate.disabled=true; error.hidden=true;
  status.textContent=t('正在计算…','Calculating…');
  try {
    const result=await engine.call('cc_plan',{depth,duration,diluentO2,diluentHe,setpointLow,setpointHigh,setpointDeco,spSwitch,spDepth,fo2Limit,bailoutTime,bailoutSCR,settings,gases:cylinders.map(namedCylinder)});
    if(expected!==revision)return;
    render(result);
    status.textContent=t('计算完成。','Calculation complete.');
  } catch(e) {
    if(expected===revision){error.textContent=e.message;error.hidden=false;if(engine.ready) status.textContent=t('本次计算未完成。','Calculation did not complete.');}
  } finally {busy=false;calculate.disabled=!engine.ready;}
});
$('#retry-engine').addEventListener('click',()=>engine.start());
renderCylinders();
syncSwitchDepth();
updateBranchButtons('cc');
engine.start();
