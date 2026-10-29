import importlib.util
import json
import random
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('planner', Path(__file__).resolve().parents[1]/'Diving/vision/planner.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def profile():
    return dict(settings={}, gases=[dict(id='air',name='Air',o2=21,he=0,size=12,pressure=200,enabled=True)], segments=[dict(depth=30,duration=2,gas='air',kind='descent'),dict(depth=30,duration=30,gas='air',kind='hold'),dict(depth=0,duration=1,gas='air',kind='ascent')])


def blend(**changes):
    data=dict(size=12,startPressure=50,startO2=21,startHe=0,targetPressure=200,targetO2=32,targetHe=0,surfacePressure=1.01325,sources=[dict(name='Oxygen',o2=100,he=0,enabled=True),dict(name='Helium',o2=0,he=100,enabled=True),dict(name='Air',o2=21,he=0,enabled=True)])
    return data | changes


class ToolTests(unittest.TestCase):
    def test_visualization_has_exact_entered_duration_and_gf99(self):
        result=p.visualize(profile())
        self.assertEqual(result['summary']['runtime'],33)
        self.assertEqual(result['points'][-1]['depth'],0)
        self.assertGreater(result['summary']['maxGF99'],100)
        self.assertTrue(any(w['code']=='ceiling' for w in result['warnings']))
        for point in result['points']:
            self.assertAlmostEqual(point['gf99'],max(0,max(point['tissueGF'])))
            self.assertEqual(len(point['tissueGF']),16)
        self.assertAlmostEqual(result['points'][-1]['gf99'],result['points'][-1]['surfaceGF'])
        with self.assertRaises(ValueError): p.plan(profile())

    def test_normalized_loading_boundaries_and_exceedance(self):
        # Shared chart boundaries must align for any positive ambient pressure.
        for ambient, m_value in ((.7,1.4),(4,6),(7,9)):
            self.assertEqual(p.tissue_loading(0,ambient,m_value),0)
            self.assertEqual(p.tissue_loading(ambient,ambient,m_value),1)
            self.assertEqual(p.tissue_loading(m_value,ambient,m_value),2)
            self.assertAlmostEqual(p.tissue_loading((ambient+m_value)/2,ambient,m_value),1.5)
            self.assertAlmostEqual(p.tissue_loading(ambient+2.5*(m_value-ambient),ambient,m_value),3.5)

    def test_tissue_chart_tracks_trimix_and_oxygen_switch(self):
        data=profile();data['gases'][0].update(o2=18,he=45)
        data['gases'].append(dict(id='oxygen',name='Oxygen',o2=100,he=0,size=6,pressure=200,enabled=True))
        data['segments'].append(dict(depth=0,duration=1,gas='oxygen',kind='hold'))
        result=p.visualize(data)
        mixed=next(point for point in result['points'] if point['time']==20)
        self.assertTrue(all(row[1]>0 for row in mixed['tissues']))
        self.assertAlmostEqual(mixed['inspiredInert'],(mixed['ambient']-.0627)*.82)
        self.assertAlmostEqual(mixed['inspiredInertRatio'],mixed['inspiredInert']/mixed['ambient'])
        for point in result['points']:
            self.assertEqual(len(point['tissueLoading']),16)
            for row,loading,gf in zip(point['tissues'],point['tissueLoading'],point['tissueGF']):
                if gf>0:self.assertAlmostEqual(100*(loading-1),gf)
                else:self.assertAlmostEqual(loading*point['ambient'],row[0]+row[1])
        switch=next(point for point in result['points'] if point['gas']=='oxygen')
        self.assertEqual(switch['inspiredInert'],0)
        self.assertEqual(switch['inspiredInertRatio'],0)
        self.assertTrue(any(row[1]>0 for row in switch['tissues']))

    def test_current_gf_differs_from_surface(self):
        data=profile();data['segments']=data['segments'][:2]
        result=p.visualize(data)
        self.assertEqual(result['summary']['runtime'],32)
        point=result['points'][-1]
        self.assertLess(point['gf99'],point['surfaceGF'])

    def test_segment_direction(self):
        data=profile();data['segments'][0]['kind']='ascent'
        with self.assertRaises(ValueError): p.visualize(data)
        data=profile();data['segments'][1]['depth']=20
        with self.assertRaises(ValueError): p.visualize(data)

    def test_nitrox_blend_balance_and_pressure(self):
        data=blend();result=p.blend(data)
        self.assertTrue(result['feasible'])
        self.assertAlmostEqual(result['steps'][-1]['toPressure'],200)
        self.assertAlmostEqual(sum(s['addPressure'] for s in result['steps']),150)
        self.assertAlmostEqual(sum(s['litres'] for s in result['steps']),1800)
        self.assertAlmostEqual(result['final']['o2'],32)
        self.assertAlmostEqual(result['final']['he'],0)
        self.assertAlmostEqual(result['steps'][0]['addPressure'],(201.01325*.32-51.01325*.21-150*.21)/.79)

    def test_trimix_and_custom_sources(self):
        for data in [blend(targetO2=18,targetHe=45),blend(startPressure=0,startO2=21,targetO2=36,sources=[dict(name='EAN50',o2=50,he=0,enabled=True),dict(name='Air',o2=21,he=0,enabled=True)])]:
            result=p.blend(data);self.assertTrue(result['feasible'])
            self.assertAlmostEqual(result['final']['o2'],data['targetO2'])
            self.assertAlmostEqual(result['final']['he'],data['targetHe'])

    def test_infeasible_and_already_matching(self):
        for data in [blend(targetPressure=40),blend(startPressure=190,startO2=100),blend(targetHe=40,sources=[dict(name='Air',o2=21,he=0,enabled=True)]),blend(startPressure=200,targetO2=32)]:
            result=p.blend(data);self.assertFalse(result['feasible']);self.assertTrue(result['reason']);self.assertEqual(result['steps'],[])
        result=p.blend(blend(startPressure=200,startO2=32))
        self.assertTrue(result['feasible']);self.assertEqual(result['steps'],[])

    def test_redundant_sources_and_empty_cylinder_residual(self):
        result=p.blend(blend(startPressure=0,targetO2=21,sources=[dict(name='Air1',o2=21,he=0),dict(name='Air2',o2=21,he=0)]))
        self.assertTrue(result['feasible']);self.assertEqual(len(result['steps']),1)
        result=p.blend(blend(startPressure=0,targetO2=100))
        self.assertFalse(result['feasible']) # zero gauge still holds air at atmospheric pressure

    def test_blend_invalid(self):
        for data in [blend(targetO2=80,targetHe=30),blend(startPressure=float('nan')),blend(sources=[]),blend(sources=[dict(name='bad',o2=100,he=10)])]:
            with self.assertRaises(ValueError): p.blend(data)

    def test_generated_blends_conserve_each_component(self):
        rng=random.Random(29)
        for _ in range(80):
            start=rng.uniform(0,120);o2=rng.uniform(10,40);he=rng.uniform(0,50)
            additions=[rng.uniform(0,50),rng.uniform(0,50),rng.uniform(0,70)]
            target=start+sum(additions);surface=1.01325
            target_o2=((start+surface)*o2/100+additions[0]+.21*additions[2])/(target+surface)*100
            target_he=((start+surface)*he/100+additions[1])/(target+surface)*100
            data=blend(startPressure=start,startO2=o2,startHe=he,targetPressure=target,targetO2=target_o2,targetHe=target_he)
            result=p.blend(data)
            self.assertTrue(result['feasible'])
            pressure=start;components=[(start+surface)*o2/100,(start+surface)*he/100]
            for step in result['steps']:
                self.assertGreater(step['addPressure'],0)
                self.assertAlmostEqual(step['fromPressure'],pressure)
                pressure=step['toPressure']
                components=[components[0]+step['addPressure']*step['o2']/100,components[1]+step['addPressure']*step['he']/100]
            self.assertAlmostEqual(pressure,target)
            self.assertAlmostEqual(components[0]/(pressure+surface)*100,target_o2)
            self.assertAlmostEqual(components[1]/(pressure+surface)*100,target_he)

    def test_visual_preserves_both_gf_settings(self):
        data=profile();data['settings']={'gfHigh':70,'gfLow':30}
        result=p.visualize(data)
        self.assertEqual(result['settings']['gfLow'],30)
        point=result['points'][190]
        self.assertGreater(point['ceilingLow'],point['ceilingHigh'])
        changed=p.visualize(data | {'settings':{'gfHigh':70,'gfLow':50}})
        self.assertEqual(result['summary']['runtime'],changed['summary']['runtime'])
        self.assertEqual(result['points'][-1]['gf99'],changed['points'][-1]['gf99'])
        self.assertNotEqual(point['ceilingLow'],changed['points'][190]['ceilingLow'])
        with self.assertRaises(ValueError):p.visualize(data | {'settings':{'gfLow':80,'gfHigh':70}})

    def test_visual_segment_rates_determine_duration(self):
        data=profile();data['segments']=[dict(depth=30,rate=15,gas='air',kind='descent'),dict(depth=30,duration=10,gas='air',kind='hold'),dict(depth=10,rate=5,gas='air',kind='ascent'),dict(depth=0,rate=10,gas='air',kind='ascent')]
        result=p.visualize(data)
        self.assertAlmostEqual(result['summary']['runtime'],17)
        self.assertEqual([s['duration'] for s in result['segments']],[2,10,4,1])
        self.assertFalse(any(w['code'] in ('ascent','descent') for w in result['warnings']))
        for invalid in (0,'',float('nan')):
            data['segments'][0]['rate']=invalid
            with self.assertRaises(ValueError):p.visualize(data)

    def test_visual_legacy_durations_and_short_movement(self):
        data=profile();old=p.visualize(data)
        self.assertEqual(old['summary']['runtime'],33)
        normalized=p.segment_timings({'segments':data['segments']})['segments']
        self.assertEqual([s['rate'] for s in normalized],[15,None,30])
        data['segments']=[dict(depth=.5,rate=10,kind='descent',gas='air')]
        self.assertAlmostEqual(p.visualize(data)['summary']['runtime'],.05)

    def test_default_plans_do_not_add_switch_dwell_or_safety_stop(self):
        self.assertEqual(p.DEFAULTS['switchTime'],0)
        self.assertEqual(p.DEFAULTS['safetyStop'],0)

    def test_custom_water_density_and_gas_details(self):
        data=profile();data['settings']={'density':1.015}
        result=p.visualize(data)
        self.assertAlmostEqual(result['points'][12]['ambient'],1.01325+30*1.015*.0980665)
        info=result['gasDetails'][0]
        self.assertEqual(info['n2'],79)
        self.assertGreater(info['decoMod'],info['mod'])

    def test_minute_cursor_has_exact_samples_and_fractional_endpoint(self):
        data=profile();data['segments']=[dict(depth=20,rate=9,gas='air',kind='descent'),dict(depth=20,duration=3.4,gas='air',kind='hold'),dict(depth=0,rate=7,gas='air',kind='ascent')]
        result=p.visualize(data)
        indices=result['minuteIndices']
        times=[result['points'][i]['time'] for i in indices]
        self.assertEqual(times[:-1],list(range(9)))
        self.assertAlmostEqual(times[-1],20/9+3.4+20/7)
        self.assertEqual(indices[-1],len(result['points'])-1)
        at_three=result['points'][indices[3]]
        surface=p.DEFAULTS['surfacePressure'];bottom=surface+20*p.DEFAULTS['density']*.0980665
        tissues=p.load_tissues([(.7902*(surface-p.WATER_VAPOUR),0)]*16,surface,bottom,20/9,(.79,0))
        expected=p.load_tissues(tissues,bottom,bottom,3-20/9,(.79,0))
        for actual,wanted in zip(at_three['tissues'],expected):
            self.assertAlmostEqual(actual[0],wanted[0],places=10)
            self.assertAlmostEqual(actual[1],wanted[1],places=10)

    def test_minute_cursor_short_profile_and_exact_end(self):
        data=profile();data['segments']=[dict(depth=1,rate=10,gas='air',kind='descent')]
        result=p.visualize(data)
        self.assertEqual([result['points'][i]['time'] for i in result['minuteIndices']],[0,.1])
        result=p.visualize(profile())
        self.assertEqual([result['points'][i]['time'] for i in result['minuteIndices']],list(range(34)))

    def test_minute_cursor_plan_ascent(self):
        data=profile();data['segments']=data['segments'][:2]
        result=p.plan(data)
        times=[result['points'][i]['time'] for i in result['minuteIndices']]
        self.assertEqual(times[:-1],list(range(int(result['summary']['runtime'])+1)))
        self.assertAlmostEqual(times[-1],result['summary']['runtime'])

    def test_scr_details(self):
        result=p.sac(dict(size=12,start=200,end=100,duration=40,depth=10,surfacePressure=1,density=1/.0980665/10))
        self.assertEqual(result['sac'],15);self.assertEqual(result['ambient'],2)
        self.assertEqual(result['usedLitres'],1200);self.assertEqual(result['pressureRate'],1.25)

    def test_english_dispatch(self):
        for action,payload in [('plan',{'settings':{'gfLow':90,'gfHigh':70}}),('blend',blend(targetO2=90,targetHe=20)),('sac',dict(size=12,start=100,end=200,duration=40,depth=10))]:
            result=json.loads(p.handle_json(json.dumps(dict(action=action,payload=payload,lang='en'))))
            self.assertFalse(result['ok']);self.assertFalse(any('\u4e00'<=c<='\u9fff' for c in result['error']))

if __name__=='__main__':unittest.main()
