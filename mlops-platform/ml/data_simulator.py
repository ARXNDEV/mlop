import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ml.train import generate_dataset


STREAM_DIR = Path(__file__).resolve().parent / "data" / "stream"


def reset() -> None:
    if STREAM_DIR.exists():
        shutil.rmtree(STREAM_DIR)
    STREAM_DIR.mkdir(parents=True, exist_ok=True)


def get_current_batch(step: int) -> pd.DataFrame:
    path = STREAM_DIR / f"step_{step:03d}.csv"
    return pd.read_csv(path)


def _progress(i: int, total: int) -> None:
    width = 30
    filled = int(width * (i / total))
    bar = "#" * filled + "-" * (width - filled)
    sys.stdout.write(f"\r[{bar}] {i}/{total}")
    sys.stdout.flush()
    if i == total:
        sys.stdout.write("\n")


def simulate_drift(*, steps: int = 50, drift_magnitude: float = 0.3) -> None:
    reset()

    base = generate_dataset(n_samples=5000, random_state=42).drop(columns=["target"])
    x0 = base.to_numpy()

    total_shift = float(drift_magnitude)
    shift_per_step = total_shift / float(steps)
    means = x0.mean(axis=0)
    stds = x0.std(axis=0)

    for step in range(1, steps + 1):
        shift = (shift_per_step * step) * np.sign(means + 1e-6)
        noise = np.random.default_rng(42 + step).normal(loc=0.0, scale=0.10, size=x0.shape)
        x_step = x0 + shift + noise * stds
        df_step = pd.DataFrame(x_step, columns=[f"f{i}" for i in range(x_step.shape[1])])
        out_path = STREAM_DIR / f"step_{step:03d}.csv"
        df_step.to_csv(out_path, index=False)
        _progress(step, steps)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--steps", type=int, default=50)
    p.add_argument("--drift-magnitude", type=float, default=0.3)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    simulate_drift(steps=args.steps, drift_magnitude=args.drift_magnitude)


if __name__ == "__main__":
    main()
