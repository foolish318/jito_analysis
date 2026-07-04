from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
JUPYTER = Path(shutil.which('jupyter') or PYTHON.with_name('jupyter'))

COMMANDS = [
    [str(PYTHON), '-m', 'api_sources.pipelines.local_inventory'],
    [str(PYTHON), '-m', 'data_processing.process', '--mode', 'local'],
    [str(PYTHON), '-m', 'data_processing.variables'],
    [str(PYTHON), '-m', 'analysis.main'],
    [str(PYTHON), '-m', 'model_selection.same_dv_iv_extensions'],
    [str(PYTHON), '-m', 'analysis.prediction'],
    [str(PYTHON), '-m', 'analysis.prior_reproduction'],
    [str(PYTHON), '-m', 'pipeline.repo_docs'],
    [
        str(JUPYTER),
        'nbconvert',
        '--to',
        'notebook',
        '--execute',
        str(PKG / 'notebooks' / 'analysis.ipynb'),
        '--output',
        'analysis.ipynb',
        '--output-dir',
        str(PKG / 'notebooks'),
    ],
    [
        str(JUPYTER),
        'nbconvert',
        '--to',
        'notebook',
        '--execute',
        str(PKG / 'notebooks' / 'report.ipynb'),
        '--output',
        'report.ipynb',
        '--output-dir',
        str(PKG / 'notebooks'),
    ],
]


def main() -> int:
    for cmd in COMMANDS:
        print('RUN:', ' '.join(cmd), flush=True)
        subprocess.run(cmd, cwd=str(PKG), check=True)
    print('v27 end-to-end run completed.', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
