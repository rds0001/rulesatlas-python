"""Keep pytest scratch data inside the authorized workspace, even for direct runs."""
import os
from pathlib import Path
import tempfile
import uuid
ROOT=Path(__file__).resolve().parent
TMP=ROOT/'.work/tmp'
TMP.mkdir(parents=True,exist_ok=True)
for key in ('TMPDIR','TMP','TEMP'): os.environ[key]=str(TMP)
tempfile.tempdir=str(TMP)
def pytest_configure(config):
    (ROOT/".work/pytest").mkdir(parents=True,exist_ok=True)
    config.option.basetemp=str(ROOT/'.work/pytest'/f'run-{uuid.uuid4().hex}')
