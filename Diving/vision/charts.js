import {t,lang} from './language.js';
export const COLORS = ['#168fca', '#24b59b', '#9272d1', '#eca44d', '#e5799b', '#648bc3', '#77a752', '#ca8b62'];
export const escapeHTML = value => String(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
export const format = (value, digits = 1) => Number.isFinite(Number(value)) ? Number(value).toLocaleString(lang==='en'?'en-US':'zh-CN', {maximumFractionDigits:digits}) : '—';
const svgText = (x,y,text,anchor='middle',fill=getComputedStyle(document.documentElement).getPropertyValue('--chart-label').trim()) => `<text x="${x}" y="${y}" text-anchor="${anchor}" fill="${fill}" font-size="10" font-family="sans-serif">${escapeHTML(text)}</text>`;
const legendItem = (color,text) => `<span><i style="--swatch:${color}"></i>${escapeHTML(text)}</span>`;

// Only the displayed labels are thinned; the cursor still uses minute snapshots.
export function timeAxisTicks(duration, width) {
  if (!(duration > 0)) return [0];
  const intervals=Math.max(2,Math.min(10,Math.floor(width/64)));
  const minimum=duration/intervals, scale=10**Math.floor(Math.log10(Math.max(1,minimum)));
  const step=[1,2,5,10].map(value=>value*scale).find(value=>value>=minimum);
  const ticks=[];
  for(let time=0;time<duration-1e-8;time+=step)ticks.push(time);
  // Reserve room for the actual end time, including fractional minutes.
  while(ticks.length>1 && (duration-ticks.at(-1))/duration*width<40)ticks.pop();
  ticks.push(duration);
  return ticks;
}

export function createCharts(profile, tissue, legend, onSelect) {
  let result = null, mode = 'depth', cursor = 0, plot = null;
  function pick(event) {
    if (!result || !plot) return;
    const box=profile.querySelector('svg').getBoundingClientRect();
    const x=(event.clientX-box.left)*plot.width/box.width;
    const time=Math.max(0,Math.min(1,(x-plot.left)/plot.innerWidth))*result.summary.runtime;
    let best=result.minuteIndices[0];
    for(const index of result.minuteIndices)if(Math.abs(result.points[index].time-time)<Math.abs(result.points[best].time-time))best=index;
    onSelect(best);
  }
  profile.addEventListener('pointerdown', event => { if (!result) return; profile.setPointerCapture(event.pointerId); pick(event); });
  profile.addEventListener('pointermove', event => { if (event.buttons) pick(event); });
  function drawProfile() {
    if (!result) return;
    const width=Math.max(280,profile.clientWidth), height=300, left=44, right=16, top=25, bottom=35;
    const innerWidth=width-left-right, innerHeight=height-top-bottom;
    plot={width,left,innerWidth};
    const theme=getComputedStyle(document.documentElement),paper=theme.getPropertyValue('--paper').trim(),line=theme.getPropertyValue('--line').trim();
    const points=result.points, gases=result.gases.filter(gas=>gas.enabled);
    let minimum=0, maximum, series, unit, invert=false;
    if (mode==='depth') {
      maximum=Math.max(10,Math.ceil(result.summary.maxDepth/5)*5); invert=true; unit=t('深度 / m','Depth / m');
      series=[{color:COLORS[0],label:t('潜水深度','Depth'),values:points.map(p=>p.depth),fill:true}];
      if(result.mode==='visualize'){
        series.push({color:'#e7a04d',label:t('GF High 上限','GF High ceiling'),values:points.map(p=>p.ceilingHigh),dash:true},{color:COLORS[2],label:t('GF Low 上限','GF Low ceiling'),values:points.map(p=>p.ceilingLow),dash:true});
        maximum=Math.max(maximum,Math.ceil(Math.max(...points.map(p=>p.ceilingLow))/5)*5);
      }else series.push({color:'#e7a04d',label:t('减压上限','Ceiling'),values:points.map(p=>p.ceiling),dash:true});
    } else if (mode==='pressure') {
      const values=points.flatMap(point=>gases.map(gas=>point.pressures[gas.id]));
      maximum=Math.max(50,Math.ceil(Math.max(...values)/50)*50); minimum=Math.min(0,Math.floor(Math.min(...values)/50)*50); unit=t('气瓶压力 / bar','Cylinder pressure / bar');
      series=gases.map(gas=>({color:COLORS[result.gases.indexOf(gas)%COLORS.length],label:gas.name,values:points.map(p=>p.pressures[gas.id])}));
      series.push({color:'#dda253',label:t('预留压力','Reserve'),values:points.map(()=>result.settings.reserve),dash:true});
    } else if(mode==='gf99'){
      maximum=Math.max(100,Math.ceil(result.summary.maxGF99/20)*20);unit='GF99 / %';
      series=[{color:COLORS[2],label:'GF99',values:points.map(p=>p.gf99)},{color:'#e7a04d',label:t('M 值 · 100%','M-value · 100%'),values:points.map(()=>100),dash:true}];
    } else {
      maximum=Math.max(1.8,Math.ceil(result.summary.maxPPO2*5)/5); unit='PPO₂ / bar';
      series=[{color:COLORS[1],label:t('氧分压','PPO₂'),values:points.map(p=>p.ppo2)},{color:'#e7a04d',label:t('底部上限','Working limit'),values:points.map(()=>result.settings.ppo2Work),dash:true},{color:'#c58b88',label:t('减压上限','Deco limit'),values:points.map(()=>result.settings.ppo2Deco),dash:true}];
    }
    const x=time=>left+time/result.summary.runtime*innerWidth;
    const y=value=>top+(invert?(value-minimum)/(maximum-minimum):1-(value-minimum)/(maximum-minimum))*innerHeight;
    let body='';
    for (let i=0;i<=5;i++) {
      const value=minimum+(maximum-minimum)*i/5, yy=y(value);
      body+=`<line x1="${left}" y1="${yy}" x2="${width-right}" y2="${yy}" stroke="${line}" stroke-dasharray="3 4"/>`+svgText(left-9,yy+3,format(value), 'end');

    }
    for(const minute of timeAxisTicks(result.summary.runtime,innerWidth)){
      const xx=x(minute);body+=`<line x1="${xx}" x2="${xx}" y1="${height-bottom}" y2="${height-bottom+5}" stroke="${line}"/>`+svgText(xx,height-12,format(minute,2),minute===result.summary.runtime?'end':'middle');
    }
    body+=svgText(left,12,unit,'start')+svgText(width-right,height-1,t('时间 / min','Time / min'),'end');
    for (const seriesItem of series) {
      const coordinates=points.map((point,index)=>`${x(point.time).toFixed(2)},${y(seriesItem.values[index]).toFixed(2)}`).join(' ');
      if (seriesItem.fill) body+=`<polygon points="${left},${y(0)} ${coordinates} ${x(result.summary.runtime)},${y(0)}" fill="${theme.getPropertyValue('--chart-fill').trim()}" opacity=".65"/>`;
      body+=`<polyline points="${coordinates}" fill="none" stroke="${seriesItem.color}" stroke-width="${seriesItem.dash?1.5:2.3}" ${seriesItem.dash?'stroke-dasharray="5 4"':''} stroke-linejoin="round"/>`;
    }
    const point=points[cursor], xx=x(point.time);
    body+=`<line x1="${xx}" x2="${xx}" y1="${top}" y2="${height-bottom}" stroke="#456f89" stroke-width="1" stroke-dasharray="3 3"/>`;
    for (const item of series.filter(item=>!item.dash)) body+=`<circle cx="${xx}" cy="${y(item.values[cursor])}" r="4" fill="${paper}" stroke="${item.color}" stroke-width="2"/>`;
    profile.innerHTML=`<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeHTML(unit)} ${t('随时间变化','over time')}" style="min-width:${width}px" viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" fill="${paper}"/>${body}</svg>`;
    legend.innerHTML=series.map(item=>legendItem(item.color,item.label)).join('');
  }
  function drawTissues() {
    if (!result) return;
    const width=Math.max(320,tissue.clientWidth),height=364,left=28,right=48,top=22,bottom=70;
    const point=result.points[cursor],rows=point.tissues;
    const theme=getComputedStyle(document.documentElement);
    const color=name=>theme.getPropertyValue(name).trim();
    const innerWidth=width-left-right,plotHeight=height-top-bottom,pitch=plotHeight/16;
    const ambientX=left+innerWidth*.3,mX=left+innerWidth*.9,endX=left+innerWidth;
    // Python provides the normalized loading. Only convert it to chart geometry.
    const x=value=>left+innerWidth*(value<=1?.3*Math.max(0,value):value<=2?.3+.6*(value-1):.9+.1*Math.min(value-2,1));
    let body=`<rect x="${left}" y="${top}" width="${innerWidth*.3}" height="${plotHeight}" fill="${color('--tissue-green')}"/><rect x="${ambientX}" y="${top}" width="${innerWidth*.6}" height="${plotHeight}" fill="${color('--tissue-yellow')}"/><rect x="${mX}" y="${top}" width="${innerWidth*.1}" height="${plotHeight}" fill="${color('--tissue-red')}"/>`;
    body+=svgText(width-2,12,'GF','end');
    rows.forEach((row,index)=>{
      const y=top+index*pitch,barEnd=x(point.tissueLoading[index]),gf=point.tissueGF[index];
      const detail=`${t('腔隔','Compartment')} ${index+1} · N₂ ${format(row[0],3)} bar · He ${format(row[1],3)} bar · ${t('M 值','M-value')} ${format(row[2],3)} bar · GF ${format(gf)}%`;
      body+=`<g class="tissue-load-row"><title>${escapeHTML(detail)}</title><rect x="${left}" y="${y+3}" width="${Math.max(0,barEnd-left)}" height="${pitch-6}" rx="1" fill="${color('--tissue-bar')}" opacity=".8"/>`;
      body+=svgText(left-8,y+pitch/2+3,String(index+1).padStart(2,'0'),'end');
      body+=svgText(width-2,y+pitch/2+3,gf>0?`${format(gf)}%`:'','end');
      if(point.tissueLoading[index]>3)body+=`<path d="M ${endX-6} ${y+4} l 4 ${pitch/2-4} l -4 ${pitch/2-4}" fill="none" stroke="${color('--tissue-line')}" stroke-width="1.5"/>`;
      body+='</g>';
    });
    for(const boundary of [ambientX,mX])body+=`<line x1="${boundary}" x2="${boundary}" y1="${top}" y2="${height-bottom}" stroke="${color('--tissue-line')}" opacity=".55"/>`;
    const inspiredX=x(point.inspiredInertRatio);
    body+=`<line class="inspired-inert-line" x1="${inspiredX}" x2="${inspiredX}" y1="${top}" y2="${height-bottom}" stroke="${color('--tissue-line')}" stroke-width="1.5" stroke-dasharray="4 3"/>`;
    body+=svgText(ambientX+4,height-bottom+16,t('环境压力','Ambient pressure'),'start')+svgText(ambientX+4,height-bottom+31,`${format(point.ambient,3)} bar`,'start');
    body+=svgText(mX+3,height-bottom+16,t('M 值','M-value'),'start')+svgText(mX+3,height-bottom+31,'GF 100%','start');
    body+=`<line x1="${left}" x2="${left+16}" y1="${height-9}" y2="${height-9}" stroke="${color('--chart-label')}" stroke-dasharray="4 3"/>`;
    body+=svgText(left+22,height-5,`${t('吸入惰性气体','Inspired inert gas')} ${format(point.inspiredInertRatio*100)}% · ${format(point.inspiredInert,3)} bar`,'start');
    tissue.innerHTML=`<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${t('十六组组织归一化负荷，时间','Sixteen normalized tissue loadings at')} ${format(point.time,2)} min" viewBox="0 0 ${width} ${height}">${body}</svg>`;
  }
  return {
    setData(data) {result=data;cursor=0;drawProfile();drawTissues();},
    select(index) {cursor=index;drawProfile();drawTissues();},
    setMode(value) {mode=value;drawProfile();},
    redraw() {drawProfile();drawTissues();},
    clear() {result=null;legend.innerHTML='';profile.innerHTML=`<div class="empty-state"><div class="empty-waves" aria-hidden="true">≈</div><strong>${t('等待新的计算','Ready to explore')}</strong><p>${t('设置参数后点击计算。','Set your parameters and calculate.')}</p></div>`;tissue.innerHTML=`<p class="chart-placeholder">${t('完成计算后显示组织压力。','Calculate to view tissue pressures.')}</p>`;}
  };
}
