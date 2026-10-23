"""Audited local inputs and non-price JSON/CSV outputs."""
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ..data import adjust_bars, read_bars, read_calendar, sha256, calendar_gaps


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path: Path, rows: list[dict], fieldnames=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, allow_nan=False) if isinstance(v, (dict, list, tuple)) else v for k, v in row.items()})


@dataclass
class Dataset:
    symbol: str
    raw: list
    bars: list
    calendar: list
    manifest: dict


def load_dataset(root: Path, symbol: str, case: bool) -> Dataset:
    directory = root / 'data/processed' / ('sina-2026-10-22' if case else f'r1-panel/{symbol}')
    manifest = json.loads((directory / f'{symbol}.manifest.json').read_text())
    csv_path, calendar_path = directory / f'{symbol}.csv', directory / 'calendar.csv'
    if manifest['sha256'] != sha256(csv_path) or manifest['calendar_sha256'] != sha256(calendar_path):
        raise ValueError(f'checksum mismatch: {symbol}')
    if manifest['adjustment'] != 'cumulative_factor' or manifest['volume_unit'] != 'shares':
        raise ValueError('unsupported price/volume basis')
    raw = read_bars(csv_path)
    if raw[-1].date.isoformat() > '2026-10-22':
        raise ValueError('unregistered snapshot cutoff')
    calendar = read_calendar(calendar_path)
    calendar_gaps(raw, calendar)
    return Dataset(symbol, raw, adjust_bars(raw), calendar, manifest)


def load_benchmark(root: Path):
    folder = root / 'data/processed/r1-benchmark'
    manifest = json.loads((folder / 'manifest.json').read_text())
    if sha256(folder / 'sh000001.csv') != manifest['sha256']:
        raise ValueError('benchmark checksum mismatch')
    return read_bars(folder / 'sh000001.csv'), manifest
