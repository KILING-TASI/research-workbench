"""Explicit local test data selection; does not fetch or change production inputs."""
import os
from pathlib import Path


def fixture_path(assets, name):
    if Path(name).name != name:
        raise ValueError('Fixture name must be a basename')
    supplied = os.environ.get('BJX_VALIDATION_DATA_DIR')
    root = Path(supplied) if supplied else Path(assets)
    path = root / name
    if not path.is_file():
        raise FileNotFoundError(f'Validation data missing: {name}; provide a local BJX_VALIDATION_DATA_DIR. No fixture was fabricated or skipped.')
    return path
