"""Educational open-circuit, single-dive ZHL-16C / GF simulation.

Equations and coefficient provenance: see MODEL.md. All planning arithmetic is
performed here; the browser only renders the returned data. Not a dive computer.
"""
import json
import math
from itertools import combinations

WATER_VAPOUR = 0.0627
N2_HALF = (4,8,12.5,18.5,27,38.3,54.3,77,109,146,187,239,305,390,498,635)
HE_HALF = (1.51,3.02,4.72,6.99,10.21,14.48,20.53,29.11,41.20,55.19,70.69,90.34,115.29,147.42,188.24,240.03)
N2_A = (1.2599,1,.8618,.7562,.6200,.5043,.4410,.4000,.3750,.3500,.3295,.3065,.2835,.2610,.2480,.2327)
N2_B = (.5050,.6514,.7222,.7825,.8126,.8434,.8693,.8910,.9092,.9222,.9319,.9403,.9477,.9544,.9602,.9653)
HE_A = (1.7424,1.3830,1.1919,1.0458,.9220,.8205,.7305,.6502,.5950,.5545,.5333,.5189,.5181,.5176,.5172,.5119)
HE_B = (.4245,.5747,.6527,.7223,.7582,.7957,.8279,.8553,.8757,.8903,.8997,.9073,.9122,.9171,.9217,.9267)
N2_K = tuple(math.log(2)/half for half in N2_HALF)
HE_K = tuple(math.log(2)/half for half in HE_HALF)
DEFAULTS = dict(gfLow=50,gfHigh=70,surfacePressure=1.01325,density=1.03,
                ascentRate=10,descentRate=18,switchTime=0,sacWork=16,sacDeco=12,
                ppo2Work=1.4,ppo2Deco=1.6,reserve=50,lastStop=3,safetyStop=0)
# NOAA single-exposure limits, PO2 in atmospheres (not bar).
OXYGEN_LIMITS = ((.6,720),(.7,570),(.8,450),(.9,360),(1,300),(1.1,240),
                 (1.2,210),(1.3,180),(1.4,150),(1.5,120),(1.6,45))


def number(value, label, low, high):
    if isinstance(value, bool): raise ValueError(f'{label}必须是数字。')
    try: value = float(value)
    except (TypeError, ValueError): raise ValueError(f'{label}必须是数字。') from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label}须在 {low:g}–{high:g} 范围内。')
    return value


def load_tissues(tissues, start_pressure, end_pressure, minutes, fractions):
    """Exact Schreiner update for a constant inspired-pressure slope."""
    if minutes <= 0: return list(tissues)
    pressure_rate = (end_pressure-start_pressure)/minutes
    result = []
    for i, initial in enumerate(tissues):
        values = []
        for old, fraction, k in zip(initial, fractions, (N2_K[i], HE_K[i])):
            inspired = fraction*(start_pressure-WATER_VAPOUR)
            rate = fraction*pressure_rate
            values.append(inspired + rate*(minutes-1/k) - (inspired-old-rate/k)*math.exp(-k*minutes))
        result.append(tuple(max(0, value) for value in values))
    return result


def coefficients(tissues):
    for i, (nitrogen, helium) in enumerate(tissues):
        total = nitrogen+helium
        if total < 1e-12: yield total, N2_A[i], N2_B[i]
        else: yield total, (N2_A[i]*nitrogen+HE_A[i]*helium)/total, (N2_B[i]*nitrogen+HE_B[i]*helium)/total


def ceiling(tissues, gf):
    return max((total-gf*a)/(1-gf+gf/b) for total,a,b in coefficients(tissues))


def tissue_loading(total, ambient, m_value):
    """Piecewise display coordinate: 0 = empty, 1 = ambient, 2 = M-value.

    Values above 2 retain their magnitude so the chart can report exceedances.
    This coordinate is for visualization only and never drives the dive plan.
    """
    return total/ambient if total <= ambient else 1+(total-ambient)/(m_value-ambient)


def surface_gf(tissues, pressure):
    return max(0, max((total-pressure)/(a+pressure/b-pressure)*100 for total,a,b in coefficients(tissues)))


def oxygen_rate(ppo2_bar):
    ata = ppo2_bar/1.01325
    otu = ((ata-.5)/.5)**(5/6) if ata > .5 else 0
    if ata > 1.6+1e-9: return None, otu
    if ata < .6: return 0, otu
    for (left, left_limit), (right, right_limit) in zip(OXYGEN_LIMITS, OXYGEN_LIMITS[1:]):
        if ata <= right:
            limit = left_limit+(right_limit-left_limit)*(ata-left)/(right-left)
            return 100/limit, otu
    return 100/45, otu


