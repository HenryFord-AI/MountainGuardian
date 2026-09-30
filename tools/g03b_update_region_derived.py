"""One-shot maintenance script: insert the DERIVED static-baseline section.

Deterministically generates the section from the authorized region.json
inputs via the G03B engine (never typed by hand) and inserts it with
minimal text surgery so the rest of the tracked file stays byte-identical.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from riskwatch.region import load_region  # noqa: E402
from riskwatch.engine.static_baseline import (  # noqa: E402
    compute_static_baseline,
    derive_static_baseline_section,
)


def main() -> int:
    path = (
        Path(__file__).resolve().parent.parent
        / "data" / "regions" / "jilong_port" / "region.json"
    )
    text = path.read_text(encoding="utf-8")

    region = load_region()
    baseline = compute_static_baseline(region)
    section = derive_static_baseline_section(baseline, generated_at="2026-10-01")

    section_text = json.dumps(
        {"derived_static_baseline": section}, ensure_ascii=False, indent=2
    )
    lines = section_text.split("\n")
    assert lines[0] == "{" and lines[-1] == "}"
    # json.dumps already indents the wrapper's inner lines by 2 spaces,
    # which is exactly the top-level member indentation of region.json.
    body = "\n".join(lines[1:-1])

    anchor = (
        '    "derivation_boundary": "No B / R / F / D / C / O7 value is '
        'stored or computed in G03A. G03B recomputes B deterministically '
        'from these inputs."\n  },\n'
    )
    assert text.count(anchor) == 1, "anchor not unique"
    text = text.replace(anchor, anchor + body + ",\n")

    old_cv = '"config_version": "g03a-2026-10-01.1"'
    assert text.count(old_cv) == 1
    text = text.replace(old_cv, '"config_version": "g03b-2026-10-01.1"')

    old_lim = (
        "Open-Meteo ECMWF / ERA5-Land values are gridded model and "
        "reanalysis products"
    )
    new_lim = (
        "Open-Meteo ECMWF forecast and ERA5 / ERA5-Land reanalysis values "
        "are gridded model and reanalysis products"
    )
    assert text.count(old_lim) == 1
    text = text.replace(old_lim, new_lim)

    orig = json.loads(path.read_text(encoding="utf-8"))
    new = json.loads(text)
    assert set(new) - set(orig) == {"derived_static_baseline"}
    assert new["config_version"] == "g03b-2026-10-01.1"
    changed = [k for k in orig if orig[k] != new[k]]
    assert changed == ["config_version", "scientific_limitations"], changed
    # nothing else touched: factors, provenance, references unchanged
    assert orig["static_susceptibility_inputs"] == new["static_susceptibility_inputs"]
    assert orig["provenance"] == new["provenance"]
    assert orig["source_references"] == new["source_references"]
    assert orig["monitoring_points"] == new["monitoring_points"]

    path.write_text(text, encoding="utf-8")
    print("OK inserted; B =", repr(baseline.value), "->", baseline.value_rounded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
