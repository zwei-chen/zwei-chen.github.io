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
