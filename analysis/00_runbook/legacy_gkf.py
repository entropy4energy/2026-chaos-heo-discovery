"""Run a script with scikit-learn's GroupKFold as the 2026-09-25 production run
had it.

scikit-learn before 1.6 ordered the groups with np.argsort's default
introsort; 1.6 and later use kind="stable". With every group of size one (the
493 four-cation families are all distinct), the fold of each system is then
decided by how the sort permutes equal keys: the stable sort keeps their
order, NumPy's generic introsort (the code path on Apple silicon, where the
production run was made) does not. The Figure 7 folds of the production run
came from the latter. This wrapper replaces GroupKFold's fold assignment with
the pre-1.6 algorithm and an exact Python copy of NumPy's generic argsort
introsort (numpy/_core/src/npysort/quicksort.cpp, aquicksort_), so that any
machine and any scikit-learn version reproduce those folds. With the
2026-09-25 input, every metric in that run's
13_summary/output/final_metrics.csv is reproduced to within 1e-9 (checked
with scikit-learn 1.9.1 on Linux).

    python3 legacy_gkf.py SCRIPT [ARGS...]
"""
import runpy
import sys

import numpy as np
from sklearn.model_selection import GroupKFold

SMALL_QUICKSORT = 16


def np_generic_argsort(v):
    v = list(v)
    num = len(v)
    t = list(range(num))
    if num < 2:
        return np.array(t)
    stack, depth = [], []
    pl, pr = 0, num - 1
    cdepth = (num.bit_length() - 1) * 2
    while True:
        if cdepth < 0:
            # heapsort fallback (not reached for these inputs)
            seg = sorted(t[pl:pr + 1], key=lambda i: v[i])
            t[pl:pr + 1] = seg
        else:
            while pr - pl > SMALL_QUICKSORT:
                pm = pl + ((pr - pl) >> 1)
                if v[t[pm]] < v[t[pl]]:
                    t[pm], t[pl] = t[pl], t[pm]
                if v[t[pr]] < v[t[pm]]:
                    t[pr], t[pm] = t[pm], t[pr]
                if v[t[pm]] < v[t[pl]]:
                    t[pm], t[pl] = t[pl], t[pm]
                vp = v[t[pm]]
                pi, pj = pl, pr - 1
                t[pm], t[pj] = t[pj], t[pm]
                while True:
                    pi += 1
                    while v[t[pi]] < vp:
                        pi += 1
                    pj -= 1
                    while vp < v[t[pj]]:
                        pj -= 1
                    if pi >= pj:
                        break
                    t[pi], t[pj] = t[pj], t[pi]
                pk = pr - 1
                t[pi], t[pk] = t[pk], t[pi]
                if pi - pl < pr - pi:
                    stack.append((pi + 1, pr))
                    pr = pi - 1
                else:
                    stack.append((pl, pi - 1))
                    pl = pi + 1
                cdepth -= 1
                depth.append(cdepth)
            for i in range(pl + 1, pr + 1):
                vi = t[i]
                vpp = v[vi]
                j = i
                while j > pl and vpp < v[t[j - 1]]:
                    t[j] = t[j - 1]
                    j -= 1
                t[j] = vi
        if not stack:
            break
        pl, pr = stack.pop()
        cdepth = depth.pop()
    return np.array(t)


def _legacy(self, X, y, groups):
    unique_groups, groups = np.unique(groups, return_inverse=True)
    n_samples_per_group = np.bincount(groups)
    indices = np_generic_argsort(n_samples_per_group)[::-1]
    n_samples_per_group = n_samples_per_group[indices]
    n_samples_per_fold = np.zeros(self.n_splits)
    group_to_fold = np.zeros(len(unique_groups))
    for group_index, weight in enumerate(n_samples_per_group):
        lightest_fold = np.argmin(n_samples_per_fold)
        n_samples_per_fold[lightest_fold] += weight
        group_to_fold[indices[group_index]] = lightest_fold
    indices = group_to_fold[groups]
    for f in range(self.n_splits):
        yield np.where(indices == f)[0]


if __name__ == "__main__":
    a = np.random.default_rng(0).integers(0, 5, 300)
    assert (a[np_generic_argsort(a)] == np.sort(a)).all()
    GroupKFold._iter_test_indices = _legacy
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    runpy.run_path(script, run_name="__main__")
