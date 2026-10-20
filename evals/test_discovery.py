"""New provenance, diagnosis sharing and progressive-disclosure invariants."""
import copy
from pathlib import Path
from types import SimpleNamespace
import test_workflow as fixtures
from workflow import add_jd, read_json, write_json, validate_run
from render_report import render

# Reuse isolated fixtures without inheriting and rerunning every legacy test.
import unittest
class DiscoveryTests(unittest.TestCase):
    setUp=fixtures.WorkflowTests.setUp
    tearDown=fixtures.WorkflowTests.tearDown
    mutate=fixtures.WorkflowTests.mutate
    codes=fixtures.WorkflowTests.codes

    def import_job(self,role='产品实习',url='https://example.org/jobs/product-intern'):
        text=Path(self.tmp.name)/'public-jd.txt'
        text.write_text('虚构招聘测试样本：参与调研及原型设计。',encoding='utf-8')
        return add_jd(SimpleNamespace(run_dir=self.root,file=text,url=url,role=role,title='虚构产品实习',company='测试公司',location='上海',level='实习',published_at='unknown',retrieved_at='2026-10-20',availability='unknown',redact_name=[]))

    def use_job(self):
        self.import_job()
        self.mutate('requirements.json',lambda rows:rows[0].update(basis='sample_jd',source_unit_ids=['JOB1-U001'],basis_note='虚构离线测试样本，不代表实际招聘。'))
        self.mutate('run.json',lambda run:run.update(market_search={'status':'partial','limitations':'仅一个虚构离线样本。','attempts':[{'role':'产品实习','query':'离线测试，不执行搜索','searched_at':'2026-10-20','outcome':'测试数据导入'}]}))
        self.mutate('run.json',lambda run:run.update(status='reviewed',review={'status':'completed','findings':['已复核测试样本及关联要求。']}))

    def test_imported_job_resets_review(self):
        self.import_job()
        self.assertIn('review',self.codes())
        source=read_json(self.root/'sources.json')['sources'][-1]
        self.assertEqual(source['kind'],'jd_sample')
        self.assertEqual(source['metadata']['availability'],'unknown')

    def test_duplicate_job_url_reuses_original_source(self):
        self.import_job()
        with self.assertRaises(ValueError):self.import_job()
        self.assertEqual(len(read_json(self.root/'sources.json')['sources']),3)

    def test_invalid_url_and_date_do_not_write_source(self):
        for url in ('javascript:alert(1)','file:///secret','https://user:password@example.org/job'):
            with self.assertRaises(ValueError):self.import_job(url=url)
        self.assertEqual(len(read_json(self.root/'sources.json')['sources']),2)

    def test_retrieved_jd_can_ground_direction_requirements(self):
        self.use_job()
        self.mutate('run.json',lambda run:run.update(mode='direction'))
        self.mutate('requirements.json',lambda rows:rows[1].update(basis='role_standard',source_unit_ids=[],basis_note='方向假设。'))
        result=validate_run(self.root)
        self.assertTrue(result['ok'],result)
        page=Path(render(self.root,Path(self.tmp.name)/'jobs')['html']).read_text(encoding='utf-8')
        parser=fixtures.Links();parser.feed(page)
        self.assertTrue(all(t in parser.ids for t in parser.targets))
        self.assertIn('https://example.org/jobs/product-intern',page)
        self.assertIn('状态待核实',page)

    def test_sample_cannot_belong_to_another_direction(self):
        self.use_job()
        self.mutate('requirements.json',lambda rows:rows[0].update(role='数据分析'))
        self.assertIn('job_role',self.codes())

    def test_resume_cannot_serve_as_retrieved_jd(self):
        self.use_job()
        self.mutate('requirements.json',lambda rows:rows[0].update(source_unit_ids=['RESUME-U002']))
        self.assertIn('basis',self.codes())

    def test_job_cannot_prove_candidate_contribution(self):
        self.use_job()
        source=read_json(self.root/'sources.json')['sources'][-1]
        self.mutate('evidence.json',lambda rows:rows[0].update(source_id='JOB1',unit_id='JOB1-U001',quote=source['text']))
        self.assertIn('candidate_evidence',self.codes())

    def test_search_pending_blocks_delivery(self):
        self.mutate('run.json',lambda run:run.update(market_search={'status':'pending','attempts':[],'limitations':''}))
        self.assertIn('market_search',self.codes())
        with self.assertRaises(ValueError):render(self.root,Path(self.tmp.name)/'blocked')

    def test_failed_search_can_deliver_honest_limits(self):
        self.mutate('requirements.json',lambda rows:[r.update(basis='role_standard',source_unit_ids=[],basis_note='方向假设。') for r in rows])
        self.mutate('run.json',lambda run:run.update(mode='direction',market_search={'status':'failed','limitations':'工具不可用，未获得 JD；仅方向假设。','attempts':[{'role':'产品实习','query':'未执行：工具不可用','searched_at':'2026-10-20','outcome':'未执行搜索'}]}))
        self.assertTrue(validate_run(self.root)['ok'],validate_run(self.root))

    def test_complete_search_requires_actual_sources(self):
        self.mutate('run.json',lambda run:run.update(market_search={'status':'complete','limitations':'','attempts':[{'role':'产品实习','query':'产品实习','searched_at':'2026-10-20','outcome':'自称成功'}]}))
        self.assertIn('market_search',self.codes())

    def test_search_date_and_job_metadata_checked(self):
        self.use_job()
        self.mutate('sources.json',lambda data:data['sources'][-1]['metadata'].update(retrieved_at='yesterday',url='javascript:alert(1)'))
        self.assertTrue({'job_date','job_url'}<=self.codes())

    def test_same_root_cause_cannot_be_duplicated(self):
        self.mutate('diagnosis.json',lambda rows:rows.append(dict(rows[0],id='D2')))
        self.assertIn('duplicate_diagnosis',self.codes())

    def test_one_diagnosis_can_serve_multiple_edits(self):
        self.mutate('sentence_review.json',lambda rows:rows[2].update(diagnosis_ids=['D1']))
        self.assertTrue(validate_run(self.root)['ok'])
        page=Path(render(self.root,Path(self.tmp.name)/'shared')['html']).read_text(encoding='utf-8')
        question=read_json(self.root/'diagnosis.json')[0]['question']
        self.assertEqual(page.count(question),1)
        self.assertEqual(page.count('id="diagnosis-D1"'),1)
        self.assertEqual(page.count('href="#diagnosis-D1"'),0)

    def test_focused_and_full_preserve_all_source_units(self):
        pages=[]
        for mode in ('focused','full'):
            self.mutate('run.json',lambda run:run.update(display_mode=mode))
            page=Path(render(self.root,Path(self.tmp.name)/mode)['html']).read_text(encoding='utf-8')
            pages.append(page)
            parser=fixtures.Links();parser.feed(page)
            self.assertTrue({'sentence-'+v['id'] for v in read_json(self.root/'sentence_review.json')}<=parser.ids)
        for page in pages:
            parser=fixtures.Links();parser.feed(page)
            self.assertEqual(len(parser.details),len(read_json(self.root/'sentence_review.json')))
            self.assertTrue(all(d.get('class')=='sentence' for d in parser.details))

    def test_legacy_run_still_valid(self):
        self.mutate('run.json',lambda run:run.update(schema_version='2.0'))
        self.mutate('diagnosis.json',lambda rows:rows[0].pop('issue_key'))
        self.assertTrue(validate_run(self.root)['ok'])

    def test_shared_diagnosis_is_not_injected_into_local_sentence(self):
        self.mutate('diagnosis.json',lambda rows:rows[0].update(does_not_demonstrate='这段全局判断不属于当前原句'))
        page=Path(render(self.root,Path(self.tmp.name)/'local')['html']).read_text(encoding='utf-8')
        self.assertNotIn('这段全局判断不属于当前原句',page)
        for v in read_json(self.root/'sentence_review.json'):
            self.assertIn(v['reason'],page)

    def test_only_one_disclosure_and_three_fields_per_review(self):
        from html.parser import HTMLParser
        class Layout(HTMLParser):
            def __init__(self):super().__init__();self.depth=0;self.max_depth=0;self.fields=[];self.capture=False
            def handle_starttag(self,tag,attrs):
                if tag=='details':self.depth+=1;self.max_depth=max(self.max_depth,self.depth)
                if tag=='h4' and self.depth:self.capture=True
            def handle_endtag(self,tag):
                if tag=='details':self.depth-=1
                if tag=='h4':self.capture=False
            def handle_data(self,data):
                if self.capture:self.fields.append(data)
        page=Path(render(self.root,Path(self.tmp.name)/'structure')['html']).read_text(encoding='utf-8')
        layout=Layout();layout.feed(page)
        self.assertEqual(layout.max_depth,1)
        self.assertEqual(layout.fields,['原文','改后','原因与建议']*len(read_json(self.root/'sentence_review.json')))
