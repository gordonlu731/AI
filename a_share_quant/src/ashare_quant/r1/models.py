"""Fixed ridge research models; preprocessing fits TRAINING rows only."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Ridge:
    columns: tuple[str, ...]
    medians: object
    centers: object
    scales: object
    coefficients: object
    alpha: float

    def predict(self, rows):
        return _design(rows, self.columns, self.medians, self.centers, self.scales) @ self.coefficients

    def audit(self):
        return {'columns': list(self.columns), 'medians': self.medians.tolist(), 'centers': self.centers.tolist(),
                'scales': self.scales.tolist(), 'coefficients': self.coefficients.tolist(), 'alpha': self.alpha,
                'missing_indicators': True, 'preprocessing_fit': 'training_only'}


def _matrix(rows, columns):
    import numpy as np
    values = np.array([[np.nan if r.get(k) is None else float(r[k]) for k in columns] for r in rows], dtype=float)
    if values.ndim != 2:
        values = values.reshape(len(rows), len(columns))
    values[~np.isfinite(values)] = np.nan
    return values


def _design(rows, columns, medians, centers, scales):
    import numpy as np
    values = _matrix(rows, columns)
    missing = np.isnan(values)
    filled = np.where(missing, medians, values)
    return np.column_stack([np.ones(len(rows)), (filled - centers) / scales, missing.astype(float)])


def fit_ridge(rows, target, columns, alpha=10.0):
    import numpy as np
    if not rows or len(rows) != len(target) or alpha <= 0 or not np.isfinite(alpha):
        raise ValueError('invalid training data/alpha')
    if len(set(columns)) != len(columns):
        raise ValueError('duplicate feature column')
    values = _matrix(rows, columns)
    medians = np.array([np.median(col[np.isfinite(col)]) if np.isfinite(col).any() else 0.0 for col in values.T])
    filled = np.where(np.isnan(values), medians, values)
    centers = filled.mean(axis=0)
    scales = filled.std(axis=0)
    scales[scales < 1e-12] = 1.0
    design = _design(rows, columns, medians, centers, scales)
    y = np.asarray(target, dtype=float)
    if not np.isfinite(y).all():
        raise ValueError('training targets must be finite')
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return Ridge(tuple(columns), medians, centers, scales, coefficients, alpha)


def cluster_weights(rows, replicates=200, seed=731):
    """Pigeonhole resampling of stock and market-time-block clusters.

    Gives descriptive uncertainty, not an independence assumption or significance.
    """
    import numpy as np
    symbols = sorted({r['symbol'] for r in rows})
    blocks = sorted({r['time_block'] for r in rows})
    symbol_index = np.array([symbols.index(r['symbol']) for r in rows])
    block_index = np.array([blocks.index(r['time_block']) for r in rows])
    rng = np.random.default_rng(seed)
    weights = []
    for _ in range(replicates):
        sw = np.bincount(rng.integers(0, len(symbols), len(symbols)), minlength=len(symbols))
        tw = np.bincount(rng.integers(0, len(blocks), len(blocks)), minlength=len(blocks))
        w = sw[symbol_index] * tw[block_index]
        if w.sum() > 0:
            weights.append(w / w.sum())
    return np.asarray(weights)
