import tempfile, unittest
from pathlib import Path
from make_example import build_example
from workflow import read_json,write_json,validate_run
class DeliveryTests(unittest.TestCase):
 def test_final_cannot_add_unreviewed_completion(self):
  with tempfile.TemporaryDirectory() as d:
   root=build_example(d,'jd');r=read_json(root/'run.json');r.update(delivery_contract='0.16.5',final_text='访谈8名商家，方案已上线并提升营收。');write_json(root/'run.json',r)
   self.assertIn('final_alignment',{e['code'] for e in validate_run(root)['errors']})
 def test_general_final_without_role(self):
  with tempfile.TemporaryDirectory() as d:
   root=build_example(d,'jd');r=read_json(root/'run.json');r.update(delivery_contract='0.16.5',mode='general',target='',target_status='unresolved',final_text='# 示例候选人',market_search={'status':'not_needed','limitations':'通用诊断','attempts':[]});write_json(root/'run.json',r)
   write_json(root/'requirements.json',[]);ds=read_json(root/'diagnosis.json')
   for x in ds:x.update(scope='document',requirement_ids=[])
   write_json(root/'diagnosis.json',ds);self.assertTrue(validate_run(root)['ok'],validate_run(root))
