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
    def test_report_unifies_review_and_diagnosis(self):
        page=Path(render(self.root,Path(self.tmp.name)/'folded')['html']).read_text(encoding='utf-8')
        parser=Links();parser.feed(page)
        self.assertTrue({'basis','gaps'}<=parser.ids)
        self.assertTrue(all(d.get('class')=='sentence' for d in parser.details))
        self.assertTrue(all('open' not in d for d in parser.details))
        self.assertEqual(page.count('id="sentence-S4"'),1)
        self.assertNotIn('完整审阅与来源',page)
        self.assertTrue(all(t in parser.ids for t in parser.targets))
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
    def test_personal_information_is_preserved_and_can_be_reviewed(self):
        from workflow import read_text
        contact='姓名：张三\n手机：13812345678 邮箱：demo@example.com\n'
        path=Path(self.tmp.name)/'contact.txt';path.write_text(contact,encoding='utf-8')
        self.assertEqual(read_text(path),contact)
        self.mutate('run.json',lambda run:run.update(summary='候选人张三，邮箱demo@example.com，手机号13812345678。'))
        self.assertTrue(validate_run(self.root)['ok'])
        page=Path(render(self.root,Path(self.tmp.name)/'contact')['html']).read_text(encoding='utf-8')
        self.assertIn('张三',page);self.assertIn('demo@example.com',page);self.assertIn('13812345678',page)
        self.assertNotIn('[姓名已删除]',page);self.assertNotIn('[联系方式已删除]',page)
    def test_html_escapes_content(self):
        self.mutate('run.json',lambda a:a.update(summary='<script>alert(1)</script>'))
        page=Path(render(self.root,Path(self.tmp.name)/'out')['html']).read_text(encoding='utf-8')
        self.assertIn('&lt;script&gt;',page); self.assertNotIn('<script>alert(1)</script>',page)
    def test_factual_lead_remains_in_validated_rewrite(self):
        rows=read_json(self.root/'sentence_review.json')
        row=next(v for v in rows if v['evidence_ids'])
        evidence={e['id']:e for e in read_json(self.root/'evidence.json')}
        original=evidence[row['evidence_ids'][0]]['quote']
        row['decision']='rewrite'
        row['text']='【<调研主题>】'+original
        write_json(self.root/'sentence_review.json',rows)
        page=Path(render(self.root,Path(self.tmp.name)/'lead')['html']).read_text(encoding='utf-8')
        self.assertIn('<strong>&lt;调研主题&gt;</strong>',page)
        self.assertNotIn('<调研主题>',page)
        row['text']='【新增999999项成果】'+original
        write_json(self.root/'sentence_review.json',rows)
        self.assertIn('new_numbers',self.codes())
    def overview(self):
        return {'headline':'已有原型交付，验证方法仍需说明','introduction':'访谈与原型工作已有材料支持。',
                'evidence_summary':'访谈和原型交付。','gap_summary':'验证方法尚未说明。',
                'priorities':[{'title':'验证方法','text':'补充方法及选择依据。','diagnosis_ids':['D1']}]}
    def test_overview_invalid_shape_blocks_delivery(self):
        self.mutate('run.json',lambda a:a.update(report_overview=[]))
        self.assertIn('overview',self.codes())
        with self.assertRaises(ValueError):render(self.root,Path(self.tmp.name)/'invalid-overview')
    def test_overall_fit_requires_traceable_requirements_and_evidence(self):
        overview=self.overview()
        req=read_json(self.root/'requirements.json')[0]['id']
        ev=read_json(self.root/'evidence.json')[0]['id']
        overview.update(fit_scope='只对已读取的岗位任务作判断。',eligibility='到岗时间未确认。',
                        assessment=[{'dimension':'需求研究','status':'partial','judgment':'有访谈，选择依据未明确。',
                                     'requirement_ids':[req],'evidence_ids':[ev]}])
        self.mutate('run.json',lambda a:a.update(report_overview=overview))
        self.assertTrue(validate_run(self.root)['ok'],validate_run(self.root))
        page=Path(render(self.root,Path(self.tmp.name)/'fit')['html']).read_text(encoding='utf-8')
        self.assertIn('部分达标',page)
        self.assertIn('到岗时间未确认。',page)
        self.assertNotIn('（一）已有经历依据',page)
        for field,value in [('status','excellent'),('requirement_ids',['R404']),('evidence_ids',[])]:
            broken=copy.deepcopy(overview);broken['assessment'][0][field]=value
            self.mutate('run.json',lambda a:a.update(report_overview=broken))
            self.assertFalse(validate_run(self.root)['ok'])
    def test_overview_priority_requires_actual_diagnosis(self):
        overview=self.overview();overview['priorities'][0]['diagnosis_ids']=['D404']
        self.mutate('run.json',lambda a:a.update(report_overview=overview))
        self.assertIn('reference',self.codes())
    def test_overview_preserves_full_summary_and_escapes_text(self):
        overview=self.overview();overview['headline']='<img src=x onerror=alert(1)>'
        self.mutate('run.json',lambda a:a.update(report_overview=overview))
        self.assertTrue(validate_run(self.root)['ok'])
        page=Path(render(self.root,Path(self.tmp.name)/'overview')['html']).read_text(encoding='utf-8')
        self.assertTrue(read_json(self.root/'run.json')['summary'])
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
