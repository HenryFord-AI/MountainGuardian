"""
MountainGuardian G03C – Risk Watch end-to-end demo smoke.

Runs the FULL run_risk_scan() workflow (all 10 gate steps) and prints the
result in the gate §19 demo format.

Modes (bounded, honest, no unnecessary calls):
  * default (offline): deterministic weather fixture through the real G03A
    normalize contract, cached G03A climatology references, NO provider —
    the AI layer runs in explicit deterministic fallback mode
    (scenario C of doc 04 §50). Zero network calls, zero cost.
  * --live-weather: real Open-Meteo forecast requests (2 point calls,
    30-minute raw cache) instead of the fixture.
  * --ai: use the real DeepSeek provider (requires DEEPSEEK_API_KEY; at
    most 5 generation calls — Remote Sensing short-circuits SKIPPED
    before any provider call in v1.0).
  * --live: --live-weather --ai against the REAL runtime snapshot db
    (the scan becomes real trend history). Without --live the smoke writes
    to a separate scratch db so fixture scans never pollute real history.

Usage (from the repository / worktree root):
    python tools/g03c_smoke.py [--runtime-dir DIR] [--region REGION_ID]
                               [--live] [--live-weather] [--ai]
                               [--recent-mm X] [--forecast-mm Y]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestration.risk_watch_orchestrator import run_risk_scan  # noqa: E402
from riskwatch.climatology import ClimatologyStore, runtime_dir  # noqa: E402
from riskwatch.region import load_region  # noqa: E402
from riskwatch.weather import WeatherCollector, normalize_weather  # noqa: E402


def build_fixture_collector(recent_mm: float, forecast_mm: float):
    """Deterministic offline collector over the real G03A normalize
    contract (same fixture discipline as tools/g03b_smoke.py)."""
    from riskwatch.weather import RegionWeatherResult

    retrieval_time = datetime.now(timezone.utc).isoformat()
    center = date.fromisoformat(retrieval_time[:10])

    times, precip = [], []
    day = center - timedelta(days=7)
    for i in range(14):
        times.append(day.isoformat())
        precip.append(recent_mm / 7.0 if i < 7 else forecast_mm / 7.0)
        day += timedelta(days=1)
    payload = {
        "latitude": None, "longitude": None, "generationtime_ms": 0.0,
        "utc_offset_seconds": 0, "timezone": "UTC",
        "timezone_abbreviation": "UTC", "elevation": None,
        "daily_units": {"time": "iso8601", "precipitation_sum": "mm",
                        "temperature_2m_max": "degC",
                        "temperature_2m_min": "degC"},
        "daily": {"time": times, "precipitation_sum": precip,
                  "temperature_2m_max": [8.0] * 14,
                  "temperature_2m_min": [-3.0] * 14},
    }

    class FixtureCollector:
        def collect_region(self, region):
            points = {
                p.point_id: normalize_weather(
                    payload, p, retrieval_time=retrieval_time,
                    request_time=retrieval_time)
                for p in region.monitoring_points}
            return RegionWeatherResult(
                region_id=region.region_id,
                retrieval_time=retrieval_time,
                status="OK",
                points=points,
                coverage={"required_points_total": len(points),
                          "required_points_ok": len(points),
                          "required_points_failed": 0, "failed_points": [],
                          "evidence_coverage_reduced": False})

    return FixtureCollector()


def _driver_labels(top_drivers: list, limit: int = 4) -> list:
    """Gate §19 demo shape: the leading static susceptibility plus the
    dynamic precipitation drivers (deterministic contribution order)."""
    labels = []
    for d in top_drivers:
        label = d["label"].split("(")[0].strip()
        kind = d.get("driver_type", "")
        if kind == "DYNAMIC":
            label = f"{label} [{d.get('monitoring_point_id') or 'regional'}]"
        entry = f"{label} ({d['contribution_points_rounded']} pts)"
        if entry not in labels:
            labels.append(entry)
        if len(labels) >= limit:
            break
    return labels


def main(argv: list[str] | None = None) -> int:
    # Windows consoles may default to a non-UTF-8 codepage; the demo output
    # contains Chinese text and must never render as mojibake.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="jilong_port")
    parser.add_argument(
        "--runtime-dir",
        default=os.environ.get("MOUNTAINGUARDIAN_RUNTIME_DIR")
        or str(runtime_dir()),
        help="runtime dir holding climatology/ and the snapshot db")
    parser.add_argument("--live", action="store_true",
                        help="real Open-Meteo + real DeepSeek + real db")
    parser.add_argument("--live-weather", action="store_true",
                        help="real Open-Meteo requests (implies real db "
                             "only together with --live)")
    parser.add_argument("--ai", action="store_true",
                        help="use the real DeepSeek provider (needs "
                             "DEEPSEEK_API_KEY)")
    parser.add_argument("--recent-mm", type=float, default=55.0)
    parser.add_argument("--forecast-mm", type=float, default=35.0)
    args = parser.parse_args(argv)

    live_weather = args.live or args.live_weather
    use_ai = args.live or args.ai

    runtime = Path(args.runtime_dir)
    region = load_region(args.region)
    store = ClimatologyStore(runtime / "climatology")
    for point in region.monitoring_points:
        if store.load(point.point_id) is None:
            print(
                f"SMOKE BLOCKED: no G03A climatology reference for "
                f"{point.point_id} under {runtime}. Materialize it once "
                f"with `python -m riskwatch.climatology` (this smoke never "
                f"downloads 30 years of archive data).")
            return 3

    if live_weather:
        collector = WeatherCollector()   # real Open-Meteo, 30-min cache
        db_path = runtime / "mountainguardian.db"
    else:
        collector = build_fixture_collector(args.recent_mm,
                                            args.forecast_mm)
        db_path = runtime / "g03c_smoke.db"   # scratch — never real history

    provider = "auto" if use_ai else None
    if use_ai and not os.environ.get("DEEPSEEK_API_KEY"):
        print("SMOKE BLOCKED: --ai/--live needs DEEPSEEK_API_KEY in the "
              "environment (authorized secret chain).")
        return 3

    result = run_risk_scan(
        args.region,
        provider=provider,
        runtime_dir=runtime,
        db_path=db_path,
        collector=collector,
    )

    det = result.deterministic_result.to_dict()
    disp = det["display"]
    region_name = str(region.data.get("region_name", result.region_id))
    agents_done = sum(
        1 for r in result.agent_results.values()
        if r.status.value in ("COMPLETED", "DEGRADED", "SKIPPED"))
    agent_states = ", ".join(
        f"{n}={r.status.value}"
        for n, r in sorted(result.agent_results.items()))
    main_drivers = _driver_labels(det["top_drivers"])

    print("=" * 72)
    print("MountainGuardian G03C – Risk Watch end-to-end smoke")
    print("=" * 72)
    print(f"Region: {region_name} ({result.region_id})")
    print(f"Run: {result.run_id}  [{result.scan_mode}]  "
          f"status {result.status}")
    print(f"Mode: weather={'LIVE Open-Meteo' if live_weather else 'offline fixture'}"
          f"  ai={'LIVE DeepSeek' if use_ai else 'deterministic fallback'}")
    print("-" * 72)
    if result.risk_index is None:
        print("Risk Index: UNAVAILABLE (required weather data missing — "
              "no fabricated risk)")
    else:
        print(f"Risk Index: {disp['C']} {result.risk_level}   "
              f"(C = 0.70 x B + 0.30 x D; NOT a probability)")
        print(f"7-Day Outlook: {disp['O7']} {result.outlook_7d_level}   "
              f"direction {det['risk_direction']}")
        print(f"B={disp['B']}  R={disp['R']}  F={disp['F']}  D={disp['D']}")
        print("Main drivers:")
        for m in main_drivers:
            print(f"  - {m}")
    print("-" * 72)
    print(f"Agents: {agents_done} completed  ({agent_states or 'not invoked'})")
    synth = result.synthesis_status
    print(f"Synthesizer: {synth}"
          + ("  [AI Analysis: Fallback Mode]"
             if result.synthesis is not None
             and result.synthesis.fallback_used else ""))
    print(f"Critic: {result.critic_status}")
    if result.critic is not None and result.critic.issues:
        for issue in result.critic.issues[:6]:
            print(f"  issue [{issue.check_id}/{issue.severity}] "
                  f"{issue.message[:100]}")
    print("-" * 72)
    prov = result.provenance["provider"]
    print(f"DeepSeek generation calls: {prov['generation_calls']} "
          f"(successful {prov.get('successful_calls', 0)}, "
          f"total latency {prov.get('total_latency_ms', 0)} ms)")
    print(f"Snapshots: data={result.data_snapshot_id}")
    print(f"           result={result.result_snapshot_id}  (db {db_path})")
    trend = result.historical_trend
    if trend is not None:
        print(f"Trend: {trend.status} ({len(trend.entries)} real "
              f"valid snapshots)")
    if result.limitations:
        print(f"Limitations ({len(result.limitations)}):")
        for lim in result.limitations[:8]:
            print(f"  - {str(lim)[:160]}")
    return 0 if result.status != "FAILED" else 2


if __name__ == "__main__":
    sys.exit(main())
