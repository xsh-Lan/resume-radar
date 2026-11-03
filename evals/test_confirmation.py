import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from confirm import confirm, execution_ready
from workflow import read_json, write_json, validate_run
from make_example import build_example


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = build_example(Path(self.temp.name) / 'sample', 'jd')

    def tearDown(self): self.temp.cleanup()

    def goal(self, source='provided', choice='specified'):
        return confirm(self.root, 1, {'target_choice': choice, 'target': '产品实习', 'jd_source': source, 'focus': ['项目经历']}, {})

    def plan(self, state):
        ids = [] if state['stage1']['route'] == '03' else ['JD']
        prefill = {'stage1_hash': state['stage1_hash'], 'jobs': [{'source_id': 'JD'}] if ids else []}
        values = {'target':'产品实习', 'selected_jd_ids':ids, 'capabilities':'调研与原型交付', 'modification_scope':'项目经历', 'sentence_review':False, 'optimized_resume':False}
        return prefill, values

    def test_unclear_target_is_a_distinct_route(self):
        state = self.goal('auto', 'unclear')
        self.assertEqual(state['stage1']['target'], '')
        self.assertEqual(state['stage1']['target_route'], 'discover')
        self.assertEqual(state['stage1']['route'], '02')

    def test_three_routes_require_real_confirmation(self):
        for source, route in [('provided','01'),('auto','02'),('none','03')]:
            state = self.goal(source)
            self.assertEqual(state['stage1']['route'], route)
            with self.assertRaises(ValueError): execution_ready(self.root)
            prefill, values = self.plan(state)
            confirm(self.root, 2, values, prefill)
            self.assertIn('stage2', execution_ready(self.root))

    def test_changed_goal_invalidates_plan(self):
        state = self.goal(); prefill, values = self.plan(state)
        confirm(self.root, 2, values, prefill)
        self.goal('none')
        with self.assertRaises(ValueError): execution_ready(self.root)
        with self.assertRaises(ValueError): confirm(self.root, 2, values, prefill)

    def test_unknown_jd_and_changed_source_are_blocked(self):
        state = self.goal(); prefill, values = self.plan(state)
        values['selected_jd_ids'] = ['invented']
        with self.assertRaises(ValueError): confirm(self.root, 2, values, prefill)
        values['selected_jd_ids'] = ['JD']; confirm(self.root, 2, values, prefill)
        sources = read_json(self.root / 'sources.json'); sources['sources'][1]['sha256'] = 'changed'; write_json(self.root / 'sources.json', sources)
        with self.assertRaises(ValueError): execution_ready(self.root)

    def test_guided_delivery_gate_and_general_mode(self):
        run = read_json(self.root / 'run.json'); run['workflow_version'] = '0.14'; write_json(self.root / 'run.json', run)
        self.assertIn('confirmation', {e['code'] for e in validate_run(self.root)['errors']})
        state = self.goal('none'); prefill, values = self.plan(state); confirm(self.root, 2, values, prefill)
        run.update(mode='general',market_search={'status':'not_needed','limitations':'通用诊断，不分析目标岗位。','attempts':[]})
        write_json(self.root / 'run.json', run); write_json(self.root / 'requirements.json', [])
        diagnoses = read_json(self.root / 'diagnosis.json')
        for d in diagnoses: d.update(scope='document', requirement_ids=[])
        write_json(self.root / 'diagnosis.json', diagnoses)
        result=validate_run(self.root)
        self.assertTrue(result['ok'], result)


if __name__ == '__main__': unittest.main()
