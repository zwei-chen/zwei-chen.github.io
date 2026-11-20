"""Gas routing on hypoxic open-circuit plans. Depths are test inputs."""
import unittest

from test_diving_planner import example, p


def deep_profile(mode='staged', switch=42.5):
    data = example(100, 8, ascentMode=mode)
    bottom = data['gases'][0]
    bottom.update(id='bottom', name='10/70', o2=10, he=70)
    data['gases'].append(dict(bottom, id='travel', name='18/35', o2=18, he=35, switchDepth=switch))
    for segment in data['segments']:
        segment['gas'] = 'bottom'
    return data


class TravelGasTests(unittest.TestCase):
    def test_round_trip_on_staged_variable_and_constant_plans(self):
        for mode in ('staged', 'variable', 'constant'):
            with self.subTest(mode=mode):
                data = deep_profile(mode)
                data.update(useDefaultRates=True, waypoints=[dict(depth=100, duration=8, gas='bottom')])
                result = p.plan(data)
                schedule = result['schedule']
                self.assertEqual(result['points'][0]['gas'], 'travel')
                self.assertEqual([(row['gas'], row['depth']) for row in schedule if row['phase']=='switch'],
                                 [('bottom', 42.5), ('travel', 42.5)])
                descents = [r for r in schedule if r['depth']>r['fromDepth']]
                self.assertEqual([(r['gas'], r['depth']) for r in descents], [('travel', 42.5), ('bottom', 100)])
                self.assertAlmostEqual(sum(row['duration'] for row in descents), 100/18)
                self.assertFalse(any(w['code']=='hypoxia' for w in result['warnings']))
                self.assertEqual(result['points'][-1]['gas'], 'travel')
                self.assertTrue(all(pt['ppo2'] >= .16-1e-8 for pt in result['points']))
                at_bottom = next(pt for pt in result['points'] if pt['depth']==100)
                for gas in result['gases']:
                    total = 0
                    for row in descents:
                        if row['gas'] != gas['id']:
                            continue
                        average_depth = (row['depth'] + row['fromDepth'])/2
                        pressure = 1.01325 + average_depth * 1.03 * .0980665
                        total += row['duration'] * pressure * (16 if row['phase']=='segment' else 12)
                    self.assertAlmostEqual(total, (gas['pressure']-at_bottom['pressures'][gas['id']])*gas['size'], places=5)

    def test_disabled_or_incompatible_travel_gas_fails_to_create_plan(self):
        for change in (dict(enabled=False), dict(switchDepth=2)):
            with self.subTest(change=change):
                data = deep_profile()
                data['gases'][1].update(change)
                with self.assertRaisesRegex(ValueError, '旅行气'):
                    p.plan(data)

    def test_visualization_keeps_the_entered_gas(self):
        result = p.visualize(deep_profile())
        self.assertEqual({pt['gas'] for pt in result['points']}, {'bottom'})

    def test_blank_and_legacy_zero_use_working_ppo2_for_both_switches(self):
        for value in ('', 0, None):
            with self.subTest(value=value):
                data = deep_profile(switch=value)
                result = p.plan(data)
                switches = [r for r in result['schedule'] if r['phase']=='switch']
                self.assertEqual([r['gas'] for r in switches], ['bottom','travel'])
                for row in switches:
                    self.assertAlmostEqual((1.01325 + row['depth']*1.03*.0980665)*.18, 1.4)

    def test_manually_entered_descent_switch_takes_precedence(self):
        data = deep_profile()
        data['segments'][:1] = [dict(depth=30, duration=2, gas='travel'),
                                dict(depth=100, duration=5, gas='bottom')]
        result = p.plan(data)
        self.assertEqual([(r['gas'],r['depth']) for r in result['schedule'] if r['phase']=='switch'],
                         [('bottom',30), ('travel',42.5)])

    def test_travel_handover_between_last_stop_and_surface_has_no_extra_station(self):
        for mode in ('staged', 'variable'):
            data = deep_profile(mode, switch=5.9)
            data['settings']['lastStop']=6
            # A short exposure that can clear at 6 m on the specified gas.
            data['segments'][0].update(depth=25, duration=25/18)
            data['segments'][1]['depth']=25
            result = p.plan(data)
            self.assertEqual(result['points'][-1]['gas'],'travel')
            self.assertEqual([r['depth'] for r in result['schedule'] if r['phase']=='switch'],[5.9,5.9])
            self.assertFalse(any(r['depth']<6 for r in result['schedule'] if r['phase']=='deco'))

    def test_bottom_only_chooses_eligible_bottom_and_ignores_saved_segments(self):
        data = deep_profile()
        data.update(profileMode='bottom',bottom=dict(depth=95,duration=11),useDefaultRates=True,
                    waypoints=[dict(depth=20,duration=15,gas='old-deleted-gas')])
        data['gases'].reverse()
        result = p.plan(data)
        self.assertEqual(result['summary']['maxDepth'],95)
        self.assertEqual(result['points'][0]['gas'],'travel')
        self.assertEqual(result['points'][-1]['depth'],0)
        self.assertTrue(any(r['gas']=='bottom' and r['depth']==r['fromDepth']==95 and r['duration']==11
                            for r in result['schedule']))
        self.assertGreater(result['summary']['decoTime'],0)
        data['gases'][1]['enabled']=False
        with self.assertRaisesRegex(ValueError,'底气'):
            p.plan(data)

    def test_a_richer_deco_gas_stays_available_after_travel_gas(self):
        data = deep_profile()
        data['gases'].append(dict(data['gases'][0], id='deco', o2=50, he=0, switchDepth=20))
        result = p.plan(data)
        switches = [(row['gas'], row['depth']) for row in result['schedule'] if row['phase']=='switch']
        self.assertEqual(switches, [('bottom', 42.5), ('travel', 42.5), ('deco', 20)])

    def test_standard_bottom_gases_follow_depth_table_and_environment(self):
        cases = [(20, 32, 0), (38, 21, 35), (50, 18, 45), (95, 10, 80), (100, 10, 80)]
        for depth, oxygen, helium in cases:
            with self.subTest(depth=depth):
                gases = p.generated_inventory(p.DEFAULTS, dict(depth=depth))
                self.assertEqual((gases[0]['o2'], gases[0]['he']), (oxygen, helium))
        with self.assertRaisesRegex(ValueError, '标准气'):
            p.generated_inventory(p.DEFAULTS, dict(depth=101))
        settings = dict(p.DEFAULTS, ppo2Work=.80)
        gases = p.generated_inventory(settings, dict(depth=30))
        self.assertLessEqual((settings['surfacePressure']+30*settings['density']*.0980665)*gases[0]['o2']/100, .80)

    def test_empty_inventory_generates_working_travel_and_deco_gases(self):
        result = p.plan(dict(profileMode='bottom',bottom=dict(depth=100,duration=15),gases=[]))
        used = {r['gas'] for r in result['schedule'] if r['duration'] > 0}
        self.assertGreaterEqual(len(used),3)
        self.assertEqual(result['summary']['maxDepth'],100)
        self.assertEqual(result['points'][-1]['depth'],0)
        self.assertTrue(all(pt['ppo2']>=.16-1e-8 for pt in result['points']))
        self.assertTrue(all(pt['ppo2']<=1.4+1e-8 for pt in result['points'] if pt['phase']=='segment'))
        self.assertEqual(result['gasSource'],'generated')
        for gas in result['gases']:
            if gas['used']:
                self.assertGreaterEqual(gas['remaining'], result['settings']['reserve']-1e-8)
                self.assertAlmostEqual(gas['remaining'], result['points'][-1]['pressures'][gas['id']])
                self.assertAlmostEqual(gas['used'], gas['cylinderCount']*gas['size']*(gas['pressure']-gas['remaining']))
