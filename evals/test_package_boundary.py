import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from package_skill import distributable


class PackageBoundaryTests(unittest.TestCase):
    def test_runtime_records_do_not_enter_install_package(self):
        for name in ['scripts/auth.json', 'assets/original.pdf', 'assets/portrait.png',
                     'skills/resume-radar/report/notes.md', 'skills/resume-radar/confirmation-replies/reply.md',
                     'skills/resume-radar/optimized-resume.md', 'standards/run.json',
                     'skills/resume-radar/SKILL.md', 'scripts/__pycache__/workflow.py']:
            self.assertFalse(distributable(Path(name)), name)

    def test_required_program_and_fixed_library_resources_remain(self):
        for name in ['scripts/workflow.py', 'assets/workbench.html',
                     'assets/hired-library/cases/COMMON.json',
                     'skills/resume-refiner/SKILL.md', 'skills/resume-radar/references/workbench.md',
                     'standards/scoring_calibration.json', 'third-party-licenses/resume-refiner-MIT.txt']:
            self.assertTrue(distributable(Path(name)), name)


if __name__ == '__main__': unittest.main()
