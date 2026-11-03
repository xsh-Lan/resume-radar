"""Behavioral checks for original-document coordinates and reference boundaries."""
import hashlib
import json
import os
import subprocess
import shutil
import sys
import unittest
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from workflow import initialize, make_source, read_json, write_json
from pdf_source import read_pdf, locate_units, pdf_module
from example_library import library
from workbench import render_workbench
from package_skill import package
from make_example import build_example, RESUME


def make_pdf(path, lines, rotate=0):
    fitz = pdf_module()
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    for index, line in enumerate(lines):
        page.insert_text((42, 64 + index * 38), line, fontsize=12, fontname='china-s')
    if rotate: page.set_rotation(rotate)
    doc.save(str(path)); doc.close()
    return path


class PdfWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(__file__).resolve().parents[1] / '.eval-tmp'
        self.path = self.scratch / uuid.uuid4().hex
        self.path.mkdir(parents=True)

    def tearDown(self):
        assert self.path.resolve().parent == self.scratch.resolve()
        shutil.rmtree(self.path)

    def test_duplicate_sentences_use_source_offsets(self):
        path = make_pdf(self.path / 'repeat.pdf', ['Repeated source sentence.', 'Repeated source sentence.'])
        pdf = read_pdf(path)
        source = make_source(pdf['text'], 'RESUME', 'resume')
        locations = locate_units(pdf, source['units'])
        values = list(locations.values())
        self.assertEqual(len(values), 2)
        self.assertTrue(all(x['status'] == 'matched' for x in values))
        self.assertLess(values[0]['rects'][0]['rect'][1], values[1]['rects'][0]['rect'][1])

    def test_external_repeated_quote_is_not_guessed(self):
        path = make_pdf(self.path / 'repeat.pdf', ['Prefix', 'Repeated source sentence.', 'Repeated source sentence.'])
        pdf = read_pdf(path)
        source = make_source('Repeated source sentence.', 'RESUME', 'resume')
        self.assertEqual(next(iter(locate_units(pdf, source['units']).values()))['status'], 'ambiguous')

    def test_rotated_coordinates_stay_inside_original_page(self):
        path = make_pdf(self.path / 'rotated.pdf', ['Selectable PDF content.'], rotate=90)
        pdf = read_pdf(path)
        locations = locate_units(pdf, make_source(pdf['text'], 'RESUME', 'resume')['units'])
        self.assertTrue(all(0 <= n <= 1 for loc in locations.values() for box in loc['rects'] for n in box['rect']))
        self.assertEqual(pdf['pages'][0]['width'], 842)

    def test_image_only_pdf_rejected_before_run_created(self):
        fitz = pdf_module(); doc = fitz.open(); page = doc.new_page()
        pix = fitz.Pixmap(fitz.csRGB, (0, 0, 1, 1), False); pix.clear_with(255)
        page.insert_image(page.rect, stream=pix.tobytes('png'))
        path = self.path / 'scan.pdf'; doc.save(str(path)); doc.close()
        target = self.path / 'blocked'
        with self.assertRaises(ValueError):
            initialize(SimpleNamespace(resume=str(path), run_dir=str(target), jd=None, candidate_key='scan', target='', stage=''))
        self.assertFalse(target.exists())

    def test_pdf_intake_preserves_original_bytes(self):
        path = make_pdf(self.path / 'source.pdf', ['Selectable PDF content.'])
        target = self.path / 'run'
        initialize(SimpleNamespace(resume=str(path), run_dir=str(target), jd=None, candidate_key='test', target='产品经理', stage=''))
        self.assertEqual(path.read_bytes(), (target / 'original.pdf').read_bytes())
        self.assertEqual(read_json(target / 'pdf-origin.json')['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def fixture(self):
        root = build_example(self.path / 'analysis', 'jd')
        pdf = make_pdf(self.path / 'source.pdf', RESUME.splitlines())
        return root, pdf

    def test_pdf_report_maps_all_units_and_keeps_original(self):
        root, pdf = self.fixture()
        result = render_workbench(root, self.path / 'report', pdf)
        self.assertEqual(result['validation']['pdf_mapping']['unresolved'], [])
        self.assertEqual(pdf.read_bytes(), (self.path / 'report/original.pdf').read_bytes())
        self.assertEqual(result['library_cases'], 2125)

    def test_wrong_original_and_invalid_case_links_block_delivery(self):
        root, pdf = self.fixture()
        write_json(root / 'pdf-origin.json', {'sha256': 'wrong', 'filename': 'source.pdf'})
        with self.assertRaises(ValueError): render_workbench(root, self.path / 'blocked', pdf)
        (root / 'pdf-origin.json').unlink()
        write_json(root / 'example_links.json', [{'review_id': 'S4', 'case_id': 'invented', 'reason': 'x', 'conditions': 'y'}])
        with self.assertRaises(ValueError): render_workbench(root, self.path / 'blocked', pdf)
        self.assertFalse((self.path / 'blocked').exists())

    def test_other_careers_cannot_receive_product_examples(self):
        root, pdf = self.fixture()
        run = read_json(root / 'run.json'); run['example_library_scope'] = 'other'; write_json(root / 'run.json', run)
        case_id = next(iter(library()['cases']))
        write_json(root / 'example_links.json', [{'review_id': 'S4', 'case_id': case_id, 'reason': 'x', 'conditions': 'y'}])
        with self.assertRaises(ValueError): render_workbench(root, self.path / 'blocked', pdf)

    def test_package_contains_resources_and_no_candidate_data(self):
        target = self.path / 'skill.zip'; package(target)
        with zipfile.ZipFile(target) as archive:
            names = archive.namelist()
            self.assertIn('resume-radar/SKILL.md', names)
            self.assertNotIn('resume-radar/skills/resume-radar/SKILL.md', names)
            self.assertNotIn('resume-radar/skills/resume-radar/agents/openai.yaml', names)
            self.assertEqual(sum(name.endswith('/SKILL.md') for name in names), 4)
            self.assertIn('resume-radar/assets/hired-library/release.json', names)
            self.assertFalse(any('.eval-tmp' in name or '/profile/' in name or 'original.pdf' in name or 'excellent-resume-patterns' in name for name in names))

    def test_cli_emits_utf8_under_windows_legacy_encoding(self):
        env = dict(os.environ, PYTHONIOENCODING='gbk')
        script = Path(__file__).resolve().parents[1] / 'scripts/example_library.py'
        case_id = next(iter(library()['cases']))
        result = subprocess.run([sys.executable, str(script), '--case-id', case_id], env=env, capture_output=True)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout.decode('utf-8'))
        self.assertIn('产品', data['roleName'])


if __name__ == '__main__': unittest.main()
