import {t,lang} from './language.js';
// Cylinder colors are shared by the input cards, pressure curves and gas summary.
export const COLORS = ['#e58b25', '#c746c6', '#30a4ae', '#c66041', '#788d35', '#bd7495', '#427ab5', '#967552'];
// Reserve a distinct color for every profile curve, including reference lines.
// These fixed assignments keep colors stable as layers or gases are toggled.
const PROFILE_COLORS = {
  depth: '#168fca', gf99: '#855ad6',
  ceilingHigh: '#d64d70', ceilingLow: '#a38a13', mValue: '#5364bb'
};
export const escapeHTML = value => String(value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
export const format = (value, digits = 1) => Number.isFinite(Number(value)) ? Number(value).toLocaleString(lang==='en'?'en-US':'zh-CN', {maximumFractionDigits:digits}) : '—';
const svgText = (x,y,text,anchor='middle',fill=getComputedStyle(document.documentElement).getPropertyValue('--chart-label').trim()) => `<text x="${x}" y="${y}" text-anchor="${anchor}" fill="${fill}" font-size="10" font-family="sans-serif">${escapeHTML(text)}</text>`;
let tissuePatternSequence=0;
const legendItem = (color,text,dash=false) => `<span><i class="${dash?'dashed':''}" style="--swatch:${color}"></i>${escapeHTML(text)}</span>`;

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
  const heliumPatternId=`tissue-he-hatch-${++tissuePatternSequence}`;
  let result = null, modes = ['depth'], cursor = 0, plot = null;
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
  function profileAxis(mode) {
    const points=result.points;
    let minimum=0,maximum,series,unit,title,color,invert=false;
    if(mode==='depth'){
      maximum=Math.max(10,Math.ceil(result.summary.maxDepth/5)*5);invert=true;unit='m';title=t('深度','Depth');color=PROFILE_COLORS.depth;
      series=[{color,label:t('潜水深度','Depth'),values:points.map(p=>p.depth),fill:true}];
      if(result.mode==='visualize'){
        series.push({color:PROFILE_COLORS.ceilingHigh,label:t('GF High 上限','GF High ceiling'),values:points.map(p=>p.ceilingHigh),dash:true},{color:PROFILE_COLORS.ceilingLow,label:t('GF Low 上限','GF Low ceiling'),values:points.map(p=>p.ceilingLow),dash:true});
        maximum=Math.max(maximum,Math.ceil(Math.max(...points.map(p=>p.ceilingLow))/5)*5);
      }else series.push({color:PROFILE_COLORS.ceilingHigh,label:t('减压上限','Ceiling'),values:points.map(p=>p.ceiling),dash:true});
    }else if(mode==='gf99'){
      maximum=Math.max(100,Math.ceil(result.summary.maxGF99/20)*20);unit='%';title='GF99';color=PROFILE_COLORS.gf99;
      series=[{color,label:'GF99',values:points.map(p=>p.gf99)},{color:PROFILE_COLORS.mValue,label:t('M 值','M-value'),values:points.map(()=>100),dash:true}];

    }
    return {mode,minimum,maximum,series,unit,title,color,invert};
  }
  function drawProfile() {
    if(!result)return;
    const axes=modes.map(profileAxis),left=44,axisGap=54,right=axes.length===1?16:axes.length*axisGap-14;
    const width=Math.max(left+right+230,profile.clientWidth),height=320,top=44,bottom=36;
    const innerWidth=width-left-right,innerHeight=height-top-bottom;
    plot={width,left,innerWidth};
    const theme=getComputedStyle(document.documentElement),paper=theme.getPropertyValue('--paper').trim(),line=theme.getPropertyValue('--line').trim();
    const points=result.points,x=time=>left+time/result.summary.runtime*innerWidth;
    for(const axis of axes)axis.y=value=>top+(axis.invert?(value-axis.minimum)/(axis.maximum-axis.minimum):1-(value-axis.minimum)/(axis.maximum-axis.minimum))*innerHeight;
    let body='';
    for(let i=0;i<=5;i++){
      const yy=top+innerHeight*i/5;
      body+=`<line x1="${left}" y1="${yy}" x2="${width-right}" y2="${yy}" stroke="${line}" stroke-dasharray="3 4"/>`;
    }
    axes.forEach((axis,index)=>{
      const axisX=index===0?left:width-right+(index-1)*axisGap,anchor=index===0?'end':'start',labelX=axisX+(index===0?-7:7);
      body+=`<g class="profile-axis" data-axis="${axis.mode}"><line x1="${axisX}" x2="${axisX}" y1="${top}" y2="${height-bottom}" stroke="${axis.color}" opacity=".65"/>`;
      body+=svgText(axisX,13,axis.title,'middle',axis.color)+svgText(axisX,28,axis.unit,'middle',axis.color);
      for(let i=0;i<=5;i++){
        const value=axis.minimum+(axis.maximum-axis.minimum)*i/5,yy=axis.y(value);
        body+=`<line x1="${axisX}" x2="${axisX+(index===0?-4:4)}" y1="${yy}" y2="${yy}" stroke="${axis.color}"/>`+svgText(labelX,yy+3,format(value,2),anchor,axis.color);
      }
      body+='</g>';
    });
    for(const minute of timeAxisTicks(result.summary.runtime,innerWidth)){
      const xx=x(minute);body+=`<line x1="${xx}" x2="${xx}" y1="${height-bottom}" y2="${height-bottom+5}" stroke="${line}"/>`+svgText(xx,height-14,format(minute,2),minute===result.summary.runtime?'end':'middle');
    }
    body+=svgText(width-right,height-1,t('时间 / min','Time / min'),'end');
    for(const axis of axes){
      body+=`<g class="profile-series" data-axis="${axis.mode}">`;
      for(const item of axis.series){
        const coordinates=points.map((point,index)=>`${x(point.time).toFixed(2)},${axis.y(item.values[index]).toFixed(2)}`).join(' ');
        if(item.fill)body+=`<polygon points="${left},${axis.y(0)} ${coordinates} ${x(result.summary.runtime)},${axis.y(0)}" fill="${theme.getPropertyValue('--chart-fill').trim()}" opacity="${axes.length>1?.2:.65}"/>`;
        body+=`<polyline points="${coordinates}" fill="none" stroke="${item.color}" stroke-width="${item.dash?1.4:2.3}" ${item.dash?'stroke-dasharray="5 4"':''} stroke-linejoin="round"/>`;
      }
      body+='</g>';
    }
    const xx=x(points[cursor].time);
    body+=`<line class="profile-cursor" x1="${xx}" x2="${xx}" y1="${top}" y2="${height-bottom}" stroke="${theme.getPropertyValue('--chart-label').trim()}" stroke-width="1" stroke-dasharray="3 3"/>`;
    for(const axis of axes)for(const item of axis.series.filter(item=>!item.dash))body+=`<circle cx="${xx}" cy="${axis.y(item.values[cursor])}" r="4" fill="${paper}" stroke="${item.color}" stroke-width="2"/>`;
    const description=axes.map(axis=>`${axis.title} (${axis.unit})`).join(' · ');
    profile.innerHTML=`<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeHTML(description)} ${t('随时间变化','over time')}" style="min-width:${width}px" viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" fill="${paper}"/>${body}</svg>`;
    legend.innerHTML=axes.flatMap(axis=>axis.series.map(item=>legendItem(item.color,`${item.label} · ${format(item.values[cursor],2)} ${axis.unit}`,item.dash))).join('');
  }
  function drawTissues() {
    if (!result || !tissue) return;
    const width=Math.max(320,tissue.clientWidth),height=364,left=28,right=48,top=22,bottom=70;
    const point=result.points[cursor],rows=point.tissues;
    const theme=getComputedStyle(document.documentElement);
    const color=name=>theme.getPropertyValue(name).trim();
    const innerWidth=width-left-right,plotHeight=height-top-bottom,pitch=plotHeight/16;
    const ambientX=left+innerWidth*.3,mX=left+innerWidth*.9,endX=left+innerWidth;
    // Python provides the normalized loading. Only convert it to chart geometry.
    const x=value=>left+innerWidth*(value<=1?.3*Math.max(0,value):value<=2?.3+.6*(value-1):.9+.1*Math.min(value-2,1));
    let body=`<rect x="${left}" y="${top}" width="${innerWidth*.3}" height="${plotHeight}" fill="${color('--tissue-green')}"/><rect x="${ambientX}" y="${top}" width="${innerWidth*.6}" height="${plotHeight}" fill="${color('--tissue-yellow')}"/><rect x="${mX}" y="${top}" width="${innerWidth*.1}" height="${plotHeight}" fill="${color('--tissue-red')}"/>`;
    body+=`<defs><pattern id="${heliumPatternId}" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="${color('--tissue-he')}" opacity=".08"/><path d="M -1 1 L 1 -1 M 0 6 L 6 0 M 5 7 L 7 5" fill="none" stroke="${color('--tissue-he')}" stroke-width="1.35"/></pattern></defs>`;
    body+=svgText(width-2,12,'GF','end');
    rows.forEach((row,index)=>{
      const y=top+index*pitch,barEnd=x(point.tissueLoading[index]),gf=point.tissueGF[index];
      const detail=`${t('腔隔','Compartment')} ${index+1} · N₂ ${format(row[0],3)} bar · He ${format(row[1],3)} bar · ${t('M 值','M-value')} ${format(row[2],3)} bar · GF ${format(gf)}%`;
      // Keep the original total-length mapping. Split its screen length by
      // Python's tissue-pressure fractions; the divider is not a new ceiling.
      const totalWidth=Math.max(0,barEnd-left),fractions=point.tissueGasFractions[index];
      const nitrogenWidth=totalWidth*fractions[0],heliumWidth=totalWidth*fractions[1],barY=y+3,barHeight=pitch-6;
      body+=`<g class="tissue-load-row"><title>${escapeHTML(detail)}</title>`;
      if(nitrogenWidth>0)body+=`<rect data-gas="n2" x="${left}" y="${barY}" width="${nitrogenWidth}" height="${barHeight}" fill="${color('--tissue-bar')}" opacity=".9"><title>${escapeHTML(t('氮气','Nitrogen'))} N₂: ${format(row[0],3)} bar</title></rect>`;
      if(heliumWidth>0){
        body+=`<rect data-gas="he" x="${left+nitrogenWidth}" y="${barY}" width="${heliumWidth}" height="${barHeight}" fill="url(#${heliumPatternId})"><title>${escapeHTML(t('氦气','Helium'))} He: ${format(row[1],3)} bar</title></rect>`;
        // Inset the border so even tiny helium contributions keep their true width.
        const border=Math.min(1,heliumWidth,barHeight);
        body+=`<rect class="tissue-he-outline" x="${left+nitrogenWidth+border/2}" y="${barY+border/2}" width="${Math.max(0,heliumWidth-border)}" height="${barHeight-border}" fill="none" stroke="${color('--tissue-he')}" stroke-width="${border}" pointer-events="none"/>`;
      }
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
    tissue.innerHTML=`<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${t('十六组组织归一化负荷，实色为氮气、条纹为氦气，时间','Sixteen normalized tissue loadings: solid nitrogen, hatched helium, at')} ${format(point.time,2)} min" viewBox="0 0 ${width} ${height}">${body}</svg>`;
  }
  return {
    setData(data) {result=data;cursor=0;drawProfile();drawTissues();},
    select(index) {cursor=index;drawProfile();drawTissues();},
    setModes(values) {const selected=['depth','gf99'].filter(mode=>values.includes(mode));modes=selected.length?selected:['depth'];drawProfile();},
    redraw() {drawProfile();drawTissues();},
    clear() {result=null;legend.innerHTML='';profile.innerHTML=`<div class="empty-state"><div class="empty-waves" aria-hidden="true">≈</div><strong>${t('等待新的计算','Ready to explore')}</strong><p>${t('设置参数后点击计算。','Set your parameters and calculate.')}</p></div>`;if(tissue)tissue.innerHTML=`<p class="chart-placeholder">${t('完成计算后显示组织压力。','Calculate to view tissue pressures.')}</p>`;}
  };
}


// This subview has pressure axes; it must never reuse the time-chart hit target.
export function createGFPressureChart(container, legend, note) {
  let data=null;
  function draw(){
    if(!data)return;
    const width=Math.max(320,container.clientWidth),height=360,left=48,right=18,top=32,bottom=45;
    const theme=getComputedStyle(document.documentElement),paper=theme.getPropertyValue('--paper').trim(),grid=theme.getPropertyValue('--line').trim(),label=theme.getPropertyValue('--chart-label').trim();
    const xmax=Math.ceil(data.maximumPressure*2)/2,ymax=Math.ceil(Math.max(data.mValue[1][1],...data.high.map(row=>row[1]))*2)/2;
    const x=p=>left+p/xmax*(width-left-right),y=p=>height-bottom-p/ymax*(height-top-bottom);
    const lowColor='#bb9418',highColor='#d64d70',combinedColor='#159d99';
    const lowLabel=`GF ${format(data.gfLow)}`,highLabel=`GF ${format(data.gfHigh)}`,combinedLabel=`GF ${format(data.gfLow)}/${format(data.gfHigh)}`;
    let body='';
    for(let i=0;i<=5;i++){
      const xx=x(xmax*i/5),yy=y(ymax*i/5);
      body+=`<line x1="${left}" x2="${width-right}" y1="${yy}" y2="${yy}" stroke="${grid}" stroke-dasharray="3 4"/>`;
      body+=svgText(left-7,yy+3,format(ymax*i/5,2),'end')+svgText(xx,height-bottom+16,format(xmax*i/5,2));
    }
    body+=svgText(left,14,t('组织惰性气体分压 / bar','Tissue inert-gas pressure / bar'),'start');
    body+=svgText(width-right,height-3,t('环境绝对压力 / bar','Ambient absolute pressure / bar'),'end');
    const line=(id,points,color,dash='',weight=2)=>`<polyline data-gf-line="${id}" points="${points.map(([px,py])=>`${x(px)},${y(py)}`).join(' ')}" fill="none" stroke="${color}" stroke-width="${weight}" ${dash?`stroke-dasharray="${dash}"`:''}/>`;
    body+=line('ambient',data.ambient,label,'4 4',1)+line('m-value',data.mValue,'#85859b','2 4',1);
    body+=`<line x1="${x(data.surfacePressure)}" x2="${x(data.surfacePressure)}" y1="${top}" y2="${height-bottom}" stroke="${label}" opacity=".4" stroke-dasharray="2 4"/>`;
    body+=line('low',data.low,lowColor,'7 4')+line('high',data.high,highColor,'3 3');
    if(data.combined.length){
      body+=line('combined',data.combined,combinedColor,'',3);
      for(const [i,[px,py]] of data.combined.entries())body+=`<circle cx="${x(px)}" cy="${y(py)}" r="4" fill="${paper}" stroke="${combinedColor}" stroke-width="2"><title>${escapeHTML(i===0?t('水面 GF High','Surface GF High'):t('GF Low 起点','GF Low anchor'))}: ${format(px,3)} bar</title></circle>`;
    }
    container.innerHTML=`<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeHTML(t('GF 压力关系示意图','GF pressure reference diagram'))}" viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" fill="${paper}"/>${body}</svg>`;
    legend.innerHTML=legendItem(lowColor,lowLabel,true)+legendItem(highColor,highLabel,true)+legendItem(combinedColor,combinedLabel+t(' · 端点连线',' · endpoint chord'))+legendItem(label,t('环境压力线','Ambient pressure'),true)+legendItem('#85859b',t('M 值线','M-value'),true);
    const anchor=data.anchorSource==='plan'?t('计划 GF Low 起点','Plan GF Low anchor'):t('GF Low 参考起点','Reference GF Low anchor');
    note.textContent=data.combined.length?`${anchor} ${format(data.anchorDepth,2)} m (${format(data.anchorPressure,3)} bar) → ${t('水面','surface')} ${format(data.surfacePressure,3)} bar · ${t('参数基准','Reference snapshot')} ${format(data.basisTime,2)} min`:
      t('本剖面没有正深度的 GF Low 起点，因此不绘制 Low/High 连线。','This profile has no positive-depth GF Low anchor, so no Low/High chord is drawn.');
  }
  return {setData(result){data=result.gfPressure;draw();},redraw:draw,clear(){data=null;container.innerHTML=`<p class="chart-placeholder">${t('计算后显示 GF 压力关系。','Calculate to view GF pressure relationships.')}</p>`;legend.innerHTML='';note.textContent='';}};
}
