import {format as f, createCharts, createGFPressureChart,timeAxisTicks} from './charts.js?v=3';
import {t} from './language.js';
const $=selector=>document.querySelector(selector);
export function createProfileView(engine){
  let result=null, playTimer=null;
  let selectedPoint=-1,pointMetricsTimer=null,pointMetricsBusy=false,pointMetricsPending=null;
  const pointMetricsCache=new Map();
  let pressureView=false;
  const gfChart=$('#gf-pressure-chart') && createGFPressureChart($('#gf-pressure-chart'),$('#gf-pressure-legend'),$('#gf-pressure-anchor'));
  const charts=createCharts($('#profile-chart'),$('#tissue-chart'),$('#chart-legend'),selectPoint);
  function stopPlay(){clearInterval(playTimer);playTimer=null;$('#play-profile').textContent=t('▶ 播放','▶ Play');}
  function clearPointInfo(){
    selectedPoint=-1;clearTimeout(pointMetricsTimer);pointMetricsPending=null;pointMetricsCache.clear();
    document.querySelectorAll('#cursor-info dd').forEach(x=>{x.textContent='—';x.classList.remove('low');x.removeAttribute('title');x.removeAttribute('aria-busy');});
    $('#point-info-hint').textContent=t('计算后移动时间游标，查看该时刻的参数。','Calculate, then move the timeline to inspect this moment.');
    $('#point-projection-hint').textContent=projectionHint();
  }
  function elapsedTime(minutes){const seconds=Math.round(minutes*60);return `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
  function renderPointInfo(p,gas){
    const values={depth:`${f(p.depth)} m`,elapsed:elapsedTime(p.time),gas:result.loopId ? gas.name : `[${result.gases.indexOf(gas)+1}] ${gas.name}`,
      pressure:p.setpoint!=null?'—':`${f(p.pressures[gas.id],1)} bar`,ppo2:`${f(p.ppo2,2)} bar`,ppn2:`${f(p.ppn2,2)} bar`,
      gf:`${f(p.gf99)}%`,'surface-gf':`${f(p.surfaceGF)}%`,
      cns:p.cns===null?t('超出估算范围','Out of range'):`${f(p.cns,1)}%`};
    if($('#cursor-setpoint'))values.setpoint=p.setpoint==null?'—':f(p.setpoint,2)+' bar';
    if(p.setpoint!=null)values.gas=result.loopLabel;
    values.ceiling=`${f(p.ceiling,1)} m`;
    for(const [key,value] of Object.entries(values))$(`#cursor-${key}`).textContent=value;
    $('#cursor-gf').classList.toggle('low',p.gf99>100);
    $('#cursor-pressure').classList.toggle('low',p.pressures[gas.id]<result.settings.reserve);
    $('#cursor-cns').classList.toggle('low',p.cns===null||p.cns>100);
    $('#cursor-gf').title=t('当前深度的主导腔隔梯度（GF99）','Leading compartment gradient at the current depth (GF99)');
    $('#cursor-surface-gf').title=t('以当前组织负荷直接到水面时的梯度，不计上升中的排气。','Surface gradient with the current tissue loading, without ascent off-gassing.');
    $('#cursor-ceiling').title=`${t('当前采用的','Current')} GF ${f(p.gf)}%`;
    $('#cursor-ppn2').title=t('呼吸气体的氮分压，不是组织内氮分压。','Nitrogen partial pressure in the breathing gas, not in the tissues.');
    if(p.setpoint!=null){
      $('#point-info-hint').textContent=t('NDL 按当前设定点延长停留，再按计划上升设定点与 GF High 模拟直接上升。','NDL extends the hold on the current setpoint and tests direct ascent at GF High on the planned ascent setpoint.');
      return;
    }
    if(result.settings.ascentMode==='instant'){
      $('#point-info-hint').textContent=t('测试 NDL 按当前组织负荷瞬移到水面，用 GF High 检查上限。','Test NDL checks a zero-time ascent to the surface at GF High.');
      return;
    }
    const ndlGF='GF High '+f(result.settings.gfHigh);
    $('#point-info-hint').textContent=t(
      `NDL：按当前气体、${ndlGF}% 和 ${f(gas.o2>=50?result.settings.decoAscentRate:result.settings.ascentRate)} m/min 连续上升估算，不计换气；≥99 min 表示达到显示上限。`,
      `NDL: current gas, ${ndlGF}% and a continuous ascent at ${f(gas.o2>=50?result.settings.decoAscentRate:result.settings.ascentRate)} m/min, without gas switches; ≥99 min is the display limit.`);
  }
  function projectionHint(){
    if(result?.points[selectedPoint]?.setpoint!=null)return t('@+5 按当前回路设定点再停 5 分钟，然后按计划上升设定点估算上升时间。Δ+5 为其与当前 TTS 之差。','@+5 projects ascent time on the planned ascent setpoint after 5 more minutes on the current setpoint. Δ+5 is the difference from the current TTS.');
    return t('@+5：原深度再停留 5 分钟后的预计上升总时间，不含这 5 分钟。Δ+5 = @+5 − 当前 TTS。按所设 GF、上升速度及已启用减压气体预测，不校验剩余气量；水面为 0。','@+5: time to surface after 5 more minutes at the current depth, excluding those 5 minutes. Δ+5 = @+5 − current TTS. Uses configured GF, ascent rate and enabled deco gases, without checking remaining gas; surface values are 0.');}
  function showPointMetrics(data){
    const ndlOutput=$('#cursor-ndl'),projection=data.projection;
    ndlOutput.textContent=`${data.ndl.capped?'≥':''}${data.ndl.minutes} min`;ndlOutput.removeAttribute('aria-busy');ndlOutput.title=$('#point-info-hint').textContent;
    for(const [id,value,signed] of [['at-plus-five',projection.atPlus5,false],['delta-plus-five',projection.deltaPlus5,true]]){
      const output=$(`#cursor-${id}`),rounded=value===null?null:Math.round(value*10)/10;
      output.textContent=rounded===null?'—':`${signed&&rounded>0?'+':''}${f(rounded,1)} min`;
      output.removeAttribute('aria-busy');
      output.title=value===null?projection.reason:projectionHint();
    }
    $('#point-projection-hint').textContent=projectionHint()+' '+(projection.tts===null?'':t(`当前 TTS：${f(projection.tts,1)} min。`,`Current TTS: ${f(projection.tts,1)} min.`))+(projection.reason?' '+t('预测不可用：','Projection unavailable: ')+projection.reason:'');
  }
  function requestPointMetrics(index){
    clearTimeout(pointMetricsTimer);
    $('#point-projection-hint').textContent=projectionHint();
    if(pointMetricsCache.has(index)){pointMetricsPending=null;showPointMetrics(pointMetricsCache.get(index));return;}
    for(const id of ['ndl','at-plus-five','delta-plus-five']){const output=$(`#cursor-${id}`);output.textContent='…';output.setAttribute('aria-busy','true');output.removeAttribute('title');}
    pointMetricsPending={snapshot:result,index};pointMetricsTimer=setTimeout(calculatePointMetrics,100);
  }
  async function calculatePointMetrics(){
    if(pointMetricsBusy||!pointMetricsPending)return;
    const {snapshot,index}=pointMetricsPending;pointMetricsPending=null;
    if(snapshot!==result)return;
    pointMetricsBusy=true;
    try{
      const p=snapshot.points[index];
      const cc=p.setpoint!=null;
      const data=await engine.call(cc?'cc_point_metrics':'point_metrics',{settings:cc?snapshot.loopSettings:snapshot.settings,point:{depth:p.depth,tissues:p.tissues,gas:p.gas,setpoint:p.setpoint,gfAnchor:p.gfAnchor,gfMode:p.gfMode,stopElapsed:p.stopElapsed,remainingPlanTTS:p.remainingPlanTTS},gases:cc?snapshot.gases.filter(g=>g.id===p.gas):snapshot.gases.filter(g=>g.id!==snapshot.loopId)});
      if(result===snapshot){pointMetricsCache.set(index,data);if(selectedPoint===index)showPointMetrics(data);}
    }catch(e){if(result===snapshot&&selectedPoint===index){for(const id of ['ndl','at-plus-five','delta-plus-five']){const output=$(`#cursor-${id}`);output.textContent='—';output.title=e.message;output.removeAttribute('aria-busy');}$('#point-projection-hint').textContent=projectionHint()+' '+e.message;}}
    finally{pointMetricsBusy=false;if(pointMetricsPending)calculatePointMetrics();}
  }
  function selectPoint(index){if(!result)return;const p=result.points[index],gas=result.gases.find(g=>g.id===p.gas);$('#time-cursor').value=String(p.time);$('#time-cursor').dataset.position=String(result.minuteIndices.indexOf(index));$('#time-cursor').setAttribute('aria-valuetext',`${f(p.time,2)} ${t('分钟','minutes')}`);$('#cursor-time').textContent=`${f(p.time,2)} / ${f(result.summary.runtime,2)} min`;
    selectedPoint=index;renderPointInfo(p,gas);requestPointMetrics(index);
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
  const selectedCharts=new Set(['depth']);
  function showChartView(){
    $('#profile-chart').hidden=pressureView;$('#chart-legend').hidden=pressureView;
    if(gfChart)$('#gf-pressure-view').hidden=!pressureView;
    $('#open-gf-window')?.setAttribute('aria-pressed',String(pressureView));
    document.querySelectorAll('[data-chart]').forEach(x=>x.setAttribute('aria-pressed',String(!pressureView&&selectedCharts.has(x.dataset.chart))));
    charts.setModes([...selectedCharts]);gfChart?.redraw();
  }
  for(const b of document.querySelectorAll('[data-chart]'))b.addEventListener('click',()=>{
    if(pressureView){pressureView=false;selectedCharts.add(b.dataset.chart);}
    else if(selectedCharts.has(b.dataset.chart)){if(selectedCharts.size===1)return;selectedCharts.delete(b.dataset.chart);}
    else selectedCharts.add(b.dataset.chart);
    showChartView();
  });
  $('#open-gf-window')?.addEventListener('click',()=>{pressureView=!pressureView;showChartView();});
  const chartResize=new ResizeObserver(()=>{charts.redraw();gfChart?.redraw();renderTimeline();});chartResize.observe($('#profile-chart'));if(gfChart)chartResize.observe($('#gf-pressure-chart'));chartResize.observe($('#timeline-scroll'));addEventListener('themechange',()=>{charts.redraw();gfChart?.redraw();});
  $('#export-chart').addEventListener('click',()=>{const svg=$(pressureView?'#gf-pressure-chart svg':'#profile-chart svg');if(svg)download(svg.outerHTML,pressureView?'Dive-Vision-GF-pressure.svg':'Dive-Vision-profile.svg','image/svg+xml');});
  showChartView();
  addEventListener('pagehide',stopPlay);
  return {
    setData(data){
      stopPlay();clearPointInfo();result=data;
      $('#play-profile').disabled=false;$('#export-chart').disabled=false;
      renderTimeline();charts.setData(result);gfChart?.setData(result);selectPoint(result.minuteIndices.at(-1));
    },
    clear(){
      stopPlay();result=null;charts.clear();gfChart?.clear();clearPointInfo();
      $('#time-cursor').disabled=true;$('#minute-ticks').replaceChildren();$('#cursor-time').textContent='—';
      $('#export-chart').disabled=true;$('#play-profile').disabled=true;$('#compartment-grid').replaceChildren();
    }
  };
}
export function download(contents,name,type){const url=URL.createObjectURL(new Blob([contents],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
