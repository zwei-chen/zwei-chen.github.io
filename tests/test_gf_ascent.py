"""Regression checks for gas-specific speeds and ceiling-controlled ascents."""
import json
import unittest
from test_diving_planner import example, p


def profile(mode):
    data = example(48, 30, ascentMode=mode, targetGF=65, decoAscentRate=4)
    for name, oxygen, depth in [('ean50', 50, 21), ('oxygen', 100, 5)]:
        data['gases'].append(dict(data['gases'][0], id=name, o2=oxygen, switchDepth=depth))
    return data


class CeilingAscentTests(unittest.TestCase):
    def test_rates_apply_on_the_breathed_gas(self):
        result = p.plan(profile('staged'))
        rows = [r for r in result['schedule'] if r['phase'] == 'ascent']
        self.assertEqual({r['gas'] for r in rows}, {'air', 'ean50', 'oxygen'})
        for row in rows:
            speed = (row['fromDepth']-row['depth']) / row['duration']
            self.assertAlmostEqual(speed, 10 if row['gas'] == 'air' else 4)
        for row in result['schedule']:
            if row['phase'] == 'deco':
                self.assertEqual(row['duration'], int(row['duration']))

    def test_waypoint_timing_uses_enabled_mode_and_gas(self):
        data = profile('staged')
        data.update(useDefaultRates=True, mode='plan', waypoints=[
            dict(depth=22, duration=0, gas='air'), dict(depth=10, duration=0, gas='ean50')])
        self.assertAlmostEqual(p.waypoint_timings(data)['waypointTimings'][1]['travelTime'], 3)
        data['mode']='vision'
        self.assertAlmostEqual(p.waypoint_timings(data)['waypointTimings'][1]['travelTime'], 1.2)

    def test_profiles_follow_limits_and_keep_the_minute_cursor(self):
        for mode in ('variable','constant'):
            with self.subTest(mode=mode):
                result = p.plan(profile(mode))
                points = [pt for pt in result['points'] if pt['phase']=='gf_ascent']
                self.assertEqual(points[-1]['depth'], 0)
                for pt in points:
                    self.assertLessEqual(pt['gf99'], pt['gf'] + 1e-4)
                rows = [r for r in result['schedule'] if r['phase']=='gf_ascent']
                self.assertEqual({r['gas'] for r in rows}, {'air','ean50','oxygen'})
                for r in rows:
                    self.assertLess(r['depth'], r['fromDepth'])
                    self.assertLessEqual((r['fromDepth']-r['depth'])/r['duration'], (10 if r['gas']=='air' else 4)+1e-5)
                times=[result['points'][i]['time'] for i in result['minuteIndices']]
                self.assertEqual(times[:-1], list(range(len(times)-1)))
                self.assertEqual(times[-1], points[-1]['time'])
                self.assertAlmostEqual(rows[-1]['arrivalGF'], rows[-1]['targetGF'], places=3)
                if mode=='constant':
                    self.assertFalse(any(r['phase'] in ('deco','safety') for r in result['schedule']))
                    self.assertGreater(result['summary']['gfAnchor'], 0)
                    self.assertEqual(rows[-1]['targetGF'], 70)
                else:
                    self.assertIsNotNone(result['summary']['gfAnchor'])
                    self.assertEqual(rows[-1]['targetGF'],70)
                    self.assertTrue({3,6,9,12,15,18,21}.issubset({round(r['depth'],6) for r in rows}))

    def test_variable_ascent_stops_and_arrival_peaks(self):
        result = p.plan(example(50, 30, ascentMode='variable'))
        schedule, points = result['schedule'], result['points']
        stops = [r for r in schedule if r['phase'] == 'deco']
        self.assertTrue(stops, 'variable mode must hold at depth between ascent legs')
        anchor = result['summary']['gfAnchor']
        self.assertEqual([r['depth'] for r in stops], list(range(int(anchor), 0, -3)))
        self.assertAlmostEqual(sum(r['duration'] for r in stops), result['summary']['decoTime'])
        peaks = []
        for stop in stops:
            self.assertEqual(stop['fromDepth'], stop['depth'])
            self.assertGreaterEqual(stop['duration'], 1)
            self.assertEqual(stop['duration'], int(stop['duration']))
            i = schedule.index(stop)
            arrival, ascent = schedule[i - 1], schedule[i + 1]
            departure = next(pt for pt in points if abs(pt['time']-stop['runtime'])<1e-8)
            self.assertLess(departure['gf99'], arrival['arrivalGF'])
            self.assertLess(departure['gf99'], ascent['arrivalGF'])
            self.assertEqual(ascent['depth'], stop['depth'] - 3)
            peaks.append(ascent['arrivalGF'])
        self.assertTrue(all(b > a for a, b in zip(peaks, peaks[1:])), peaks)
        self.assertAlmostEqual(peaks[-1], 70, places=3)

    def test_variable_mode_counts_only_grid_stations_as_stops(self):
        data = profile('variable')
        data['settings']['lastStop'] = 6
        data['gases'][1]['switchDepth'] = 14
        result = p.plan(data)
        self.assertIn(14, [r['depth'] for r in result['schedule'] if r['phase']=='switch'])
        stops = [r['depth'] for r in result['schedule'] if r['phase']=='deco']
        self.assertTrue(stops)
        self.assertEqual(stops, list(range(int(stops[0]), 5, -3)))
        self.assertFalse(any(row['gas']=='oxygen' for row in result['schedule']))

    def test_projection_resumes_an_in_progress_station_minute(self):
        result = p.plan(profile('variable'))
        point = next(pt for pt in result['points'] if pt['phase'] == 'deco' and 1.1 < pt['stopElapsed'] < 1.3)
        metrics = p.point_metrics(dict(settings=result['settings'], gases=result['gases'], point=point))
        self.assertAlmostEqual(metrics['projection']['tts'], result['summary']['runtime'] - point['time'], places=4)

    def test_constant_dispatch_and_projection_match_from_bottom(self):
        data=profile('staged')
        response=json.loads(p.handle_json(json.dumps(dict(action='constant_gf', payload=data))))
        self.assertTrue(response['ok'],response.get('error'))
        result=response['result']
        bottom=next(pt for pt in reversed(result['points']) if pt['phase']=='segment')
        metrics=p.point_metrics(dict(settings=result['settings'], gases=result['gases'], point=bottom))
        self.assertAlmostEqual(metrics['projection']['tts'],result['summary']['tts'],delta=.02)
        self.assertEqual(result['settings']['ascentMode'],'constant')

    def test_continuous_ascent_tracks_interpolated_ceiling_from_first_contact(self):
        data = profile('constant')
        data['settings'].update(gfLow=40, gfHigh=85)
        result = p.plan(data)
        anchor = result['summary']['gfAnchor']
        self.assertIsNotNone(anchor)
        self.assertGreater(abs(anchor - 3 * round(anchor / 3)), .001)
        path = [pt for pt in result['points'] if pt['phase']=='gf_ascent' and pt['gfAnchor'] is not None]
        self.assertAlmostEqual(path[0]['depth'], anchor, places=6)
        self.assertAlmostEqual(path[0]['ceilingLow'], anchor, places=5)
        for pt in path:
            self.assertAlmostEqual(pt['gf'], 85 - 45 * pt['depth'] / anchor, places=5)
            self.assertLessEqual(pt['ceiling'], pt['depth'] + 1e-6)
        bound = [pt for pt in path if 3 < pt['depth'] < anchor - 1 and abs(pt['depth'] - pt['ceiling']) < 1e-5]
        self.assertGreater(len(bound), 30)
        midpoint = bound[len(bound)//2]
        metrics = p.point_metrics(dict(settings=result['settings'],point=midpoint,gases=result['gases']))
        self.assertAlmostEqual(metrics['projection']['tts'],result['summary']['runtime']-midpoint['time'],delta=.02)
        expected_ndl = p.ndl(dict(settings=dict(result['settings'],ascentMode='staged'),point=midpoint,
                                  gas=next(g for g in result['gases'] if g['id']==midpoint['gas'])))
        self.assertEqual(metrics['ndl'], expected_ndl)
        data['settings'].update(gfLow=55, gfHigh=75)
        self.assertNotEqual(p.plan(data)['summary']['tts'], result['summary']['tts'])

    def test_equal_pair_reproduces_single_gf_profile_and_ignores_stale_target(self):
        data = profile('constant')
        data['settings'].update(gfLow=65, gfHigh=65, targetGF=25)
        result = p.plan(data)
        self.assertNotIn('targetGF', result['settings'])
        self.assertEqual({pt['gf'] for pt in result['points']}, {65})
        # Reference run of the previous single-target implementation at GF 65.
        self.assertAlmostEqual(result['summary']['tts'],42.3042466621,places=4)
        self.assertAlmostEqual(result['summary']['gasUsed'],3855.5596598,places=3)

    def test_ascent_at_rate_limit_when_target_unreached(self):
        for mode in ('variable','constant'):
            data=example(10,5,ascentMode=mode)
            r=p.plan(data)
            self.assertAlmostEqual(r['summary']['tts'],1)
            self.assertLess(r['points'][-1]['gf99'],r['points'][-1]['gf'])

    def test_constant_midwater_switch_limited_by_ppo2(self):
        data=profile('constant')
        data['gases'][2]['switchDepth']=8
        r=p.plan(data)
        switch=next(pt for pt in r['points'] if pt['phase']=='switch' and pt['gas']=='oxygen')
        self.assertAlmostEqual(switch['ppo2'],r['settings']['ppo2Deco'])

class InstantAscentTests(unittest.TestCase):
    def test_instant_ascent_keeps_stations_and_has_no_travel_exposure(self):
        data = profile('instant')
        result = p.plan(data)
        pts, summary = result['points'], result['summary']
        self.assertGreater(summary['decoTime'], 0)
        self.assertAlmostEqual(summary['tts'], summary['decoTime'])
        stops = [r['depth'] for r in result['schedule'] if r['phase']=='deco']
        self.assertEqual(stops, list(range(int(stops[0]), 0, -3)))
        self.assertEqual({r['gas'] for r in result['schedule'] if r['phase']=='switch'}, {'ean50','oxygen'})
        jumps = [(a,b) for a,b in zip(pts,pts[1:]) if b['depth'] < a['depth']-1e-7]
        self.assertTrue(jumps)
        for a,b in jumps:
            self.assertEqual(a['time'], b['time'])
            self.assertEqual([r[:2] for r in a['tissues']], [r[:2] for r in b['tissues']])
            self.assertEqual((a['cns'],a['pressures']),(b['cns'],b['pressures']))
            self.assertLessEqual(b['ceiling'],b['depth']+1e-6)
        self.assertEqual(pts[result['minuteIndices'][-1]]['depth'],0)
        bottom = next(pt for pt in reversed(pts) if pt['phase']=='segment')
        metrics = p.point_metrics(dict(settings=result['settings'],gases=result['gases'],point=bottom))
        self.assertAlmostEqual(metrics['projection']['tts'],summary['tts'])

    def test_instant_on_waypoints_and_manual_ascents(self):
        data = example(12,2,ascentMode='instant')
        data['segments'].append(dict(depth=6,duration=.6,gas='air'))
        for default in (True,False):
            data['useDefaultRates']=default
            if default: data['waypoints']=[dict(depth=d,duration=t,gas='air') for d,t in [(12,2),(6,0)]]
            result=p.plan(data)
            self.assertAlmostEqual(result['summary']['runtime'],12/18+2)
            self.assertEqual(result['summary']['tts'],0)
            self.assertTrue(result['segments'][-1]['duration']==0)
        deep=example(48,30,ascentMode='instant')
        deep['segments'].append(dict(depth=0,duration=2,gas='air'))
        with self.assertRaisesRegex(ValueError,'减压上限'):
            p.plan(deep)
