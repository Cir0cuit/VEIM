"""Every catalog entry has an offline freshness Case, or a stated reason not to.

The same rule the icon and README checks apply: a distribution added without
a Case would go back to being tested only by the live sweep, which passes any
old release that still answers.
"""
import importlib
from pathlib import Path

from src.recipes.registry import CATALOG


def _group_modules():
    here = Path(__file__).parent
    for path in sorted(here.glob("test_freshness_*.py")):
        if path.stem != Path(__file__).stem:
            yield path.stem, importlib.import_module(f"tests.{path.stem}")


def test_every_catalog_entry_has_a_freshness_case_or_an_exemption():
    owner, problems = {}, []
    for stem, module in _group_modules():
        for table in ("CASES", "EXEMPT"):
            for key in getattr(module, table, {}):
                if key in owner:
                    problems.append(f"{key}: in {owner[key]} and {stem}.{table}")
                owner[key] = f"{stem}.{table}"
            if table == "EXEMPT":
                problems += [f"{key}: exempt with no reason ({stem})"
                             for key, reason in getattr(module, table, {}).items()
                             if not str(reason).strip()]

    catalog = {cls.key for cls in CATALOG}
    missing = sorted(catalog - owner.keys())
    unknown = sorted(owner.keys() - catalog)
    if missing:
        problems.append(f"no Case and no exemption: {', '.join(missing)}")
    if unknown:
        problems.append(f"not a catalog key: {', '.join(unknown)}")
    assert not problems, "\n".join(problems)
