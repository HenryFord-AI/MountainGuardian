"""
MountainGuardian G03A – Risk Watch data foundation.

Independent Risk Watch Source of Truth (data/regions/<region_id>/region.json),
Open-Meteo weather collection, 1991-2020 climatology reference and immutable
SQLite snapshot persistence.

Hard boundaries of this package (frozen design, docs 04/06/07):
  * no Historical Replay / post-event data path (the Case Pack is never read);
  * no B / R / F / D / C / O7 computation and no risk bands (G03B);
  * no agent / LLM workflow (G03C);
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