def validate(payload, *, mode='plan'):
    settings = dict(DEFAULTS)
    limits = dict(gfLow=(1,100),gfHigh=(1,100),surfacePressure=(.6,1.1),density=(.95,1.1),
                  ascentRate=(1,18),descentRate=(1,30),switchTime=(0,5),sacWork=(1,100),
                  sacDeco=(1,100),ppo2Work=(.5,1.6),ppo2Deco=(.5,1.6),reserve=(0,150),
                  lastStop=(3,6),safetyStop=(0,5))
    raw = payload.get('settings', {})
    for key, (low, high) in limits.items():
        settings[key] = number(raw.get(key,settings[key]), key, low, high)
    if settings['gfLow'] > settings['gfHigh']: raise ValueError('GF Low 不能大于 GF High。')
    if settings['lastStop'] not in (3,6): raise ValueError('末站深度只能为 3 m 或 6 m。')
    if settings['ppo2Work'] > settings['ppo2Deco']: raise ValueError('底部氧分压上限不能大于减压氧分压上限。')
    gases = []
    raw_gases = payload.get('gases', [])
    if not isinstance(raw_gases,list) or not 1 <= len(raw_gases) <= 8: raise ValueError('请设置 1–8 种气体。')
    for row in raw_gases:
        gas = dict(id=str(row.get('id',''))[:40],name=str(row.get('name','Gas'))[:40],enabled=row.get('enabled',True) is True)
        for key,low,high in [('o2',1,100),('he',0,99),('size',1,50),('pressure',1,350),('switchDepth',0,150)]:
            gas[key] = number(row.get(key,0), gas['name']+' '+key,low,high)
        if gas['o2']+gas['he'] > 100: raise ValueError(f"{gas['name']} 的氧气与氦气比例之和不能超过 100%。")
        if not gas['id'] or any(item['id']==gas['id'] for item in gases): raise ValueError('气体编号重复或缺失。')
        gas['fractions'] = ((100-gas['o2']-gas['he'])/100,gas['he']/100)
        gases.append(gas)
    segments = []
    raw_segments = segment_timings(dict(payload,settings=settings,mode=mode))['segments']
    if not isinstance(raw_segments,list) or not 1 <= len(raw_segments) <= 24: raise ValueError('请设置 1–24 个潜水分段。')
    if payload.get('useDefaultRates') is True and 'waypoints' in payload:
        for i,row in enumerate(payload['waypoints']):
            if not any(g['id']==str(row.get('gas','')) and g['enabled'] for g in gases):
                raise ValueError(f'第 {i+1} 段引用了停用或不存在的气体。')
    for i,row in enumerate(raw_segments):
        gas_id = str(row.get('gas',''))
        if not any(g['id']==gas_id and g['enabled'] for g in gases): raise ValueError(f'第 {i+1} 段引用了停用或不存在的气体。')
        segments.append(dict(depth=number(row.get('depth'),f'第 {i+1} 段深度',0,150),duration=number(row.get('duration'),f'第 {i+1} 段耗时',.000001,180),gas=gas_id))
    if sum(row['duration'] for row in segments) > 360: raise ValueError('计划分段总时长不能超过 360 分钟。')
    if max(row['depth'] for row in segments) == 0: raise ValueError('至少一个分段的深度须大于 0。')
    return settings,gases,segments


