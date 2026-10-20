import copy
import json
import subprocess
import sys
import tempfile
import shutil
import uuid
import unittest
from pathlib import Path
from types import SimpleNamespace
from html.parser import HTMLParser
from make_example import build_example
from workflow import validate_run,read_json,write_json,make_source,add_source,snapshot
from render_report import render
from sanitize_report import process_files

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.ids=set(); self.targets=[]; self.details=[]; self.anchor_count=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.add(a['id'])
        if tag=='details':self.details.append(a)
        if tag=='a':self.anchor_count+=1
        if tag=='a' and a.get('href','').startswith('#'):self.targets.append(a['href'][1:])

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.scratch=(Path(__file__).resolve().parents[1]/'.eval-tmp').resolve()
        self.scratch.mkdir(exist_ok=True)
        directory=self.scratch/uuid.uuid4().hex
        directory.mkdir()
        self.tmp=SimpleNamespace(name=str(directory))
        self.root=build_example(directory/'jd','jd')
    def tearDown(self):
        directory=Path(self.tmp.name).resolve()
        if directory.parent!=self.scratch or len(directory.name)!=32:
            raise RuntimeError('Refusing to delete outside isolated evaluation scratch')
        shutil.rmtree(directory)
    def mutate(self,file,callback):
        data=read_json(self.root/file); callback(data); write_json(self.root/file,data)
    def codes(self): return {e['code'] for e in validate_run(self.root)['errors']}
    def test_three_modes_render_and_real_links(self):
        for mode in ('jd','direction','explore'):
            root=self.root if mode=='jd' else build_example(Path(self.tmp.name)/mode,mode)
            result=validate_run(root); self.assertTrue(result['ok'],result)
            self.assertEqual(result['counts']['resume_units'],result['counts']['reviewed'])
            page=Path(render(root,Path(self.tmp.name)/('out-'+mode))['html']).read_text(encoding='utf-8')
            parser=Links(); parser.feed(page)
            self.assertTrue(all(t in parser.ids for t in parser.targets))
            self.assertNotIn('没有编造事实',page)
    def test_quote_must_exist(self):
        self.mutate('evidence.json',lambda a:a[1].update(quote='这句不存在'))
        self.assertIn('quote',self.codes())
    def test_report_defaults_to_collapsed_details_without_jump_links(self):
        page=Path(render(self.root,Path(self.tmp.name)/'folded')['html']).read_text(encoding='utf-8')
        parser=Links();parser.feed(page)
        self.assertGreaterEqual(len([d for d in parser.details if d.get('class')=='report-section']),5)
        self.assertTrue(all('open' not in d for d in parser.details))
        self.assertEqual(parser.anchor_count,0)
        self.assertIn('overall',parser.ids)
    def test_plain_word_headings_preserve_source_and_sections(self):
        text='教育经历\n某大学\n项目经历\n某项目。\n'
        source=make_source(text,'X','resume')
        self.assertEqual([u['section'] for u in source['units']],['教育经历','教育经历','项目经历','项目经历'])
        self.assertTrue(all(text[u['start']:u['end']]==u['text'] for u in source['units']))
    def test_english_sentences_decimal_and_source_spans(self):
        text='Used Python 3.14. Built a prototype.\n完成访谈。结果待确认！\n'
        source=make_source(text,'X','resume')
        self.assertEqual(len(source['units']),4)
        self.assertEqual(''.join(u['text'] for u in source['units']),text.replace('\n',''))
        self.assertTrue(all(text[u['start']:u['end']]==u['text'] for u in source['units']))
    def test_conservative_draft_also_needs_supported_numbers(self):
        self.mutate('sentence_review.json',lambda a:a[3].update(text='预计咨询量下降99%。'))
        self.assertIn('new_numbers',self.codes())
    def test_source_tamper(self):
        self.mutate('sources.json',lambda a:a['sources'][0].update(text='替换后的新来源'))
        self.assertIn('source_hash',self.codes()); self.assertIn('source_units',self.codes())
    def test_cannot_drop_unit_from_source_ledger(self):
        self.mutate('sources.json',lambda a:a['sources'][0]['units'].pop())
        self.assertIn('source_units',self.codes())
    def test_missing_review_blocks_render(self):
        self.mutate('sentence_review.json',lambda a:a.pop())
        self.assertIn('coverage',self.codes())
        with self.assertRaises(ValueError):render(self.root,Path(self.tmp.name)/'blocked')
        self.assertFalse((Path(self.tmp.name)/'blocked').exists())
    def test_duplicate_coverage(self):
        self.mutate('sentence_review.json',lambda a:a.append(dict(a[1],id='S99')))
        self.assertIn('coverage',self.codes())
    def test_new_number_rejected(self):
        self.mutate('sentence_review.json',lambda a:a[1].update(decision='rewrite',text='访谈80名商家。'))
        self.assertIn('new_numbers',self.codes())
    def test_ownership_upgrade_rejected(self):
        self.mutate('sentence_review.json',lambda a:a[1].update(decision='rewrite',text='主导商家调研。'))
        self.assertIn('ownership_upgrade',self.codes())
    def test_expected_result_not_completed(self):
        self.mutate('sentence_review.json',lambda a:a[3].update(decision='rewrite',text='已上线并提升咨询效果。'))
        self.assertIn('completion_upgrade',self.codes())
    def test_unknown_is_not_confirmed_gap(self):
        self.mutate('diagnosis.json',lambda a:a[0].update(gap_type='experience_gap'))
        self.assertIn('unconfirmed_gap',self.codes())
    def test_nojd_cannot_create_hard_requirement(self):
        self.root=build_example(Path(self.tmp.name)/'direction','direction')
        self.mutate('requirements.json',lambda a:a[0].update(importance='hard'))
        self.assertIn('hard_requirement',self.codes())
    def test_jd_requires_actual_jd_reference(self):
        self.mutate('requirements.json',lambda a:a[0].update(source_unit_ids=['RESUME-U002']))
        self.assertIn('basis',self.codes())
    def test_user_confirmation_needs_answer_source(self):
        self.mutate('evidence.json',lambda a:a[1].update(status='user_confirmed'))
        self.assertIn('evidence_status',self.codes())
    def test_explore_roles_require_actual_evidence(self):
        self.root=build_example(Path(self.tmp.name)/'explore','explore')
        self.mutate('run.json',lambda a:a['role_options'][0].update(evidence_ids=[]))
        self.assertIn('roles',self.codes())
    def test_keep_cannot_silently_rewrite(self):
        self.mutate('sentence_review.json',lambda a:a[1].update(text='已经更改'))
        self.assertIn('keep_changed',self.codes())
    def test_new_source_invalidates_completed_review(self):
        answer=Path(self.tmp.name)/'answer.txt'; answer.write_text('尚未设计验证方法。',encoding='utf-8')
        result=add_source(SimpleNamespace(run_dir=self.root,kind='followup',file=answer,redact_name=[]))
        self.assertEqual(result['source_id'],'FOLLOWUP1'); self.assertIn('review',self.codes())
    def test_confirmed_absence_can_be_recorded(self):
        answer=make_source('尚未设计验证方法。','FOLLOWUP1','followup')
        self.mutate('sources.json',lambda a:a['sources'].append(answer))
        self.mutate('evidence.json',lambda a:a.append({'id':'E6','source_id':'FOLLOWUP1','unit_id':'FOLLOWUP1-U001','quote':answer['text'],'status':'user_confirmed','actor':'individual','action':'确认尚未设计验证方法','completion':'actual'}))
        self.mutate('diagnosis.json',lambda a:a[0].update(gap_type='experience_gap',confirmed_by_user=True,confirmation_evidence_ids=['E6'],evidence_ids=['E3','E6']))
        self.mutate('requirements.json',lambda a:a[1].update(support='missing'))
        self.assertTrue(validate_run(self.root)['ok'],validate_run(self.root))
    def test_nonstandard_output_filename_and_visible_errors(self):
        path=Path(self.tmp.name)/'AI产品经理.html'; path.write_text('姓名：示例\n邮箱：demo@example.com\n电话：13812345678\n学校：某大学\n访谈8名商家。',encoding='utf-8')
        other=Path(self.tmp.name)/'untouched.txt'; other.write_text('other@example.com',encoding='utf-8')
        result=process_files([path]); self.assertTrue(result['ok'])
        self.assertIn('某大学',path.read_text(encoding='utf-8')); self.assertIn('8名',path.read_text(encoding='utf-8'))
        self.assertNotIn('demo@example.com',path.read_text(encoding='utf-8')); self.assertEqual(other.read_text(encoding='utf-8'),'other@example.com')
        self.assertFalse(process_files([Path(self.tmp.name)/'missing.txt'])['ok'])
    def test_html_escapes_content(self):
        self.mutate('run.json',lambda a:a.update(summary='<script>alert(1)</script>'))
        page=Path(render(self.root,Path(self.tmp.name)/'out')['html']).read_text(encoding='utf-8')
        self.assertIn('&lt;script&gt;',page); self.assertNotIn('<script>alert(1)</script>',page)
    def overview(self):
        return {'headline':'已有原型交付，验证方法仍需说明','introduction':'访谈与原型工作已有材料支持。',
                'evidence_summary':'访谈和原型交付。','gap_summary':'验证方法尚未说明。',
                'priorities':[{'title':'验证方法','text':'补充方法及选择依据。','diagnosis_ids':['D1']}]}
    def test_overview_invalid_shape_blocks_delivery(self):
        self.mutate('run.json',lambda a:a.update(report_overview=[]))
        self.assertIn('overview',self.codes())
        with self.assertRaises(ValueError):render(self.root,Path(self.tmp.name)/'invalid-overview')
    def test_overview_priority_requires_actual_diagnosis(self):
        overview=self.overview();overview['priorities'][0]['diagnosis_ids']=['D404']
        self.mutate('run.json',lambda a:a.update(report_overview=overview))
        self.assertIn('reference',self.codes())
    def test_overview_preserves_full_summary_and_escapes_text(self):
        overview=self.overview();overview['headline']='<img src=x onerror=alert(1)>'
        self.mutate('run.json',lambda a:a.update(report_overview=overview))
        self.assertTrue(validate_run(self.root)['ok'])
        page=Path(render(self.root,Path(self.tmp.name)/'overview')['html']).read_text(encoding='utf-8')
        self.assertIn(read_json(self.root/'run.json')['summary'],page)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;',page)
        self.assertNotIn('<img src=x onerror=alert(1)>',page)
        parser=Links();parser.feed(page)
        expected={'sentence-'+v['id'] for v in read_json(self.root/'sentence_review.json')}
        self.assertTrue(expected<=parser.ids)
    def test_snapshot_isolated(self):
        target=Path(snapshot(self.root)['snapshot']); before=read_json(target/'run.json')
        self.mutate('run.json',lambda a:a.update(summary='后续版本'))
        self.assertEqual(read_json(target/'run.json'),before)
    def test_cli_invalid_input_fails(self):
        script=Path(__file__).resolve().parents[1]/'scripts/workflow.py'
        result=subprocess.run([sys.executable,str(script),'validate','--run-dir',str(Path(self.tmp.name)/'missing')],capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(result.returncode,0); self.assertFalse(json.loads(result.stdout)['ok'])

if __name__=='__main__': unittest.main()
