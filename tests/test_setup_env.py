"""Check Windows setup isolation without downloading or installing dependencies."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest


pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows setup scripts')
PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_project(tmp_path):
    project = tmp_path / 'project with spaces'
    project.mkdir()
    for name in ('setup_env.ps1', 'setup_env.bat'):
        shutil.copyfile(PROJECT / name, project / name)
    subprocess.run(
        [sys.executable, '-I', '-m', 'venv', '--without-pip', str(project / 'venv')],
        check=True, capture_output=True,
    )
    (project / 'requirements.txt').write_text('# Offline setup test\n')
    (project / 'download_models.py').write_text(
        "from pathlib import Path\n"
        "Path(__file__).with_name('models-ran').touch()\n"
    )
    fake_pip = project / 'venv' / 'Lib' / 'site-packages' / 'pip'
    fake_pip.mkdir()
    (fake_pip / '__init__.py').write_text('')
    (fake_pip / '__main__.py').write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "with Path(os.environ['SETUP_AUDIT']).open('a') as log:\n"
        "    log.write(json.dumps({'args': sys.argv[1:], 'prefix': sys.prefix,\n"
        "                          'env': dict(os.environ)}) + '\\n')\n"
        "stage = 'upgrade' if '--upgrade' in sys.argv else 'dependencies'\n"
        "sys.exit(9 if os.environ.get('SETUP_FAIL') == stage else 0)\n"
    )
    return project


def run_setup(project, suffix='ps1', fail=''):
    env = os.environ.copy()
    env.update({
        'SETUP_AUDIT': str(project / 'audit.jsonl'), 'SETUP_FAIL': fail,
        'PIP_NO_INDEX': '1',
        'PIP_TARGET': str(project.parent / 'outside-target'),
        'PIP_PREFIX': str(project.parent / 'outside-prefix'),
        'PIP_ROOT': str(project.parent / 'outside-root'),
        'PIP_PYTHON': sys.executable, 'PIP_USER': 'true',
        'PIP_CONFIG_FILE': str(project.parent / 'outside-pip.ini'),
        'PYTHONHOME': str(project.parent / 'invalid-python-home'),
        'PYTHONPATH': str(project.parent / 'outside-imports'),
    })
    script = str(project / f'setup_env.{suffix}')
    command = (
        ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script]
        if suffix == 'ps1' else ['cmd.exe', '/d', '/c', script]
    )
    return subprocess.run(
        command, cwd=project.parent, env=env, input='',
        capture_output=True, text=True, timeout=30,
    )


@pytest.mark.parametrize('suffix', ['ps1', 'bat'])
def test_setup_uses_only_project_venv_from_another_directory(setup_project, suffix):
    result = run_setup(setup_project, suffix)
    assert result.returncode == 0, result.stdout + result.stderr
    records = [json.loads(line) for line in (setup_project / 'audit.jsonl').read_text().splitlines()]
    assert len(records) == 2
    venv = setup_project / 'venv'
    for record in records:
        assert Path(record['prefix']) == venv
        assert '--require-virtualenv' in record['args']
        assert '--no-user' in record['args']
        env = record['env']
        for name in ('PIP_TARGET', 'PIP_PREFIX', 'PIP_ROOT', 'PIP_PYTHON', 'PYTHONHOME', 'PYTHONPATH'):
            assert not env.get(name)
        assert env['PIP_CONFIG_FILE'] == 'nul'
        assert env['PIP_USER'] == 'false'
        assert Path(env['PIP_CACHE_DIR']) == venv / '.cache' / 'pip'
        assert Path(env['TEMP']) == Path(env['TMP']) == venv / '.tmp'
    assert Path(records[1]['args'][-1]) == setup_project / 'requirements.txt'
    assert (setup_project / 'models-ran').is_file()
    assert not (setup_project.parent / 'venv').exists()


@pytest.mark.parametrize('suffix', ['ps1', 'bat'])
@pytest.mark.parametrize('fail,call_count', [('upgrade', 1), ('dependencies', 2)])
def test_setup_stops_immediately_when_pip_fails(setup_project, suffix, fail, call_count):
    result = run_setup(setup_project, suffix=suffix, fail=fail)
    assert result.returncode != 0
    assert len((setup_project / 'audit.jsonl').read_text().splitlines()) == call_count
    assert not (setup_project / 'models-ran').exists()


def test_fresh_setup_installs_local_wheel_only_into_venv(setup_project):
    fresh = setup_project.parent / 'fresh project'
    shutil.copytree(setup_project, fresh, ignore=shutil.ignore_patterns('venv'))
    wheel = fresh / 'setup_probe-1.0-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('setup_probe.py', 'VALUE = 42\n')
        archive.writestr('setup_probe-1.0.dist-info/METADATA',
                         'Metadata-Version: 2.1\nName: setup-probe\nVersion: 1.0\n')
        archive.writestr('setup_probe-1.0.dist-info/WHEEL',
                         'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
        archive.writestr('setup_probe-1.0.dist-info/RECORD', '')
    (fresh / 'requirements.txt').write_text(wheel.as_uri() + '\n')
    result = run_setup(fresh)
    assert result.returncode == 0, result.stdout + result.stderr
    installed = fresh / 'venv' / 'Lib' / 'site-packages' / 'setup_probe.py'
    assert installed.is_file()
    assert (fresh / 'models-ran').is_file()
    assert not (fresh.parent / 'outside-target').exists()
    assert not (fresh.parent / 'outside-prefix').exists()
    assert not (fresh.parent / 'outside-root').exists()


def test_setup_rejects_venv_with_system_packages(setup_project):
    config = setup_project / 'venv' / 'pyvenv.cfg'
    config.write_text(config.read_text().replace(
        'include-system-site-packages = false', 'include-system-site-packages = true',
    ))
    result = run_setup(setup_project)
    assert result.returncode != 0
    assert not (setup_project / 'audit.jsonl').exists()
    assert not (setup_project / 'models-ran').exists()