class Simulation:
    def __init__(self, settings, gases):
        self.settings = settings
        self.gases = {gas['id']:gas for gas in gases}
        self.surface = settings['surfacePressure']
        self.metre = settings['density']*.0980665
        self.tissues = [(.7902*(self.surface-WATER_VAPOUR),0)]*16
        self.time = self.depth = 0.0
        self.anchor = None
        self.visualization = False
        self.gf_mode = 'high'
        self.used = {gas['id']:0.0 for gas in gases}
        self.cns = self.otu = self.max_ppo2 = 0.0
        self.cns_known = True
        self.points, self.schedule, self.warnings = [],[],[]
        self.warning_keys = set()

    def pressure(self, depth): return self.surface+depth*self.metre

    def gf(self, depth):
        low,high = self.settings['gfLow']/100,self.settings['gfHigh']/100
        if self.anchor is not None and self.anchor > 0: return high-(high-low)*min(1,max(0,depth/self.anchor))
        return low if self.gf_mode=='low' else high

    def warn(self, code, text, key=None):
        key = key or code
        if key not in self.warning_keys:
            self.warning_keys.add(key)
            self.warnings.append(dict(code=code,message=text))

    def record(self, gas, phase, *, time=None, depth=None, tissues=None, used=None, cns=None, cns_known=None):
        time=self.time if time is None else time
        if abs(time-round(time))<1e-8: time=float(round(time))
        depth=self.depth if depth is None else depth
        tissues=self.tissues if tissues is None else tissues
        used=self.used if used is None else used
        cns=self.cns if cns is None else cns
        cns_known=self.cns_known if cns_known is None else cns_known
        ambient = self.pressure(depth)
        inspired_inert = (ambient-WATER_VAPOUR)*sum(gas['fractions'])
        self.points.append(dict(time=time,depth=depth,ambient=ambient,phase=phase,gas=gas['id'],
            ceiling=max(0,(ceiling(tissues,self.gf(depth))-self.surface)/self.metre),
            ceilingLow=max(0,(ceiling(tissues,self.settings['gfLow']/100)-self.surface)/self.metre),
            ceilingHigh=max(0,(ceiling(tissues,self.settings['gfHigh']/100)-self.surface)/self.metre),
            gf=self.gf(depth)*100,gf99=surface_gf(tissues,ambient),
            tissueGF=[(total-ambient)/(a+ambient/b-ambient)*100 for total,a,b in coefficients(tissues)],
            surfaceGF=surface_gf(tissues,self.surface),ppo2=ambient*gas['o2']/100,
            ppn2=ambient*gas['fractions'][0],cns=cns if cns_known else None,
            inspiredInert=inspired_inert,inspiredInertRatio=inspired_inert/ambient,
            tissueLoading=[tissue_loading(total,ambient,a+ambient/b) for total,a,b in coefficients(tissues)],
            tissueGasFractions=[(n/(n+h),h/(n+h)) if n+h>0 else (0,0) for n,h in tissues],
            tissues=[[n,h,a+ambient/b] for (n,h),(_,a,b) in zip(tissues,coefficients(tissues))],
            pressures={key:self.gases[key]['pressure']-volume/self.gases[key]['size'] for key,volume in used.items()}))

    def advance(self, depth, duration, gas, phase):
        if duration <= 1e-9:
            if phase=='switch':
                self.record(gas,phase)
                self.schedule.append(dict(phase=phase,fromDepth=self.depth,depth=self.depth,duration=0,runtime=self.time,gas=gas['id'],decompression=self.anchor is not None))
            return
        if self.time+duration > 1080: raise ValueError('模拟超过 1080 分钟，请缩短潜水时长或调整参数。')
        start_depth, start_time = self.depth,self.time
        manual_ascent = phase=='segment' and depth < start_depth
        previous_mode = self.gf_mode
        if manual_ascent and not self.visualization and not self.can_ascend(0,gas): self.gf_mode='low'
        steps = max(1,math.ceil(duration*(60 if manual_ascent else 6)))
        dt = duration/steps
        limit = self.settings['ppo2Work'] if phase=='segment' else self.settings['ppo2Deco']
        rmv = self.settings['sacWork'] if phase=='segment' else self.settings['sacDeco']
        for i in range(steps):
            target = start_depth+(depth-start_depth)*(i+1)/steps
            p0,p1 = self.pressure(self.depth),self.pressure(target)
            po2 = (p0+p1)/2*gas['o2']/100
            cns,otu = oxygen_rate(po2)
            # Add exact minute snapshots without altering the integration grid,
            # schedule, oxygen accumulation or subsequent tissue state.
            next_time=start_time+dt*(i+1)
            for minute in range(math.floor(self.time+1e-8)+1,math.ceil(next_time-1e-8)):
                elapsed=minute-self.time
                minute_depth=self.depth+(target-self.depth)*elapsed/dt
                minute_pressure=self.pressure(minute_depth)
                minute_tissues=load_tissues(self.tissues,p0,minute_pressure,elapsed,gas['fractions'])
                minute_used=dict(self.used)
                minute_used[gas['id']]+=rmv*(p0+minute_pressure)/2*elapsed
                self.record(gas,phase,time=minute,depth=minute_depth,tissues=minute_tissues,used=minute_used,
                            cns=self.cns+(cns or 0)*elapsed,cns_known=self.cns_known and cns is not None)
            self.tissues = load_tissues(self.tissues,p0,p1,dt,gas['fractions'])
            self.used[gas['id']] += rmv*(p0+p1)/2*dt
            self.max_ppo2 = max(self.max_ppo2,max(p0,p1)*gas['o2']/100)
            if cns is None: self.cns_known=False
            else: self.cns += cns*dt
            self.otu += otu*dt
            if max(p0,p1)*gas['o2']/100 > limit+1e-8:
                self.warn('oxygen',f"{gas['name']} 在部分深度超过所设氧分压上限。",'oxygen-'+gas['id'])
            if min(p0,p1)*gas['o2']/100 < .16:
                self.warn('hypoxia',f"{gas['name']} 在部分深度的氧分压低于 0.16 bar。",'hypoxia-'+gas['id'])
            self.depth = target
            self.time = start_time+dt*(i+1)
            if phase=='segment' and p1+1e-6 < ceiling(self.tissues,self.gf(target)):
                if self.visualization: self.warn('ceiling','设定分段越过了 GF High 的减压上限；本页仅展示该剖面，不自动修正上升。')
                else: raise ValueError('手动分段穿越了当前 GF 的减压上限。请在更深处结束分段，让程序自动生成上升计划。')
            if not manual_ascent or i%10==0 or i==steps-1 or abs(self.time-round(self.time))<1e-8: self.record(gas,phase)
        self.gf_mode=previous_mode
        row = dict(phase=phase,fromDepth=start_depth,depth=depth,duration=duration,runtime=self.time,gas=gas['id'],decompression=phase=='deco' or (phase=='switch' and self.anchor is not None))
        previous = self.schedule[-1] if self.schedule else None
        if previous and previous['phase']==phase and previous['gas']==gas['id'] and phase in ('deco','ascent') and (phase=='ascent' or previous['depth']==depth):
            previous['depth']=depth
            previous['duration']+=duration
            previous['runtime']=self.time
        else: self.schedule.append(row)

    def can_ascend(self, target, gas):
        # Require the next stop to be permitted by the departure tissues too;
        # this matches the published DecoTengu stop-release convention.
        if (self.anchor is not None or self.gf_mode=='low') and self.pressure(target)+1e-8 < ceiling(self.tissues,self.gf(target)):
            return False
        duration = (self.depth-target)/self.settings['ascentRate']
        steps = max(1,math.ceil(duration*60))
        tissues = self.tissues
        depth = self.depth
        for i in range(steps):
            next_depth = self.depth+(target-self.depth)*(i+1)/steps
            tissues = load_tissues(tissues,self.pressure(depth),self.pressure(next_depth),duration/steps,gas['fractions'])
            if self.pressure(next_depth)+1e-8 < ceiling(tissues,self.gf(next_depth)): return False
            depth = next_depth
        return True

    def best_gas(self, current):
        choices = [gas for gas in self.gases.values() if gas['enabled'] and gas['o2']>current['o2'] and self.depth<=gas['switchDepth']+1e-7 and .16<=self.pressure(self.depth)*gas['o2']/100<=self.settings['ppo2Deco']+1e-8]
        return max(choices,key=lambda gas:gas['o2']) if choices else current

    def next_depth(self, gas):
        target = max(0,math.floor((self.depth-1e-7)/3)*3)
        if target < self.settings['lastStop']: target=0
        switch_depths = [g['switchDepth'] for g in self.gases.values() if g['enabled'] and g['o2']>gas['o2'] and (self.gf_mode!='low' or g['switchDepth']>=self.settings['lastStop']) and target<g['switchDepth']<self.depth-1e-7 and self.pressure(g['switchDepth'])*g['o2']/100<=self.settings['ppo2Deco']+1e-8]
        return max([target]+switch_depths)

    def refresh_ascent_mode(self, gas):
        if self.gf_mode=='high' and not self.can_ascend(0,gas):
            self.gf_mode='low'
            if self.depth < self.settings['lastStop']:
                raise ValueError('最后一段浅于设定末站，且仍需减压。请在更深处结束手动分段。')
            if self.pressure(self.depth)+1e-8 < ceiling(self.tissues,self.settings['gfLow']/100):
                raise ValueError('最后一段已浅于 GF Low 允许的首站深度。请在更深处结束手动分段。')
            for candidate in self.gases.values():
                if candidate['enabled'] and candidate['o2']>gas['o2'] and candidate['switchDepth']<self.settings['lastStop']:
                    self.warn('switch',f"{candidate['name']} 的切换深度浅于末站 {self.settings['lastStop']:g} m，自动减压不使用该换气点。",'switch-'+candidate['id'])

    def ascend(self, gas):
        # A no-stop ascent is assessed at GF High before searching the GF Low anchor.
        self.refresh_ascent_mode(gas)
        safety_pending = self.settings['safetyStop'] > 0 and self.depth >= 5 and self.gf_mode=='high'
        while self.depth > 1e-7:
            switch_dwell=0
            chosen = self.best_gas(gas)
            # Locate an obligation before a gas-switch dwell can clear it.
            # A switch at a required stop is part of the decompression wait.
            if self.gf_mode=='low' and self.anchor is None and not self.can_ascend(self.next_depth(chosen),chosen):
                self.anchor=self.depth
            if chosen['id'] != gas['id']:
                gas=chosen
                switch_dwell=self.settings['switchTime']
                self.advance(self.depth,switch_dwell,gas,'switch')
            self.refresh_ascent_mode(gas)
            safety_pending=safety_pending and self.gf_mode=='high'
            target=self.next_depth(gas)
            if safety_pending and target<5<=self.depth: target=5
            if safety_pending and abs(self.depth-5)<1e-7:
                self.advance(5,self.settings['safetyStop'],gas,'safety')
                safety_pending=False
                self.refresh_ascent_mode(gas)
                target=self.next_depth(gas)
            if self.gf_mode=='low' and self.anchor is None and not self.can_ascend(target,gas):
                self.anchor=self.depth
            # Once decompression starts, stop for at least one minute at each
            # station. Gas-switch dwell at the same depth counts toward it.
            if self.anchor is not None and switch_dwell < 1:
                self.advance(self.depth,1-switch_dwell,gas,'deco')
            while not self.can_ascend(target,gas):
                self.advance(self.depth,1,gas,'deco')
            self.advance(target,(self.depth-target)/self.settings['ascentRate'],gas,'ascent')
        return gas


