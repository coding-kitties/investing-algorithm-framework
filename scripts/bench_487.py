"""Size + speed comparison for issue #487."""
import copy
import os
import tempfile
import time

from investing_algorithm_framework.domain import (
    load_backtests_from_directory,
    save_backtests_to_directory,
)


def dir_size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total


def file_count(path):
    if os.path.isfile(path):
        return 1
    return sum(len(files) for _, _, files in os.walk(path))


def fmt(n):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def main():
    bts = load_backtests_from_directory("examples/batch_one", workers=4)
    bts = [b for b in bts if b.backtest_runs]
    print(f"loaded {len(bts)} non-empty backtests "
          f"(runs each: {[len(b.backtest_runs) for b in bts]})")
    sample = bts[0]

    with tempfile.TemporaryDirectory() as tmp:
        bundle_path = os.path.join(tmp, "sample.iafbt")
        sample.save(bundle_path)
        b1_size = dir_size(bundle_path)
        legacy_path = os.path.join(tmp, "sample_legacy")
        sample.save(legacy_path)
        l1_size = dir_size(legacy_path)
        l1_files = file_count(legacy_path)

    print()
    print("=== ONE backtest ===")
    print(f"  bundle : {fmt(b1_size):>10}   (1 file)")
    print(f"  legacy : {fmt(l1_size):>10}   ({l1_files} files)")
    print(f"  -> bundle {l1_size/b1_size:.1f}x smaller, "
          f"{l1_files}x fewer files")

    print()
    print("=== Extrapolated ===")
    print(f"{'N':>7}  {'bundle':>12}  {'legacy':>12}  "
          f"{'b.files':>10}  {'l.files':>10}")
    for N in (100, 500, 1000, 5000, 10000):
        print(f"{N:>7,}  {fmt(b1_size * N):>12}  "
              f"{fmt(l1_size * N):>12}  "
              f"{N:>10,}  {l1_files * N:>10,}")

    N = 200
    multiplier = (N // len(bts)) + 1
    big = []
    for _ in range(multiplier):
        for b in bts:
            if len(big) >= N:
                break
            clone = copy.deepcopy(b)
            clone.algorithm_id = f"algo_{len(big):05d}"
            big.append(clone)
        if len(big) >= N:
            break

    with tempfile.TemporaryDirectory() as tmp:
        bundle_dir = os.path.join(tmp, "bundles")
        legacy_dir = os.path.join(tmp, "legacy")

        t0 = time.perf_counter()
        save_backtests_to_directory(big, bundle_dir, workers=4,
                                    format="bundle")
        t_save_b = time.perf_counter() - t0
        t0 = time.perf_counter()
        save_backtests_to_directory(big, legacy_dir, workers=1,
                                    format="directory")
        t_save_l = time.perf_counter() - t0

        actual_b = dir_size(bundle_dir)
        actual_l = dir_size(legacy_dir)
        nb = file_count(bundle_dir)
        nl = file_count(legacy_dir)

        t0 = time.perf_counter()
        load_backtests_from_directory(bundle_dir, workers=4)
        t_load_b = time.perf_counter() - t0
        t0 = time.perf_counter()
        load_backtests_from_directory(legacy_dir, workers=1)
        t_load_l = time.perf_counter() - t0

    print()
    print(f"=== VERIFIED with N = {N} ===")
    print(f"  size  bundle : {fmt(actual_b):>10}   "
          f"legacy : {fmt(actual_l):>10}   "
          f"-> bundle {actual_l/actual_b:.1f}x smaller")
    print(f"  files bundle : {nb:>10,}   "
          f"legacy : {nl:>10,}   "
          f"-> bundle {nl/nb:.0f}x fewer")
    print(f"  save  bundle : {t_save_b:7.2f}s   "
          f"legacy : {t_save_l:7.2f}s   "
          f"-> bundle {t_save_l/t_save_b:.2f}x faster")
    print(f"  load  bundle : {t_load_b:7.2f}s   "
          f"legacy : {t_load_l:7.2f}s   "
          f"-> bundle {t_load_l/t_load_b:.2f}x faster")


if __name__ == "__main__":
    main()
