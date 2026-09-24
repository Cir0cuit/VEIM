"""Keep the README's catalog in step with the registry.

The README states how many entries and editions the catalog has, lists the
entries under their categories, and lists every edition of every entry. All
of that is generated from the registry, between markers, so that adding a
recipe or a flavor cannot leave the README describing an older catalog.

    python tools/readme_catalog.py          # print the generated section
    python tools/readme_catalog.py --write  # rewrite it in README.md

tests/test_readme.py fails when README.md differs from what this prints.
"""
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.recipes.registry import registry, CATEGORY_ORDER  # noqa: E402

README = os.path.join(BASE_DIR, "README.md")
START, END = "<!-- catalog:start -->", "<!-- catalog:end -->"
COUNTS = re.compile(r"· \d+ distributions and tools · \d+ editions")


def counts() -> str:
    recipes = registry.get_all_recipes()
    editions = sum(len(r.get_flavors()) for r in recipes)
    return f"· {len(recipes)} distributions and tools · {editions} editions"


def _by_category():
    recipes = registry.get_all_recipes()
    for category in CATEGORY_ORDER:
        members = [r for r in recipes if r.category == category]
        yield category, sorted(members, key=lambda r: r.name.lower())


def section() -> str:
    lines = [START, "", "| Category | Distributions |", "|---|---|"]
    for category, members in _by_category():
        lines.append(f"| **{category}** | {', '.join(r.name for r in members)} |")
    lines += ["", "<details>", "<summary>Every edition, by entry</summary>", ""]
    for category, members in _by_category():
        lines += [f"**{category}**", ""]
        for recipe in members:
            flavors = ", ".join(f.name for f in recipe.get_flavors())
            lines.append(f"- **{recipe.name}** — {flavors}")
        lines.append("")
    lines += ["</details>", "", END]
    return "\n".join(lines)


def render(text: str) -> str:
    """README text with the generated parts brought up to date."""
    start, end = text.index(START), text.index(END) + len(END)
    text = text[:start] + section() + text[end:]
    if not COUNTS.search(text):
        raise SystemExit("README.md has no '· N distributions and tools · N editions' line")
    return COUNTS.sub(counts(), text)


def main() -> int:
    with open(README, encoding="utf-8") as handle:
        current = handle.read()
    wanted = render(current)
    if "--write" in sys.argv[1:]:
        if wanted != current:
            with open(README, "w", encoding="utf-8", newline="") as handle:
                handle.write(wanted)
            print("README.md updated")
        else:
            print("README.md already current")
        return 0
    print(section())
    return 0 if wanted == current else 1


if __name__ == "__main__":
    raise SystemExit(main())