def ndl(payload):
    """Remaining whole minutes on the current gas, followed by a no-stop ascent.

    Reuse the planner's one-second ascent checks at GF High, with no gas switch.
    Search each whole minute to avoid assuming monotonic mixed-gas loading.
    99 is a display/search cap, not an assertion of unlimited no-stop time.
    """
    raw=payload.get('settings',{})
    settings=dict(DEFAULTS)
    for key,low,high in [('gfHigh',1,100),('surfacePressure',.6,1.1),('density',.95,1.1),('ascentRate',1,18)]:
        settings[key]=number(raw.get(key,settings[key]),key,low,high)
    point=payload.get('point',{})
    depth=number(point.get('depth'),'depth',0,150)
    rows=point.get('tissues',[])
    if not isinstance(rows,list) or len(rows)!=16 or any(not isinstance(row,(list,tuple)) or len(row)<2 for row in rows):
        raise ValueError('NDL requires 16 tissue compartments.')
    tissues=[(number(row[0],'N2',0,100),number(row[1],'He',0,100)) for row in rows]
    raw_gas=payload.get('gas',{})
    o2=number(raw_gas.get('o2'),'O2',1,100)
    he=number(raw_gas.get('he'),'He',0,99)
    if o2+he>100: raise ValueError('O2 + He must not exceed 100%.')
    gas=dict(id='current',o2=o2,he=he,fractions=((100-o2-he)/100,he/100))
    probe=Simulation(settings,[gas])
    probe.depth=depth
    probe.tissues=tissues
    ambient=probe.pressure(depth)
    for elapsed in range(100):
        if ceiling(probe.tissues,settings['gfHigh']/100)>ambient+1e-8 or not probe.can_ascend(0,gas):
            return dict(minutes=max(0,elapsed-1),capped=False,ascentRate=settings['ascentRate'])
        if elapsed<99:
            probe.tissues=load_tissues(probe.tissues,ambient,ambient,1,gas['fractions'])
    return dict(minutes=99,capped=True,ascentRate=settings['ascentRate'])


def gas_details(settings, gases):
    metre=settings['density']*.0980665
    return [dict(id=g['id'],n2=100-g['o2']-g['he'],mod=max(0,(settings['ppo2Work']/(g['o2']/100)-settings['surfacePressure'])/metre),
                 decoMod=max(0,(settings['ppo2Deco']/(g['o2']/100)-settings['surfacePressure'])/metre)) for g in gases]


