"""Render every example and fail if any layout check reports a problem.

usage: python3 scripts/selftest.py
"""

import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
EX = os.path.join(HERE, "..", "examples")
sys.path.insert(0, HERE)

from dimdraw import sheet as sheet_mod  # noqa: E402


def main():
    results = {}
    orig_save = sheet_mod.Sheet.save

    def save(self, path, *a, **kw):
        problems = orig_save(self, path, *a, **kw)
        results[os.path.basename(path)] = problems
        return problems

    sheet_mod.Sheet.save = save
    for name in ("template", "handset", "flask", "bracket", "coffee_maker", "car"):
        spec = importlib.util.spec_from_file_location(name, os.path.join(EX, f"{name}.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "main"):
            mod.main()
        elif hasattr(mod, "build") and hasattr(mod, "sheet_one"):
            tmp = tempfile.mkdtemp(prefix="dimdraw-selftest-")
            model = mod.build()
            mod.sheet_one(model).save(os.path.join(tmp, f"{name}-1.svg"), png=False)
            mod.sheet_two(model).save(os.path.join(tmp, f"{name}-2.svg"), png=False)
        else:
            tmp = tempfile.mkdtemp(prefix="dimdraw-selftest-")
            for fn in ("sheet_one", "sheet_two"):
                if hasattr(mod, fn):
                    getattr(mod, fn)().save(os.path.join(tmp, f"{name}-{fn}.svg"), png=False)
    bad = {k: v for k, v in results.items() if v}
    print()
    for k in sorted(results):
        print(f"{'FAIL' if results[k] else 'ok  '}  {k}  ({len(results[k])} problems)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
