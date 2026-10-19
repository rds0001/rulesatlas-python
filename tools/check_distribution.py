"""Check release metadata and exercise the installed wheel and source archive."""
import hashlib
import json
import os
from email.parser import Parser
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.work/release-check'
WORK.mkdir(parents=True, exist_ok=True)
DIST = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'dist'
wheels = list(DIST.glob('rulesatlas-*.whl'))
sources = list(DIST.glob('rulesatlas-*.tar.gz'))
assert len(wheels) == len(sources) == 1, 'Expected one wheel and one source archive'
with zipfile.ZipFile(wheels[0]) as archive:
    metadata_file = next(p for p in archive.namelist() if p.endswith('.dist-info/METADATA'))
    metadata = Parser().parsestr(archive.read(metadata_file).decode())
    license_file = next(p for p in archive.namelist() if p.endswith('/licenses/LICENSE'))
    assert metadata['Name'] == 'rulesatlas'
    assert metadata['License-Expression'] == 'MIT'
    assert metadata['Author'] or metadata['Author-email'], 'Release author is required'
    assert 'TODO_' not in archive.read(metadata_file).decode(), 'Complete author metadata first'
    assert 'TODO_' not in archive.read(license_file).decode(), 'Complete copyright metadata first'
    assert not any(p.startswith('ruleatlas/') for p in archive.namelist())

smoke = '''
import os
from pathlib import Path
import rulesatlas as r
from rulesatlas.builtin import PACKS
assert Path(r.__file__).resolve().is_relative_to(Path(os.environ['RULESATLAS_TEST_TARGET']))
assert r.__version__ == os.environ['RULESATLAS_TEST_VERSION']
assert len(r.list_games()) == len(PACKS) == 212
for profile_id, pack in PACKS.items():
    state = r.new_state(profile_id, players=[{'id': f'p{i}'} for i in range(pack['participants']['min'])])
    assert r.validate_state(state)['valid'], profile_id
    r.legal_actions(state)
    r.outcome(state)
print('Installed import and 212 bounded initial-state checks passed.')
'''
env = os.environ.copy()
env.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
for key in ('TMPDIR', 'TMP', 'TEMP'):
    env[key] = str(WORK)
results = []
for artifact in (wheels[0], sources[0]):
    with tempfile.TemporaryDirectory(prefix='installed-', dir=WORK) as target:
        env.update(PYTHONPATH=target, RULESATLAS_TEST_TARGET=target,
                   RULESATLAS_TEST_VERSION=metadata['Version'])
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps',
                        '--no-build-isolation', '--no-cache-dir', '--disable-pip-version-check',
                        '--target', target, str(artifact)], check=True, cwd=ROOT, env=env)
        subprocess.run([sys.executable, '-c', smoke], check=True, cwd=ROOT, env=env)
        subprocess.run([sys.executable, '-m', 'pytest', '--capture=sys', '-q'], check=True, cwd=ROOT, env=env)
    results.append(dict(file=artifact.name, bytes=artifact.stat().st_size,
                        sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                        installed_tests='passed', initial_states=212))
report = dict(name='rulesatlas', version=metadata['Version'], status='passed', artifacts=results)
(WORK / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