def plan(payload, auto_ascent=True):
    settings,gases,segments=validate(payload,mode='plan' if auto_ascent else 'vision')
    simulation=Simulation(settings,gases)
    simulation.visualization=not auto_ascent
    current=simulation.gases[segments[0]['gas']]
    simulation.record(current,'start')
    for segment in segments:
        gas=simulation.gases[segment['gas']]
        if gas['id'] != current['id']:
            if auto_ascent: simulation.advance(simulation.depth,settings['switchTime'],gas,'switch')
            else: simulation.record(gas,'switch')
        rate=(segment['depth']-simulation.depth)/segment['duration']
        if auto_ascent and rate > settings['descentRate']+1e-8: simulation.warn('descent','手动分段的下降速度超过设定上限。')
        if auto_ascent and -rate > settings['ascentRate']+1e-8: simulation.warn('ascent','手动分段的上升速度超过设定上限。')
        simulation.advance(segment['depth'],segment['duration'],gas,'segment')
        current=gas
    ascent_start=simulation.time
    if auto_ascent: simulation.ascend(current)
    gas_results=[]
    for gas in gases:
        used=simulation.used[gas['id']]
        remaining=gas['pressure']-used/gas['size']
        gas_results.append({key:value for key,value in gas.items() if key!='fractions'} | dict(used=used,remaining=remaining))
        if used and remaining < settings['reserve']:
            detail='气量不足' if remaining < 0 else '低于预留压力'
            simulation.warn('gas',f"{gas['name']} {detail}：理论余压 {remaining:.1f} bar，预留 {settings['reserve']:g} bar。",'gas-'+gas['id'])
    if not simulation.cns_known: simulation.warn('cns-range','部分氧分压超出 NOAA 单次暴露表范围，CNS 无法完整估算。')
    elif simulation.cns > 100: simulation.warn('cns','本次模拟的 CNS 氧暴露估算超过 100%。')
    deco=sum(row['duration'] for row in simulation.schedule if row['decompression'])
    integer_points={int(round(point['time'])):i for i,point in enumerate(simulation.points) if abs(point['time']-round(point['time']))<1e-8}
    minute_indices=[integer_points[minute] for minute in range(math.floor(simulation.time+1e-8)+1)]
    if minute_indices[-1]!=len(simulation.points)-1: minute_indices.append(len(simulation.points)-1)
    result=dict(mode='plan' if auto_ascent else 'visualize',settings=settings,gases=gas_results,gasDetails=gas_details(settings,gases),
                segments=segments,points=simulation.points,minuteIndices=minute_indices,schedule=simulation.schedule,warnings=simulation.warnings,
                summary=dict(runtime=simulation.time,maxDepth=max(row['depth'] for row in segments),
                    decoTime=deco,tts=simulation.time-ascent_start,firstStop=next((row['depth'] for row in simulation.schedule if row['decompression'] and row['duration']>0),None),
                    gfAnchor=simulation.anchor,cns=simulation.cns if simulation.cns_known else None,otu=simulation.otu,
                    gasUsed=sum(simulation.used.values()),maxPPO2=simulation.max_ppo2,
                    maxGF99=max(point['gf99'] for point in simulation.points),
                    endDepth=simulation.depth))
    if payload.get('useDefaultRates') is True and 'waypoints' in payload:
        result['waypointTimings']=waypoint_timings(dict(payload,mode='plan' if auto_ascent else 'vision'))['waypointTimings']
    result['gfPressure']=gf_pressure_diagram(result)
    return result


def sac(payload):
    size=number(payload.get('size'), '气瓶容量',1,50)
    start=number(payload.get('start'),'起始压力',0,350)
    end=number(payload.get('end'),'结束压力',0,350)
    duration=number(payload.get('duration'),'潜水时长',.1,600)
    depth=number(payload.get('depth'),'平均深度',0,150)
    surface=number(payload.get('surfacePressure',1.01325),'水面气压',.6,1.1)
    density=number(payload.get('density',1.03),'水密度',.95,1.1)
    if end>=start: raise ValueError('结束压力须小于起始压力。')
    ambient=surface+depth*density*.0980665
    return dict(sac=size*(start-end)/duration/ambient,ambient=ambient,
                usedLitres=size*(start-end),pressureDrop=start-end,pressureRate=(start-end)/duration/ambient)


def waypoints_from_segments(segments):
    """Pair a movement with its following hold only when depth and gas match."""
    waypoints=[]
    previous_moving=False
    for row in segments:
        moving=row['kind']!='hold'
        if not moving and previous_moving and waypoints[-1]['depth']==row['depth'] and waypoints[-1]['gas']==row['gas']:
            waypoints[-1]['duration']=row['duration']
        else:
            waypoints.append(dict(depth=row['depth'],duration=0 if moving else row['duration'],gas=row['gas']))
        previous_moving=moving
    return waypoints


def waypoint_timings(payload):
    """Expand depth/hold targets into physical movement and hold segments."""
    rows=payload.get('waypoints')
    if not isinstance(rows,list) or not 1<=len(rows)<=12:
        raise ValueError('默认速度模式请设置 1–12 个目标深度。')
    mode=payload.get('mode','vision')
    if mode not in ('plan','vision'): raise ValueError('Invalid segment timing mode.')
    settings=payload.get('settings',{})
    previous=0
    segments=[]
    timings=[]
    waypoints=[]
    for i,row in enumerate(rows):
        depth=number(row.get('depth'),f'第 {i+1} 段深度',0,150)
        hold=number(row.get('duration'),f'第 {i+1} 段耗时',0,180)
        gas=str(row.get('gas',''))
        travel=0
        if depth!=previous:
            kind='descent' if depth>previous else 'ascent'
            key=kind+'Rate'
            rate=number(settings.get(key,DEFAULTS[key]) if mode=='plan' else DEFAULTS[key],key,1,30 if kind=='descent' else 18)
            travel=number(abs(depth-previous)/rate,f'第 {i+1} 段耗时',.000001,180)
            segments.append(dict(depth=depth,duration=travel,rate=rate,gas=gas,kind=kind))
        if hold>0:
            segments.append(dict(depth=depth,duration=hold,rate=None,gas=gas,kind='hold'))
        waypoints.append(dict(depth=depth,duration=hold,gas=gas))
        timings.append(dict(travelTime=travel,totalTime=travel+hold))
        previous=depth
    return dict(segments=segments,waypoints=waypoints,waypointTimings=timings,useDefaultRates=True)


