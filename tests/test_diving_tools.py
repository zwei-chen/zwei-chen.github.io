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

    def test_tissue_gas_shares_use_tissue_pressures_and_handle_zero(self):
        air=p.visualize(profile())
        self.assertTrue(all(pair==[1.0,0.0] or pair==(1.0,0.0)
                            for point in air['points'] for pair in point['tissueGasFractions']))
        data=profile();data['gases'][0].update(o2=18,he=45)
        result=p.visualize(data)
        mixed=next(point for point in result['points'] if point['time']==20)
        self.assertTrue(all(0<share[1]<1 for share in mixed['tissueGasFractions']))
        for point in result['points']:
            for (n,h,_),(n_share,h_share) in zip(point['tissues'],point['tissueGasFractions']):
                self.assertAlmostEqual(n_share+h_share,1)
                self.assertAlmostEqual(n_share*(n+h),n)
                self.assertAlmostEqual(h_share*(n+h),h)
        # Tissue proportions vary by compartment; they are not breathing-mix fractions.
        self.assertGreater(max(v[1] for v in mixed['tissueGasFractions'])-min(v[1] for v in mixed['tissueGasFractions']),.05)
        settings,gases,_=p.validate(profile())
        simulation=p.Simulation(settings,gases);simulation.tissues=[(0,0)]*16
        simulation.record(gases[0],'start')
        self.assertEqual(simulation.points[-1]['tissueGasFractions'],[(0,0)]*16)

    def test_current_gf_differs_from_surface(self):
        data=profile();data['segments']=data['segments'][:2]
        result=p.visualize(data)
        self.assertEqual(result['summary']['runtime'],32)
        point=result['points'][-1]
        self.assertLess(point['gf99'],point['surfaceGF'])

    def test_point_partial_pressures_and_cns_follow_selected_time(self):
        data=profile();data['gases'][0].update(o2=32,he=20)
        result=p.visualize(data)
        self.assertEqual(result['points'][0]['cns'],0)
        values=[point['cns'] for point in result['points']]
        self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
        self.assertAlmostEqual(values[-1],result['summary']['cns'])
        halfway=next(point for point in result['points'] if point['time']==15)
        self.assertLess(halfway['cns'],values[-1])
        for point in result['points']:
            self.assertAlmostEqual(point['ppn2'],point['ambient']*.48)
            self.assertAlmostEqual(point['ppo2']+point['ppn2']+point['ambient']*.20,point['ambient'])

    def test_cns_at_inserted_minute_and_after_out_of_range(self):
        settings,gases,_=p.validate(profile())
        gas=dict(gases[0],o2=100,he=0,fractions=(0,0))
        sim=p.Simulation(settings,[gas]);sim.visualization=True
        sim.record(gas,'start');sim.advance(0,1.17,gas,'segment')
        minute=next(point for point in sim.points if point['time']==1)
        self.assertAlmostEqual(minute['cns'],100/300)
        self.assertAlmostEqual(sim.points[-1]['cns'],1.17*100/300)
        sim.advance(10,1.17,gas,'segment')
        self.assertIsNone(sim.points[-1]['cns'])
        sim.advance(0,1.17,gas,'segment')
        self.assertIsNone(sim.points[-1]['cns'])

    def test_ndl_boundary_matches_no_stop_planning(self):
        for o2,he in [(21,0),(21,35)]:
            with self.subTest(o2=o2,he=he):
                data=profile();data['segments']=data['segments'][:2]
                data['segments'][1]['duration']=5
                data['gases'][0].update(o2=o2,he=he)
                result=p.visualize(data)
                request=dict(settings=result['settings'],point=result['points'][-1],gas=result['gases'][0])
                before=json.dumps(request,sort_keys=True)
                remaining=p.ndl(request)
                self.assertEqual(json.dumps(request,sort_keys=True),before)
                self.assertFalse(remaining['capped'])
                self.assertGreater(remaining['minutes'],0)
                data['segments'][1]['duration']=5+remaining['minutes']
                self.assertEqual(p.plan(data)['summary']['decoTime'],0)
                data['segments'][1]['duration']+=1
                self.assertGreater(p.plan(data)['summary']['decoTime'],0)

    def test_ndl_zero_cap_conservatism_and_switch(self):
        data=profile();data['segments']=data['segments'][:2]
        result=p.visualize(data)
        request=dict(settings=result['settings'],point=result['points'][-1],gas=result['gases'][0])
        self.assertEqual(p.ndl(request)['minutes'],0)
        initial=dict(request,point=result['points'][0])
        self.assertEqual(p.ndl(initial)['minutes'],99)
        self.assertTrue(p.ndl(initial)['capped'])
        self.assertTrue(p.ndl(dict(initial,gas=dict(o2=100,he=0)))['capped'])
        start_at_depth=next(point for point in result['points'] if point['time']==2)
        request['point']=start_at_depth
        low=p.ndl(request)['minutes']
        high=p.ndl(dict(request,settings=dict(result['settings'],gfHigh=85)))['minutes']
        self.assertGreater(high,low)
        nitrox=p.ndl(dict(request,gas=dict(o2=32,he=0)))['minutes']
        self.assertGreater(nitrox,low)
        reply=json.loads(p.handle_json(json.dumps(dict(action='ndl',payload=request,lang='en'))))
        self.assertTrue(reply['ok']);self.assertEqual(reply['result']['minutes'],low)
        with self.assertRaises(ValueError):p.ndl(dict(request,point=dict(depth=30,tissues=[])))
        with self.assertRaises(ValueError):p.ndl(dict(request,gas=dict(o2=80,he=40)))

    def test_gf_pressure_fixed_lines_match_independent_buhlmann_equation(self):
        data=profile();result=p.visualize(data);g=result['gfPressure']
        self.assertEqual((g['gfLow'],g['gfHigh']),(50,70))
        for key,gf in [('low',.5),('high',.7)]:
            for ambient,tissue_limit in g[key]:
                # Recover the fraction of the available M-value gradient.
                self.assertAlmostEqual((tissue_limit-ambient)/(g['a']+ambient/g['b']-ambient),gf)
                # Independently invert the limit to recover ambient pressure.
                self.assertAlmostEqual((tissue_limit-gf*g['a'])/(gf/g['b']+1-gf),ambient)
        self.assertTrue(all(l[1]<h[1] for l,h in zip(g['low'],g['high'])))

    def test_gf_pressure_endpoint_chord_and_actual_plan_anchor(self):
        data=profile();data['segments']=data['segments'][:2]
        result=p.plan(data);g=result['gfPressure']
        self.assertEqual(g['anchorSource'],'plan')
        self.assertEqual(g['anchorDepth'],result['summary']['gfAnchor'])
        self.assertEqual(g['combined'][0],g['high'][0])
        ambient,tissue=g['combined'][1]
        self.assertAlmostEqual(ambient,g['surfacePressure']+g['anchorDepth']*result['settings']['density']*.0980665)
        self.assertAlmostEqual((tissue-ambient)/(g['a']+ambient/g['b']-ambient),.5)
        # The chord is an illustration, deliberately not a change to the solver.
        before=json.dumps(result,sort_keys=True)
        p.gf_pressure_diagram(result)
        self.assertEqual(json.dumps(result,sort_keys=True),before)

    def test_gf_pressure_trimix_and_reference_anchor(self):
        data=profile();data['gases'][0].update(o2=18,he=45)
        result=p.visualize(data);g=result['gfPressure']
        self.assertEqual(g['anchorSource'],'reference')
        self.assertEqual(g['basisTime'],32)
        basis=next(row for row in result['points'] if row['time']==32)
        n,h=basis['tissues'][g['compartment']-1][:2];i=g['compartment']-1
        self.assertAlmostEqual(g['a'],(p.N2_A[i]*n+p.HE_A[i]*h)/(n+h))
        self.assertAlmostEqual(g['b'],(p.N2_B[i]*n+p.HE_B[i]*h)/(n+h))
        self.assertGreater(g['anchorDepth'],0)
        self.assertEqual(g['combined'][1][0],g['anchorPressure'])

    def test_gf_pressure_no_anchor_equal_gf_and_json(self):
        data=profile();data['segments']=[dict(depth=1,duration=1,gas='air',kind='descent')]
        g=p.visualize(data)['gfPressure']
        self.assertEqual(g['combined'],[])
        data=profile();data['settings'].update(gfLow=70,gfHigh=70)
        response=json.loads(p.handle_json(json.dumps(dict(action='visualize',payload=data,lang='en'))))
        self.assertTrue(response['ok']);g=response['result']['gfPressure']
        self.assertEqual(g['low'],g['high'])
        self.assertTrue(all(point['time']>=0 for point in response['result']['points']))

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

    def test_default_waypoints_connect_depths_without_arrival_dwell(self):
        data=dict(profile(),useDefaultRates=True,waypoints=[
            dict(depth=18,duration=2,gas='air'),dict(depth=6,duration=3,gas='air'),
            dict(depth=0,duration=0,gas='air')])
        original=json.dumps(data,sort_keys=True)
        result=p.visualize(data)
        self.assertAlmostEqual(result['summary']['runtime'],7.8)
        self.assertEqual([s['duration'] for s in result['segments']],[1,2,1.2,3,.6])
        self.assertEqual([s['depth'] for s in result['segments']],[18,18,6,6,0])
        self.assertEqual(result['summary']['endDepth'],0)
        explicit=dict(data,useDefaultRates=False,segments=[
            dict(depth=18,rate=18,gas='air',kind='descent'),dict(depth=18,duration=2,gas='air',kind='hold'),
            dict(depth=6,rate=10,gas='air',kind='ascent'),dict(depth=6,duration=3,gas='air',kind='hold'),
            dict(depth=0,rate=10,gas='air',kind='ascent')])
        self.assertEqual(result['points'],p.visualize(explicit)['points'])
        self.assertEqual(json.dumps(data,sort_keys=True),original)

    def test_default_waypoint_migration_preserves_gas_switch_and_holds(self):
        data=profile();data['useDefaultRates']=True
        data['gases'].append(dict(data['gases'][0],id='nitrox',name='EAN32',o2=32))
        data['segments'][1]['gas']='nitrox'
        converted=p.segment_timings(data)
        self.assertIn('waypoints',converted)
        self.assertEqual(converted['waypoints'],[
            dict(depth=30,duration=0,gas='air'),dict(depth=30,duration=30,gas='nitrox'),
            dict(depth=0,duration=0,gas='air')])
        self.assertEqual(p.visualize(data)['points'],p.visualize(dict(data,waypoints=converted['waypoints']))['points'])
        data['segments'][1]['gas']='air'
        self.assertEqual(p.segment_timings(data)['waypoints'],[
            dict(depth=30,duration=30,gas='air'),dict(depth=0,duration=0,gas='air')])

    def test_default_waypoint_timing_follows_edited_depth_and_plan_rates(self):
        data=dict(profile(),useDefaultRates=True,mode='plan',settings=dict(descentRate=12,ascentRate=6),
                  waypoints=[dict(depth=18,duration=2,gas='air'),dict(depth=6,duration=0,gas='air')])
        timings=p.segment_timings(data)
        self.assertEqual([s['duration'] for s in timings['segments']],[1.5,2,2])
        self.assertEqual([s['travelTime'] for s in timings['waypointTimings']],[1.5,2])
        self.assertEqual([s['totalTime'] for s in timings['waypointTimings']],[3.5,2])
        data['waypoints'][0]['depth']=12
        self.assertEqual([s['duration'] for s in p.plan(data)['segments']],[1,2,1])

    def test_default_waypoint_validation_and_zero_hold(self):
        base=dict(profile(),useDefaultRates=True)
        for rows in ([],[dict(depth=30,duration=-1,gas='air')],
                     [dict(depth=30,duration=float('nan'),gas='air')],
                     [dict(depth=30,duration=2,gas='missing')],
                     [dict(depth=0,duration=0,gas='air')]):
            with self.assertRaises(ValueError):p.visualize(dict(base,waypoints=rows))
        result=p.visualize(dict(base,waypoints=[dict(depth=.5,duration=0,gas='air')]))
        self.assertAlmostEqual(result['summary']['runtime'],.5/18)
        self.assertEqual(len(result['segments']),1)
        self.assertEqual(result['summary']['endDepth'],.5)
        rows=[dict(depth=3 if i%2==0 else 6,duration=.1,gas='air') for i in range(12)]
        result=p.visualize(dict(base,waypoints=rows))
        self.assertEqual(len(result['segments']),24)
        expanded=p.segment_timings(dict(base,waypoints=rows))['segments']
        self.assertEqual(result['points'],p.visualize(dict(base,useDefaultRates=False,segments=expanded))['points'])

    def test_default_rates_visualize_without_extra_hold(self):
        data=profile();data['settings'].update(descentRate=5,ascentRate=4)
        data['segments']=[dict(depth=30,useDefaultRate=True,duration=90,rate=1,gas='air',kind='descent'),
                          dict(depth=30,duration=3,useDefaultRate=True,gas='air',kind='hold'),
                          dict(depth=0,useDefaultRate=True,duration=90,rate=1,gas='air',kind='ascent')]
        original=json.dumps(data,sort_keys=True)
        result=p.visualize(data)
        self.assertEqual(len(result['segments']),3)
        self.assertAlmostEqual(result['summary']['runtime'],30/18+3+30/10)
        self.assertEqual([s['duration'] for s in result['segments']],[30/18,3,3])
        self.assertEqual(json.dumps(data,sort_keys=True),original)
        explicit=json.loads(json.dumps(data))
        for row,rate in zip(explicit['segments'],[18,None,10]):
            row.pop('useDefaultRate');row['rate']=rate
        self.assertEqual(result['points'],p.visualize(explicit)['points'])

    def test_default_rates_plan_follow_settings_and_depths(self):
        data=profile();data['settings'].update(descentRate=12,ascentRate=6)
        data['segments']=[dict(depth=18,useDefaultRate=True,duration=99,rate=1,gas='air'),
                          dict(depth=18,duration=2,gas='air'),
                          dict(depth=6,useDefaultRate=True,duration=99,rate=1,gas='air')]
        result=p.plan(data)
        self.assertEqual([s['duration'] for s in result['segments']],[1.5,2,2])
        explicit=json.loads(json.dumps(data))
        for row,duration in zip(explicit['segments'],[1.5,2,2]):
            row.pop('useDefaultRate',None);row['duration']=duration
        self.assertEqual(result['points'],p.plan(explicit)['points'])
        data['settings'].update(descentRate=18,ascentRate=12)
        self.assertEqual([s['duration'] for s in p.plan(data)['segments']],[1,2,1])
        data['segments'][2]['depth']=12
        self.assertEqual(p.plan(data)['segments'][2]['duration'],.5)

    def test_global_default_rate_switch_overrides_all_legacy_rows(self):
        data=profile();data['settings'].update(descentRate=12,ascentRate=6)
        data['segments']=[dict(depth=18,duration=3,rate=9,useDefaultRate=False,gas='air',kind='descent'),
                          dict(depth=18,duration=2,gas='air',kind='hold'),
                          dict(depth=6,duration=4,rate=3,useDefaultRate=True,gas='air',kind='ascent')]
        original=json.dumps(data,sort_keys=True)
        for mode,automatic,manual in [('vision',[1,2,1.2],[2,2,4]),('plan',[1.5,2,2],[3,2,4])]:
            for enabled,expected in [(True,automatic),(False,manual)]:
                resolved=p.segment_timings(dict(data,mode=mode,useDefaultRates=enabled))
                self.assertIs(resolved['useDefaultRates'],enabled)
                self.assertEqual([row['duration'] for row in resolved['segments']],expected)
                runner=p.visualize if mode=='vision' else p.plan
                result=runner(dict(data,useDefaultRates=enabled))
                self.assertEqual([row['duration'] for row in result['segments']],expected)
        self.assertEqual(json.dumps(data,sort_keys=True),original)

    def test_legacy_default_modes_can_migrate_without_changed_travel_times(self):
        data=profile()
        data['segments'][0]['useDefaultRate']=True
        mixed=p.segment_timings(data)
        self.assertFalse(mixed['useDefaultRates'])
        migrated=json.loads(json.dumps(data))
        for saved,resolved in zip(migrated['segments'],mixed['segments']):
            if saved.get('useDefaultRate'):
                saved['rate']=resolved['rate'];saved['duration']=resolved['duration']
            saved.pop('useDefaultRate',None)
        migrated['useDefaultRates']=False
        self.assertEqual(p.visualize(migrated)['points'],p.visualize(data)['points'])
        data['segments'][2]['useDefaultRate']=True
        self.assertTrue(p.segment_timings(data)['useDefaultRates'])

    def test_global_default_mode_rejects_invalid_values(self):
        for value in ('true',1,None):
            with self.assertRaises(ValueError):p.visualize(dict(profile(),useDefaultRates=value))

    def test_default_rates_short_travel_and_manual_fallback(self):
        data=profile();data['segments']=[dict(depth=.5,useDefaultRate=True,gas='air',kind='descent')]
        self.assertAlmostEqual(p.visualize(data)['summary']['runtime'],.5/18)
        for moving in ('plan','vision'):
            rows=[dict(depth=18,duration=4,rate=3,useDefaultRate=False,gas='air')]
            response=p.segment_timings(dict(mode=moving,segments=rows))['segments'][0]
            self.assertEqual(response['duration'],4 if moving=='plan' else 6)
        for value in ('true',1,None):
            data['segments'][0]['useDefaultRate']=value
            with self.assertRaises(ValueError):p.visualize(data)
        data['segments'][0]['useDefaultRate']=True
        reply=json.loads(p.handle_json(json.dumps(dict(action='segments',payload=dict(data,mode='plan')))))
        self.assertTrue(reply['ok'])
        self.assertAlmostEqual(reply['result']['segments'][0]['duration'],.5/18)

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
