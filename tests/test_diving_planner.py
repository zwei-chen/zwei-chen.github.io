"""Numeric and behavioural checks for the educational dive planner."""
import importlib.util
import math
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('planner', Path(__file__).resolve().parents[1] / 'Diving/vision/planner.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def example(depth=30, duration=20, **settings):
    return {'settings': settings, 'gases': [dict(id='air', name='Air', o2=21, he=0, size=24, pressure=232, switchDepth=0, enabled=True)], 'segments': [dict(depth=depth, duration=depth/18, gas='air'), dict(depth=depth, duration=duration, gas='air')]}


class PlannerTests(unittest.TestCase):
    def test_half_time_and_helium(self):
        start = [(0.79 * (1 - p.WATER_VAPOUR), 0)] * 16
        result = p.load_tissues(start, 4, 4, 4, (0.79, 0))
        expected = (start[0][0] + 0.79 * (4-p.WATER_VAPOUR)) / 2
        self.assertAlmostEqual(result[0][0], expected, places=12)
        self.assertEqual(result[0][1], 0)
        self.assertEqual(p.N2_HALF[0], 4)
        self.assertEqual(p.HE_HALF[0], 1.51)

    def test_schreiner_partition_invariance(self):
        start = [(0.74, 0)] * 16
        whole = p.load_tissues(start, 1, 7, 3, (0.40, 0.42))
        half = p.load_tissues(start, 1, 4, 1.5, (0.40, 0.42))
        split = p.load_tissues(half, 4, 7, 1.5, (0.40, 0.42))
        for a, b in zip(whole, split):
            for x, y in zip(a, b): self.assertAlmostEqual(x, y, places=12)

    def test_shallow_no_deco(self):
        result = p.plan(example(10, 15))
        self.assertEqual(result['summary']['decoTime'], 0)
        self.assertEqual(result['points'][-1]['depth'], 0)
        self.assertEqual(len(result['points'][-1]['tissues']), 16)

    def test_deco_and_ceiling(self):
        result = p.plan(example(40, 35))
        self.assertGreater(result['summary']['decoTime'], 0)
        for point in result['points']:
            if point['phase'] in ('ascent', 'deco', 'switch'):
                self.assertLessEqual(point['ceiling'], point['depth'] + 1e-5)
        self.assertLessEqual(result['points'][-1]['surfaceGF'], 70.0001)

    def test_gas_switch_and_accounting(self):
        data = example(40, 30)
        data['gases'].append(dict(id='ean50', name='EAN50', o2=50, he=0, size=7, pressure=200, switchDepth=21, enabled=True))
        result = p.plan(data)
        switches = [row for row in result['schedule'] if row['phase']=='switch']
        self.assertTrue(switches)
        self.assertLessEqual(switches[0]['depth'],21)
        for gas in result['gases']:
            self.assertAlmostEqual(gas['remaining'], gas['pressure'] - gas['used']/gas['size'], places=6)
        data['gases'][1]['enabled'] = False
        result = p.plan(data)
        self.assertFalse(any(row['gas']=='ean50' for row in result['schedule']))

    def test_published_c_version_profile(self):
        data = example(35,38.25,gfLow=30,gfHigh=85,density=.09985/.0980665,ascentRate=10,descentRate=20)
        data['segments'][0]['duration']=1.75
        result=p.plan(data)
        stops=[(row['depth'],row['duration']) for row in result['schedule'] if row['phase']=='deco']
        self.assertEqual(stops,[(18,1),(15,1),(12,4),(9,6),(6,14),(3,26)])
        self.assertEqual(result['summary']['decoTime'],52)

    def test_manual_ascent_cannot_skip_first_stop(self):
        data=example(40,35)
        data['segments'].append(dict(depth=12,duration=28/9,gas='air'))
        with self.assertRaisesRegex(ValueError,'手动分段'): p.plan(data)

    def test_shallow_switch_cannot_bypass_last_stop(self):
        data=example(40,35,lastStop=6)
        data['gases'].append(dict(id='oxygen',name='Oxygen',o2=100,he=0,size=7,pressure=200,switchDepth=5,enabled=True))
        result=p.plan(data)
        self.assertTrue(any(w['code']=='switch' for w in result['warnings']))
        for row in result['schedule']:
            if row['phase']=='deco': self.assertGreaterEqual(row['depth'],6)

    def test_zero_duration_switch_is_visible(self):
        data=example(40,30,switchTime=0)
        data['gases'].append(dict(id='ean50',name='EAN50',o2=50,he=0,size=7,pressure=200,switchDepth=21,enabled=True))
        result=p.plan(data)
        switches=[row for row in result['schedule'] if row['phase']=='switch']
        self.assertEqual(switches[0]['duration'],0)

    def test_oxygen_units_and_range(self):
        rate,otu=p.oxygen_rate(1.01325)
        self.assertAlmostEqual(rate,100/300)
        self.assertAlmostEqual(otu,1)
        self.assertAlmostEqual(p.oxygen_rate(1.6*1.01325)[0]*45,100)
        self.assertIsNone(p.oxygen_rate(1.7*1.01325)[0])

    def test_switch_wait_does_not_hide_decompression(self):
        data=example(20,24,switchTime=0)
        data['gases'].append(dict(id='ean50',name='EAN50',o2=50,he=0,size=7,pressure=200,switchDepth=3,enabled=True))
        no_switch_wait=p.plan(data)
        data['settings']['switchTime']=1
        with_switch_wait=p.plan(data)
        self.assertEqual(with_switch_wait['summary']['firstStop'],3)
        self.assertEqual(with_switch_wait['summary']['decoTime'],1)
        self.assertAlmostEqual(no_switch_wait['summary']['runtime'],with_switch_wait['summary']['runtime'])

    def test_switch_dwell_can_create_decompression(self):
        data=example(30,10,gfLow=30,gfHigh=85,switchTime=5)
        data['gases'].append(dict(id='ean22',name='EAN22',o2=22,he=0,size=12,pressure=200,switchDepth=30,enabled=True))
        result=p.plan(data)
        self.assertEqual(result['summary']['gfAnchor'],9)
        stops=[row for row in result['schedule'] if row['phase']=='deco']
        self.assertEqual([row['depth'] for row in stops],[9,6,3])
        self.assertTrue(any(point['gf']<85 for point in result['points'] if point['phase']=='ascent'))

    def test_optional_stop_when_final_segment_is_exactly_five_metres(self):
        data=example(10,10,safetyStop=3)
        data['segments'].append(dict(depth=5,duration=5/9,gas='air'))
        stops=[row for row in p.plan(data)['schedule'] if row['phase']=='safety']
        self.assertEqual([(row['depth'],row['duration']) for row in stops],[(5,3)])

    def test_invalid_inputs(self):
        for settings in [dict(gfLow=90,gfHigh=70), dict(ascentRate=0), dict(surfacePressure=float('nan'))]:
            with self.subTest(settings=settings), self.assertRaises(ValueError): p.plan(example(**settings))
        data = example()
        data['gases'][0]['he'] = 90
        with self.assertRaises(ValueError): p.plan(data)
        data = example()
        data['segments'][0]['gas'] = 'missing'
        with self.assertRaises(ValueError): p.plan(data)

    def test_reserve_warning(self):
        data = example(30, 25)
        data['gases'][0]['pressure'] = 50
        self.assertTrue(any(w['code']=='gas' for w in p.plan(data)['warnings']))

    def test_sac(self):
        result = p.sac(dict(size=12,start=200,end=100,duration=40,depth=10,surfacePressure=1,density=1/0.0980665/10))
        self.assertAlmostEqual(result['sac'],15)
        with self.assertRaises(ValueError): p.sac(dict(size=12,start=100,end=200,duration=40,depth=10))


if __name__ == '__main__': unittest.main()