def segment_timings(payload):
    """Resolve travel time in Python without adding any arrival/rounding dwell.

    Old plan durations take precedence over cached rates; visual segments use
    their explicit rates. The global switch overrides legacy per-row choices.
    """
    if payload.get('useDefaultRates') is True and 'waypoints' in payload:
        return waypoint_timings(payload)
    rows=payload.get('segments',[])
    if not isinstance(rows,list) or not 1<=len(rows)<=24:
        raise ValueError('请设置 1–24 个潜水分段。')
    mode=payload.get('mode','vision')
    if mode not in ('plan','vision'): raise ValueError('Invalid segment timing mode.')
    settings=payload.get('settings',{})
    has_global='useDefaultRates' in payload
    global_default=payload.get('useDefaultRates')
    if has_global and not isinstance(global_default,bool):
        raise ValueError('Default speed must be enabled or disabled.')
    previous=0
    segments=[]
    for i,row in enumerate(rows):
        depth=number(row.get('depth'),f'第 {i+1} 段深度',0,150)
        inferred='descent' if depth>previous else 'ascent' if depth<previous else 'hold'
        kind=(row.get('kind') or inferred) if mode=='vision' else inferred
        valid=(kind=='hold' and depth==previous or kind=='descent' and depth>previous or kind=='ascent' and depth<previous)
        if not valid: raise ValueError('分段类型与目标深度不一致：停留须保持上一深度，下潜须更深，上升须更浅。')
        default_rate=global_default if has_global else row.get('useDefaultRate',False)
        if not isinstance(default_rate,bool): raise ValueError('Default speed must be enabled or disabled.')
        if kind=='hold':
            duration=number(row.get('duration'),f'第 {i+1} 段耗时',.000001,180)
            rate=None
        elif default_rate:
            key=kind+'Rate'
            raw_rate=settings.get(key,DEFAULTS[key]) if mode=='plan' else DEFAULTS[key]
            rate=number(raw_rate,key,1,30 if kind=='descent' else 18)
            duration=number(abs(depth-previous)/rate,f'第 {i+1} 段耗时',.000001,180)
        elif mode=='plan' and row.get('duration') is not None:
            duration=number(row['duration'],f'第 {i+1} 段耗时',.000001,180)
            rate=abs(depth-previous)/duration
        elif row.get('rate') is not None:
            rate=number(row['rate'],f'第 {i+1} 段速度',.1,60)
            duration=number(abs(depth-previous)/rate,f'第 {i+1} 段耗时',.000001,180)
        else:
            duration=number(row.get('duration'),f'第 {i+1} 段耗时',.000001,180)
            rate=abs(depth-previous)/duration
        segments.append(dict(row,depth=depth,kind=kind,rate=rate,duration=duration))
        previous=depth
    moving=[row for row in segments if row['kind']!='hold']
    resolved_default=global_default if has_global else bool(moving) and all(row.get('useDefaultRate',False) for row in moving)
    return dict(segments=segments,useDefaultRates=resolved_default,waypoints=waypoints_from_segments(segments))


def visualize(payload):
    return plan(payload,auto_ascent=False)


def gf_pressure_diagram(result):
    """Pressure-space reference lines, separate from the decompression solver.

    Freeze one automatically chosen controlling compartment at the last maximum
    depth snapshot. A pressure-space endpoint chord is explicitly illustrative:
    the solver still interpolates GF itself linearly with depth.
    """
    settings=result['settings']
    surface=settings['surfacePressure']; metre=settings['density']*.0980665
    low=settings['gfLow']/100; high=settings['gfHigh']/100
    deepest=max(point['depth'] for point in result['points'])
    basis=next(point for point in reversed(result['points']) if abs(point['depth']-deepest)<1e-7)
    rows=list(coefficients([tuple(row[:2]) for row in basis['tissues']]))
    limits=[(total-low*a)/(1-low+low/b) for total,a,b in rows]
    index=max(range(16),key=lambda i:limits[i])
    _,a,b=rows[index]
    anchor_depth=result['summary']['gfAnchor']
    anchor_source='plan' if anchor_depth is not None else 'reference'
    if anchor_depth is None:
        anchor_depth=max(0,(limits[index]-surface)/metre)
    anchor=surface+anchor_depth*metre
    maximum=max(surface+deepest*metre,anchor,surface+.5)
    def allowed(pressure,gf):
        return pressure+gf*(a+pressure/b-pressure)
    fixed_low=[[pressure,allowed(pressure,low)] for pressure in (surface,maximum)]
    fixed_high=[[pressure,allowed(pressure,high)] for pressure in (surface,maximum)]
    # No positive Low anchor means no Low-to-High transition to illustrate.
    combined=([[surface,allowed(surface,high)],[anchor,allowed(anchor,low)]]
              if anchor_depth>1e-8 else [])
    return dict(gfLow=settings['gfLow'],gfHigh=settings['gfHigh'],
        surfacePressure=surface,anchorPressure=anchor,anchorDepth=anchor_depth,
        anchorSource=anchor_source,maximumPressure=maximum,
        basisTime=basis['time'],compartment=index+1,a=a,b=b,
        low=fixed_low,high=fixed_high,combined=combined,
        ambient=[[0,0],[maximum,maximum]],mValue=[[0,a],[maximum,a+maximum/b]])


