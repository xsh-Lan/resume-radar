"""Package the distributable skill without candidate data or evaluation artifacts."""
import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('scripts', 'assets', 'skills', 'standards', 'third-party-licenses')
FILES = ('requirements.txt', 'README.md', 'PRODUCT.md', 'CHANGELOG.md', 'PRIVACY.md',
         'THIRD_PARTY_NOTICES.md', 'DESIGN.md')
PROMOTED_ENTRIES = {'skills/resume-radar/SKILL.md', 'skills/resume-radar/agents/openai.yaml'}
RUNTIME_FOLDERS = {'__pycache__', '.git', '.eval-tmp', 'profile', 'runs', 'report', 'reports',
                   'sessions', 'job-sources', 'confirmation-replies', 'candidate-data'}
RUNTIME_FILES = {'run.json', 'sources.json', 'evidence.json', 'requirements.json', 'diagnosis.json',
                 'sentence_review.json', 'confirmation.json', 'auth.json', 'original.pdf',
                 'optimized-resume.md', 'goal-values.json', 'plan-values.json', 'target-values.json'}
ASSET_FILES = {'assets/confirm.html', 'assets/report.css', 'assets/workbench.html',
               'assets/workbench.css', 'assets/workbench.js'}


def distributable(relative):
    """Only program resources are installable; runtime records stay outside."""
    if any(part in RUNTIME_FOLDERS for part in relative.parts): return False
    if relative.name in RUNTIME_FILES or relative.name.startswith('.env'): return False
    name = relative.as_posix()
    if name in PROMOTED_ENTRIES: return False
    category = relative.parts[0]
    if category == 'scripts': return len(relative.parts) == 2 and relative.suffix == '.py'
    if category == 'assets':
        return name in ASSET_FILES or (name.startswith('assets/hired-library/') and relative.suffix == '.json')
    if category == 'skills': return relative.suffix in {'.md', '.yaml'}
    if category == 'standards': return relative.suffix in {'.md', '.json'}
    if category == 'third-party-licenses': return relative.suffix in {'.txt', '.md'}
    return False


def package(output):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(ROOT / 'skills/resume-radar/SKILL.md', 'resume-radar/SKILL.md')
        archive.write(ROOT / 'skills/resume-radar/agents/openai.yaml', 'resume-radar/agents/openai.yaml')
        for name in FILES:
            archive.write(ROOT / name, 'resume-radar/' + name)
        for directory in DIRECTORIES:
            for path in sorted((ROOT / directory).rglob('*')):
                if not path.is_file() or path.is_symlink() or not distributable(path.relative_to(ROOT)): continue
                archive.write(path, 'resume-radar/' + path.relative_to(ROOT).as_posix())
    return {'package': str(output), 'bytes': output.stat().st_size}


if __name__ == '__main__':
    from cli_support import configure_stdio
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    print(json.dumps(package(parser.parse_args().output), ensure_ascii=False))
