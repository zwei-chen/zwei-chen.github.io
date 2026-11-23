import json
import unittest

from test_diving_planner import example, p


def profile(**overrides):
    return dict(dict(depth=40, duration=30, setpoint=1.3, diluentO2=21, diluentHe=0,
                     gases=example()['gases']), **overrides)


class ClosedCircuitTests(unittest.TestCase):
    def test_constant_setpoint_and_surface_limit(self):
        tissues = [(0, 0)] * 16
        amb = 5
        state = p.load_cc_tissues(tissues, amb, amb, 4, (.5, .5), 1.3)
        self.assertAlmostEqual(state[0][0], (amb-p.WATER_VAPOUR-1.3)*.5*.5)
        threshold = 1.3 + p.WATER_VAPOUR
        full = p.load_cc_tissues(state, 2, 1, 2, (.5,.5), 1.3)
        first = p.load_cc_tissues(state, 2, threshold, (2-threshold)*2, (.5,.5), 1.3)
        split = p.load_cc_tissues(first, threshold, 1, (threshold-1)*2, (.5,.5), 1.3)
        for a,b in zip(full,split):
            for x,y in zip(a,b):
                self.assertAlmostEqual(x,y,places=10)

    def test_bailout_keeps_cc_history_and_uses_separate_gases(self):
        result = p.cc_plan(profile())
        cc, bo = result['cc'],result['bailout']
        self.assertEqual(cc['schedule'][-1]['depth'],0)
        self.assertEqual(bo['schedule'][-1]['depth'],0)
        self.assertAlmostEqual(bo['startTime'],40/18+30)
        self.assertEqual(bo['startDepth'],40)
        self.assertGreater(bo['surfaceTime'],cc['surfaceTime'])
        self.assertEqual({r['gas'] for r in bo['schedule']},{'air'})
        self.assertGreater(bo['gases'][0]['used'],0)
        self.assertEqual(cc,p.cc_plan(profile(gases=[]))['cc'])
        self.assertFalse(p.cc_plan(profile(gases=[]))['bailout']['available'])

    def test_bailout_at_runtime_and_out_of_range(self):
        result=p.cc_plan(profile(bailoutTime=1))
        self.assertAlmostEqual(result['bailout']['startDepth'],18)
        self.assertAlmostEqual(result['bailout']['startTime'],1)
        result=p.cc_plan(profile(bailoutTime=1000))
        self.assertFalse(result['bailout']['available'])

    def test_gas_limits_shortfalls_and_translated_errors(self):
        gas=example()['gases'][0]
        bo=p.cc_plan(profile(gases=[dict(gas, o2=100)]))['bailout']
        self.assertFalse(bo['available'])
        bo=p.cc_plan(profile(gases=[dict(gas, size=1, pressure=50)]))['bailout']
        self.assertTrue(bo['available'])
        self.assertGreater(bo['gases'][0]['shortfall'],0)
        request=dict(action='cc_plan',lang='en',payload=profile(gases=[]))
        self.assertTrue(json.loads(p.handle_json(json.dumps(request)))['result']['bailout']['reason'].isascii())

    def test_multigas_bailout_preserves_absolute_runtime_and_volume(self):
        gas = example()['gases'][0]
        data = profile(gases=[gas, dict(gas, id='deco', name='EAN50', o2=50, switchDepth=21)])
        result = p.cc_plan(data)
        bo = result['bailout']
        self.assertTrue(any(r['phase']=='switch' and r['gas']=='deco' and r['depth']==21 for r in bo['schedule']))
        expected = sum(25*(1.01325+1.03*.0980665*(r['fromDepth']+r['depth'])/2)*r['duration'] for r in bo['schedule'])
        self.assertAlmostEqual(expected, sum(g['used'] for g in bo['gases']))
        first = next(r for r in result['cc']['schedule'] if r['phase']=='deco')
        t = first['runtime']-.5
        branch = p.cc_plan(dict(data,bailoutTime=t))['bailout']
        self.assertAlmostEqual(branch['startDepth'],first['depth'])
        self.assertAlmostEqual(branch['surfaceTime']-t,sum(r['duration'] for r in branch['schedule']))
        in_transit = next(r for r in result['cc']['schedule'] if r['phase']=='ascent' and r['runtime']>first['runtime'])
        mid = in_transit['runtime']-in_transit['duration']/2
        branch = p.cc_plan(dict(data,bailoutTime=mid))['bailout']
        self.assertFalse(any(r['phase']=='deco' and abs(r['depth']/3-round(r['depth']/3))>.001 for r in branch['schedule']))

    def test_helium_validation_and_setpoint_effect(self):
        with self.assertRaises(ValueError):
            p.cc_plan(profile(diluentO2=50,diluentHe=60))
        with self.assertRaises(ValueError):
            p.cc_plan(profile(diluentO2=100))
        self.assertGreater(p.cc_plan(profile(setpoint=.8))['cc']['surfaceTime'],
                           p.cc_plan(profile(setpoint=1.3))['cc']['surfaceTime'])

    def test_dual_setpoints_and_surface_fo2_limit(self):
        data = profile(setpointLow=.7, setpointHigh=1.3, spSwitch='descent', spDepth=12, diluentHe=35)
        result = p.cc_plan(data)
        cc = result['cc']
        points = cc['profilePoints']
        selected = next(i for i,pt in enumerate(points) if pt['phase']=='setpoint')
        before,after = points[selected-1:selected+1]
        self.assertAlmostEqual(after['time'],12/18)
        self.assertEqual(before['tissues'],after['tissues'])
        self.assertEqual([before['setpoint'],after['setpoint']],[.7,1.3])
        self.assertTrue(all(pt['setpoint']==1.3 for pt in points[selected:]))
        self.assertAlmostEqual(points[-1]['ppo2'],1.01325*.90)
        self.assertEqual(points[-1]['depth'],0)
        bo = result['bailout']
        first = bo['profilePoints'][0]
        cc_branch = next(pt for pt in points if abs(pt['time']-bo['startTime'])<1e-8)
        self.assertEqual(first['tissues'],cc_branch['tissues'])
        self.assertAlmostEqual(first['cns'],cc_branch['cns'])
        self.assertNotIn('setpoint',first)
        self.assertEqual(len(points[-1]['tissueGasFractions']),16)

    def test_switch_options_do_not_force_high(self):
        base = profile(setpointLow=.65,setpointHigh=1.25)
        for mode,threshold in [('low',0),('descent',0),('descent',50)]:
            cc = p.cc_plan(dict(base,spSwitch=mode,spDepth=threshold))['cc']
            self.assertEqual({pt['setpoint'] for pt in cc['profilePoints']},{.65})
        at_bottom = p.cc_plan(base)['cc']
        event = next(pt for pt in at_bottom['profilePoints'] if pt['phase']=='setpoint')
        self.assertEqual(event['depth'],40)
        with self.assertRaises(ValueError):
            p.cc_plan(dict(base,setpointLow=1.3,setpointHigh=1.0))

    def test_cc_cursor_forecasts_at_depth_and_surface(self):
        cc = p.cc_plan(profile(setpointLow=.7,setpointHigh=1.3))['cc']
        hold = next(pt for pt in reversed(cc['profilePoints']) if pt['phase']=='hold')
        def metrics(point):
            return p.cc_point_metrics(dict(settings=cc['settings'],gases=cc['inventory'],point=point))
        prediction = metrics(hold)
        self.assertEqual(prediction['ndl']['minutes'],0)
        self.assertAlmostEqual(prediction['projection']['tts'],cc['tts'])
        self.assertGreater(prediction['projection']['atPlus5'],prediction['projection']['tts'])
        surface=metrics(cc['profilePoints'][-1])
        self.assertEqual(surface['projection']['tts'],0)

    def test_deco_setpoint_starts_on_ascent_and_applies_to_projections(self):
        base = profile(depth=100, duration=25, diluentO2=10, diluentHe=70,
                       setpointLow=.7, setpointHigh=1.3, gases=[])
        old = p.cc_plan(base)['cc']
        cc = p.cc_plan(dict(base,setpointDeco=1.6))['cc']
        self.assertEqual(cc['bottomSetpoint'],1.3)
        hold = next(pt for pt in reversed(cc['profilePoints']) if pt['phase']=='hold')
        self.assertEqual(hold['tissues'],next(pt['tissues'] for pt in reversed(old['profilePoints']) if pt['phase']=='hold'))
        changed = next(pt for pt in cc['profilePoints'] if pt['setpoint']==1.6)
        self.assertEqual((changed['time'],changed['tissues'],changed['cns']),(hold['time'],hold['tissues'],hold['cns']))
        self.assertEqual({r['setpoint'] for r in cc['schedule'] if r['phase'] in ('ascent','deco')},{1.6})
        self.assertLess(cc['tts'],old['tts'])
        self.assertAlmostEqual(cc['profilePoints'][-1]['ppo2'],.90*cc['settings']['surfacePressure'])
        metrics=p.cc_point_metrics(dict(settings=cc['settings'],gases=cc['inventory'],point=hold))
        self.assertAlmostEqual(metrics['projection']['tts'],cc['tts'])
        delayed=p.cc_plan(dict(base,setpointDeco=1.6,duration=30))['cc']
        self.assertAlmostEqual(metrics['projection']['atPlus5'],delayed['tts'])

    def test_deco_setting_is_optional_and_does_not_change_bailout_at_bottom(self):
        base = profile(setpointLow=.7,setpointHigh=1.3)
        old = p.cc_plan(base)
        self.assertEqual(p.cc_plan(dict(base,setpointDeco=''))['cc'],old['cc'])
        changed = p.cc_plan(dict(base,setpointDeco=1.6))
        self.assertEqual(changed['bailout'],old['bailout'])
        with self.assertRaises(ValueError):
            p.cc_plan(dict(base,setpointDeco=1.7))