def blend(payload):
    """Isothermal ideal-gas component balance; all entered pressures are gauge.

    Enumerate independent nonnegative supply bases (at most three components).
    This supports duplicate or collinear sources without inventing a solution.
    No venting, source inventory, temperature or real-gas corrections are assumed.
    """
    size=number(payload.get('size'),'气瓶容量',1,50)
    surface=number(payload.get('surfacePressure',1.01325),'水面气压',.6,1.1)
    start=number(payload.get('startPressure'),'当前压力',0,350)
    target=number(payload.get('targetPressure'),'目标压力',0,350)
    def fractions(o2,he):
        o2=number(o2,'O₂',0,100)/100;he=number(he,'He',0,100)/100
        if o2+he>1+1e-12: raise ValueError('氧气与氦气比例之和不能超过 100%。')
        return (o2,he,max(0,1-o2-he))
    initial=fractions(payload.get('startO2'),payload.get('startHe'))
    final=fractions(payload.get('targetO2'),payload.get('targetHe'))
    raw=payload.get('sources',[])
    if not isinstance(raw,list) or not 1<=len(raw)<=6: raise ValueError('请设置 1–6 种补充气源。')
    sources=[]
    for source in raw:
        f=fractions(source.get('o2'),source.get('he'))
        if source.get('enabled',True) is True:
            sources.append(dict(name=str(source.get('name','Gas'))[:40],fractions=f))
    remaining=[(target+surface)*f-(start+surface)*i for f,i in zip(final,initial)]
    def impossible(code,reason): return dict(feasible=False,code=code,reason=reason,steps=[])
    if target<start-1e-8: return impossible('pressure','目标压力低于当前压力，无法仅通过补气完成；需要先放气并重新计算。')
    for component,value in zip(('O₂','He','N₂'),remaining):
        if value < -1e-8:
            return impossible('excess',f'当前余气中的 {component} 已超过目标所需量，无法仅通过补气完成；需要先放气或更换目标。')
    if target-start<1e-8:
        return dict(feasible=True,steps=[],final=dict(pressure=target,o2=final[0]*100,he=final[1]*100),totalLitres=0,totalPressure=0)
    def solve(columns):
        n=len(columns)
        matrix=[[sum(a*b for a,b in zip(columns[i],columns[j])) for j in range(n)]+[sum(a*b for a,b in zip(columns[i],remaining))] for i in range(n)]
        for col in range(n):
            pivot=max(range(col,n),key=lambda row:abs(matrix[row][col]))
            if abs(matrix[pivot][col])<1e-11: return None
            matrix[col],matrix[pivot]=matrix[pivot],matrix[col]
            scale=matrix[col][col];matrix[col]=[x/scale for x in matrix[col]]
            for row in range(n):
                if row!=col:
                    scale=matrix[row][col]
                    matrix[row]=[x-scale*y for x,y in zip(matrix[row],matrix[col])]
        values=[row[-1] for row in matrix]
        if any(v < -1e-7 for v in values): return None
        values=[max(0,v) for v in values]
        if any(abs(sum(c[i]*v for c,v in zip(columns,values))-remaining[i])>1e-7 for i in range(3)): return None
        return values
    chosen=None
    for n in range(1,min(3,len(sources))+1):
        for subset in combinations(sources,n):
            values=solve([source['fractions'] for source in subset])
            if values is not None: chosen=list(zip(subset,values));break
        if chosen is not None: break
    if chosen is None:
        return impossible('sources','已启用的气源无法配出目标比例；请检查缺少的氧气、氦气或氮气来源，或调整目标。')
    pressure=start;components=[(start+surface)*f for f in initial];steps=[]
    for source,delta in chosen:
        if delta<1e-8: continue
        before=pressure;pressure+=delta
        components=[x+delta*f for x,f in zip(components,source['fractions'])]
        steps.append(dict(gas=source['name'],o2=source['fractions'][0]*100,he=source['fractions'][1]*100,
                          fromPressure=before,toPressure=pressure,addPressure=delta,litres=delta*size,
                          mixO2=components[0]/(pressure+surface)*100,mixHe=components[1]/(pressure+surface)*100))
    return dict(feasible=True,steps=steps,totalLitres=(target-start)*size,totalPressure=target-start,
                final=dict(pressure=pressure,o2=components[0]/(pressure+surface)*100,he=components[1]/(pressure+surface)*100))


