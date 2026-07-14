"""
Geographic coordinate utilities.

Provides:
- BD-09 (Baidu Maps) → WGS-84 (iOS / GPS) coordinate conversion
- Haversine geodesic distance calculation
"""

import math
from typing import Tuple

# --- Earth / coordinate-system constants ---
_PI = math.pi
_X_PI = _PI * 3000.0 / 180.0
_SEMI_MAJOR = 6378245.0  # a — semi-major axis (meters)
_ECC_SQ = 0.00669342162296594323  # ee — eccentricity squared
_EARTH_RADIUS = 6371000.0  # mean radius (meters)


# ---------------------------------------------------------------------------
#  BD-09 → WGS-84 conversion
# ---------------------------------------------------------------------------
# The chain is:  BD-09 → GCJ-02 → WGS-84
#
# BD-09 is Baidu's proprietary projection.  GCJ-02 (a.k.a. "Mars
# coordinates") is the Chinese national standard with an obfuscation
# offset.  WGS-84 is what GPS receivers and iOS report natively.
# ---------------------------------------------------------------------------


def _gcj_offset_lat(lng: float, lat: float) -> float:
    """Latitude component of the GCJ-02 obfuscation offset."""
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat
    ret += 0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * _PI) +
            20.0 * math.sin(2.0 * lng * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * _PI) +
            40.0 * math.sin(lat / 3.0 * _PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * _PI) +
            320.0 * math.sin(lat * _PI / 30.0)) * 2.0 / 3.0
    return ret


def _gcj_offset_lng(lng: float, lat: float) -> float:
    """Longitude component of the GCJ-02 obfuscation offset."""
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng
    ret += 0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * _PI) +
            20.0 * math.sin(2.0 * lng * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * _PI) +
            40.0 * math.sin(lng / 3.0 * _PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * _PI) +
            300.0 * math.sin(lng / 30.0 * _PI)) * 2.0 / 3.0
    return ret


def bd09_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """Convert a BD-09 coordinate pair to WGS-84.

    Args:
        lng: Longitude in BD-09.
        lat: Latitude in BD-09.

    Returns:
        ``(longitude, latitude)`` in WGS-84.
    """
    # --- BD-09 → GCJ-02 ---
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)

    gcj_lng = z * math.cos(theta)
    gcj_lat = z * math.sin(theta)

    # --- GCJ-02 → WGS-84 ---
    d_lat = _gcj_offset_lat(gcj_lng - 105.0, gcj_lat - 35.0)
    d_lng = _gcj_offset_lng(gcj_lng - 105.0, gcj_lat - 35.0)

    rad_lat = gcj_lat / 180.0 * _PI
    magic = 1.0 - _ECC_SQ * math.sin(rad_lat) ** 2
    sqrt_magic = math.sqrt(magic)

    d_lng_deg = (d_lng * 180.0) / (_SEMI_MAJOR / sqrt_magic *
                                   math.cos(rad_lat) * _PI)
    d_lat_deg = (d_lat * 180.0) / (_SEMI_MAJOR * (1.0 - _ECC_SQ) /
                                   (magic * sqrt_magic) * _PI)

    return (gcj_lng * 2.0 - (gcj_lng + d_lng_deg),
            gcj_lat * 2.0 - (gcj_lat + d_lat_deg))


# ---------------------------------------------------------------------------
#  Geodesic distance (haversine)
# ---------------------------------------------------------------------------

def haversine_distance(lng1: float, lat1: float,
                       lng2: float, lat2: float) -> float:
    """Return the great-circle distance **in meters** between two WGS-84
    points using the haversine formula.

    Accurate to ~0.5 % for most terrestrial distances.
    """
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlng / 2.0) ** 2)

    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return _EARTH_RADIUS * c
