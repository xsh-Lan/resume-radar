"""Package the distributable skill without candidate data or evaluation artifacts."""
import argparse
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('scripts', 'assets', 'skills', 'standards', 'third-party-licenses')
FILES = ('requirements.txt', 'README.md', 'THIRD_PARTY_NOTICES.md', 'DESIGN.md')


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
                if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc': continue
                archive.write(path, 'resume-radar/' + path.relative_to(ROOT).as_posix())
    return {'package': str(output), 'bytes': output.stat().st_size}


if __name__ == '__main__':
    from cli_support import configure_stdio
    configure_stdio()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    print(json.dumps(package(parser.parse_args().output), ensure_ascii=False))
