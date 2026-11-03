import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from confirm import confirm, execution_ready, record_reply, record_target
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

    def test_codex_reply_gate_and_receipt_integrity(self):
        response = self.root / 'answer.txt'
        response.write_text('', encoding='utf-8')
        values = {'target_choice':'unclear','jd_source':'none','focus':['项目经历']}
        with self.assertRaises(ValueError): record_reply(self.root, 1, values, {}, response)
        self.assertFalse((self.root / 'confirmation.json').exists())
        response.write_text('没有明确方向，先通用诊断，重点看项目经历。', encoding='utf-8')
        state = record_reply(self.root, 1, values, {}, response)
        self.assertEqual(state['conversation_receipts']['1']['channel'], 'codex')
        prefill, plan = self.plan(state)
        response.write_text('按这个方案分析，不需要逐句清单和优化全文。', encoding='utf-8')
        record_reply(self.root, 2, plan, prefill, response)
        self.assertIn('stage2', execution_ready(self.root))
        (self.root / 'confirmation-replies/stage1.txt').write_text('changed', encoding='utf-8')
        with self.assertRaises(ValueError): execution_ready(self.root)

    def target(self, source='provided', **changes):
        answer = self.root / 'target-answer.txt'
        answer.write_text('使用我提供的JD；若不明确则由你推荐。', encoding='utf-8')
        values = dict(target_choice='specified', target='产品实习', jd_source=source,
                      selected_jd_ids=[] if source == 'none' else ['JD'])
        values.update(changes)
        return record_target(self.root, values, answer)

    def test_single_target_has_fixed_outputs_and_no_second_gate(self):
        for source in ('provided', 'none'):
            state = self.target(source)
            self.assertNotIn('stage2', state)
            self.assertTrue(state['outputs']['optimized_resume'])
            self.assertTrue(state['outputs']['sentence_review'])
            self.assertFalse(state['outputs']['followup_questions'])
            self.assertEqual(execution_ready(self.root)['kind'], 'single_target')

    def test_delegated_search_records_resolved_job_without_another_answer(self):
        sources = read_json(self.root / 'sources.json')
        job = next(s for s in sources['sources'] if s['id'] == 'JD')
        job['kind'] = 'jd_sample'
        write_json(self.root / 'sources.json', sources)
        state = self.target('auto', target_choice='unclear', delegated=True)
        self.assertTrue(state['target_decision']['delegated'])
        self.assertEqual(execution_ready(self.root)['target_decision']['route'], '02')
        with self.assertRaises(ValueError): self.target('auto', selected_jd_ids=[])

    def test_single_target_rejects_changed_sources_and_fake_output_gate(self):
        self.target()
        sources = read_json(self.root / 'sources.json')
        next(s for s in sources['sources'] if s['id'] == 'JD')['sha256'] = 'changed'
        write_json(self.root / 'sources.json', sources)
        with self.assertRaises(ValueError): execution_ready(self.root)
        self.target()
        state = read_json(self.root / 'confirmation.json')
        state['outputs']['followup_questions'] = True
        write_json(self.root / 'confirmation.json', state)
        with self.assertRaises(ValueError): execution_ready(self.root)

    def test_v016_accepts_single_target_and_requires_optimized_text(self):
        self.target()
        run = read_json(self.root / 'run.json')
        run['workflow_version'] = '0.16'
        run['final_text'] = '# 示例候选人'
        run['report_overview'] = {'headline':'产品实习申请：调研与原型有依据，验证方法待补充','introduction':'按已有材料作条件判断。','evidence_summary':'访谈与原型','gap_summary':'验证方法','assessment':[{'dimension':'需求调研','judgment':'有直接材料','status':'met','requirement_ids':['R1'],'evidence_ids':['E2']}],'fit_scope':'仅依据本次材料','eligibility':'到岗约束未核实','priorities':[]}
        write_json(self.root / 'run.json', run)
        self.assertTrue(validate_run(self.root)['ok'])
        run['final_text'] = ''; write_json(self.root / 'run.json', run)
        self.assertIn('confirmation', {e['code'] for e in validate_run(self.root)['errors']})

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
        run = read_json(self.root / 'run.json')
        for version in ('0.14', '0.15'):
            run['workflow_version'] = version; write_json(self.root / 'run.json', run)
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
