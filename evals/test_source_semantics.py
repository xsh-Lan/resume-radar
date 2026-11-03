import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from source_semantics import is_layout_symbol, presentation_reviews


class SourceSemanticsTests(unittest.TestCase):
    def test_bullets_are_layout_but_language_and_operators_are_content(self):
        for text in ['\uf075', '•', ' ◆ ', '\uf0b7', '▪\n']:
            self.assertTrue(is_layout_symbol(text), repr(text))
        for text in ['C++', 'C#', 'F1', '50%', '+', '−', '*', '1.', '• 项目正文', '', '\ue123']:
            self.assertFalse(is_layout_symbol(text), repr(text))

    def test_legacy_symbol_reviews_disappear_without_mutating_the_ledger(self):
        resume = {'units':[{'id':'U1','text':'\uf075'}, {'id':'U2','text':'RAG知识库'},
                           {'id':'U3','text':'C++'}]}
        reviews = [{'id':'S1','unit_ids':['U1'],'decision':'drop'},
                   {'id':'S2','unit_ids':['U2','U1'],'decision':'merge'},
                   {'id':'S3','unit_ids':['U3'],'decision':'keep'}]
        original = copy.deepcopy(reviews)
        visible, layout = presentation_reviews(resume, reviews)
        self.assertEqual([r['id'] for r in visible], ['S2','S3'])
        self.assertEqual(visible[0]['unit_ids'], ['U2'])
        self.assertEqual(layout, ['U1'])
        self.assertEqual(reviews, original)


if __name__ == '__main__': unittest.main()
