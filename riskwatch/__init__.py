"""
MountainGuardian – Risk Watch package.

G03A data foundation (this module's exports): independent Risk Watch Source
of Truth (data/regions/<region_id>/region.json), Open-Meteo weather
collection, 1991-2020 climatology reference and immutable SQLite snapshot
persistence.

G03B deterministic engine: the risk-index computation (B/R/F/D/C/O7, bands,
direction, trend, What Changed, Top Risk Drivers) lives in the
``riskwatch.engine`` subpackage and is deliberately NOT imported here, so
the data-foundation modules below stay free of risk formulas.

Hard boundaries of the G03A data-foundation modules (frozen design, docs
04/06/07; enforced by tests/test_g03a_isolation.py):
  * no Historical Replay / post-event data path (the Case Pack is never read);
  * no risk-index computation and no risk bands in region.py, weather.py,
    cache.py, climatology.py, snapshot_store.py or this module;
  * no agent / LLM workflow anywhere in this package (G03C);
  * no UI, no satellite/STAC discovery.
"""

from riskwatch.region import (
    MonitoringPoint,
    RegionConfig,
    RegionConfigError,
    REGIONS_DIR,
    load_region,
)
from riskwatch.weather import (
    PointWeather,
    PointWeatherFailure,
    RegionWeatherResult,
    WeatherCollectionError,
    WeatherCollector,
    WeatherConfigError,
    WeatherTimeoutError,
)
from riskwatch.cache import WeatherRawCache
from riskwatch.climatology import (
    CLIMATOLOGY_BASELINE_END,
    CLIMATOLOGY_BASELINE_START,
    ClimatologyReference,
    ClimatologyStore,
    HistoricalWeatherClient,
    build_climatology,
    percentile_of,
)
from riskwatch.snapshot_store import (
    SnapshotExistsError,
    SnapshotStore,
    default_db_path,
)

__all__ = [
    "MonitoringPoint",
    "RegionConfig",
    "RegionConfigError",
    "REGIONS_DIR",
    "load_region",
    "PointWeather",
    "PointWeatherFailure",
    "RegionWeatherResult",
    "WeatherCollectionError",
    "WeatherCollector",
    "WeatherConfigError",
    "WeatherTimeoutError",
    "WeatherRawCache",
    "CLIMATOLOGY_BASELINE_END",
    "CLIMATOLOGY_BASELINE_START",
    "ClimatologyReference",
    "ClimatologyStore",
    "HistoricalWeatherClient",
    "build_climatology",
    "percentile_of",
    "SnapshotExistsError",
    "SnapshotStore",
    "default_db_path",
]