# Error localization at the JSON boundary keeps the numerical API language-neutral.
# Parameterized messages are translated through ordered phrase replacements.
EN_MESSAGES = {
'请设置 1–24 个潜水分段。':'Set 1–24 dive segments.',
'默认速度模式请设置 1–12 个目标深度。':'Set 1–12 target depths in default speed mode.',

'GF Low 不能大于 GF High。':'GF Low must not exceed GF High.',
'末站深度只能为 3 m 或 6 m。':'The last stop must be 3 m or 6 m.',
'底部氧分压上限不能大于减压氧分压上限。':'The working PPO2 limit must not exceed the decompression limit.',
'请设置 1–8 种气体。':'Set between 1 and 8 gases.',
'请设置 1–12 个潜水分段。':'Set between 1 and 12 dive segments.',
'请设置 1–6 种补充气源。':'Set between 1 and 6 supply gases.',
'气体编号重复或缺失。':'Gas identifiers must be present and unique.',
'计划分段总时长不能超过 360 分钟。':'Total entered segment time must not exceed 360 minutes.',
'至少一个分段的深度须大于 0。':'At least one segment must be below the surface.',
'模拟超过 1080 分钟，请缩短潜水时长或调整参数。':'Simulation exceeds 1080 minutes. Shorten the dive or adjust the settings.',
'手动分段穿越了当前 GF 的减压上限。请在更深处结束分段，让程序自动生成上升计划。':'An entered segment crosses the GF ceiling. End the entered profile deeper and let the planner calculate ascent.',
'设定分段越过了 GF High 的减压上限；本页仅展示该剖面，不自动修正上升。':'The entered profile crosses the GF High ceiling. Visualization does not correct the ascent.',
'最后一段浅于设定末站，且仍需减压。请在更深处结束手动分段。':'The final segment is shallower than the last stop while decompression is required. End the profile deeper.',
'最后一段已浅于 GF Low 允许的首站深度。请在更深处结束手动分段。':'The final segment is above the GF Low ceiling. End the profile deeper.',
'手动分段的下降速度超过设定上限。':'An entered descent exceeds the configured rate.',
'手动分段的上升速度超过设定上限。':'An entered ascent exceeds the configured rate.',
'部分氧分压超出 NOAA 单次暴露表范围，CNS 无法完整估算。':'Some PPO2 values exceed the NOAA table range; CNS cannot be fully estimated.',
'本次模拟的 CNS 氧暴露估算超过 100%。':'Estimated CNS exposure for this simulation exceeds 100%.',
'结束压力须小于起始压力。':'End pressure must be less than start pressure.',
'分段类型与目标深度不一致：停留须保持上一深度，下潜须更深，上升须更浅。':'Segment direction does not match its depth: hold at the previous depth, descend deeper, or ascend shallower.',
'目标压力低于当前压力，无法仅通过补气完成；需要先放气并重新计算。':'Target pressure is below current pressure. Adding gas cannot achieve it; venting and recalculation would be needed.',
'已启用的气源无法配出目标比例；请检查缺少的氧气、氦气或氮气来源，或调整目标。':'Enabled supplies cannot produce the target mix. Check available oxygen, helium and nitrogen sources, or change the target.',
'当前余气中的 ':'The remaining ',
' 已超过目标所需量，无法仅通过补气完成；需要先放气或更换目标。':' exceeds the target amount. Adding gas cannot remove it; venting or a different target would be needed.',
' 的氧气与氦气比例之和不能超过 100%。':': oxygen and helium fractions must not exceed 100% in total.',
'氧气与氦气比例之和不能超过 100%。':'Oxygen and helium fractions must not exceed 100% in total.',
' 在部分深度超过所设氧分压上限。':' exceeds the configured PPO2 limit at some depths.',
' 在部分深度的氧分压低于 0.16 bar。':' has PPO2 below 0.16 bar at some depths.',
' 的切换深度浅于末站 ':': switch depth is shallower than the last stop of ',
' m，自动减压不使用该换气点。':' m; this switch point is not used for automatic decompression.',
'引用了停用或不存在的气体。':'references a disabled or missing gas.',
'必须是数字。':' must be numeric.', '须在 ':' must be in ', ' 范围内。':' range.',
'气瓶容量':'Cylinder size','起始压力':'Start pressure','结束压力':'End pressure',
'当前压力':'Current pressure','目标压力':'Target pressure','潜水时长':'Duration',
'平均深度':'Average depth','水面气压':'Surface pressure','水密度':'Water density',
'分段深度':'Segment depth','海拔':'Altitude','未知计算请求。':'Unknown calculation request.',
'气量不足':'insufficient gas','低于预留压力':'below reserve','：理论余压 ':': theoretical remaining ',
' bar，预留 ':' bar; reserve ',' bar。':' bar.', '第 ':'Segment ', ' 段深度':' depth',' 段耗时':' duration',' 段速度':' speed',' 段':' ',
}


def localize(text,lang):
    if lang!='en': return text
    for original,translation in sorted(EN_MESSAGES.items(),key=lambda item:-len(item[0])):
        text=text.replace(original,translation)
    return text


def handle_json(request):
    lang='zh'
    try:
        request=json.loads(request)
        lang=request.get('lang','zh')
        action=request.get('action','plan')
        payload=request.get('payload',{})
        if action=='plan': result=plan(payload)
        elif action=='visualize': result=visualize(payload)
        elif action=='segments': result=segment_timings(payload)
        elif action=='ndl': result=ndl(payload)
        elif action=='blend': result=blend(payload)
        elif action=='sac': result=sac(payload)
        elif action=='environment':
            altitude=number(payload.get('altitude'),'海拔',-100,3000)
            result=dict(surfacePressure=1.01325*(1-2.25577e-5*altitude)**5.25588)
        else: raise ValueError('未知计算请求。')
        for warning in result.get('warnings',[]): warning['message']=localize(warning['message'],lang)
        if 'reason' in result: result['reason']=localize(result['reason'],lang)
        return json.dumps(dict(ok=True,result=result),ensure_ascii=False,allow_nan=False)
    except (ValueError,TypeError,KeyError) as error:
        return json.dumps(dict(ok=False,error=localize(str(error),lang)),ensure_ascii=False)
