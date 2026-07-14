"""
Route loading, interpolation, and randomization.

Route files contain a sequence of BD-09 coordinate objects::

    {"lng":"117.17...","lat":"39.11..."},{"lng":"117.17...","lat":"39.11..."},...

This module parses those files, converts coordinates to WGS-84,
interpolates waypoints at a fixed time step, and adds natural-looking
random perturbations so the simulated movement does not appear robotic.
"""

import json
import math
import random
import time
from typing import List, Dict, Tuple

from geo_utils import bd09_to_wgs84, haversine_distance


# ---- route file I/O -------------------------------------------------------

def load_route(filepath: str) -> List[Dict[str, float]]:
    """Parse a route file and return a list of WGS-84 waypoints.

    The file format is a sequence of JSON objects separated by commas
    (but not wrapped in an array).  Each object has string ``"lng"``
    and ``"lat"`` keys in BD-09.

    Args:
        filepath: Path to the route file.

    Returns:
        List of dicts with ``lng`` and ``lat`` as **floats** in WGS-84.
    """
    with open(filepath, "r", encoding="utf-8") as fh:
        raw = fh.read().strip()

    # Wrap the comma-separated objects in an array so json.loads works.
    wrapped = f"[{raw}]"
    # Remove a trailing comma before the closing bracket if present.
    if wrapped.endswith(",]"):
        wrapped = wrapped[:-2] + "]"

    raw_points = json.loads(wrapped)
    converted: List[Dict[str, float]] = []
    for pt in raw_points:
        wgs_lng, wgs_lat = bd09_to_wgs84(float(pt["lng"]), float(pt["lat"]))
        converted.append({"lng": wgs_lng, "lat": wgs_lat})
    return converted


# ---- interpolation ---------------------------------------------------------

def interpolate_route(waypoints: List[Dict[str, float]],
                      speed: float,
                      dt: float = 0.2) -> List[Dict[str, float]]:
    """Create time-spaced waypoints along a route.

    Given a list of sparse route waypoints (a closed loop) and a
    constant travel speed, generate dense waypoints at *dt*-second
    intervals via linear interpolation along each segment.

    Args:
        waypoints: Route points with ``lat`` / ``lng`` keys.
        speed: Travel speed in **meters per second**.
        dt: Time step between consecutive output points in seconds.

    Returns:
        Dense list of ``{"lat", "lng"}`` dicts covering one full lap.
    """
    if len(waypoints) < 2:
        return list(waypoints)

    result: List[Dict[str, float]] = []
    n = len(waypoints)

    # Cumulative segment end-times (seconds).
    segment_times: List[float] = []

    # --- first segment (index 0 → 1) ---
    d0 = haversine_distance(waypoints[0]["lng"], waypoints[0]["lat"],
                            waypoints[1]["lng"], waypoints[1]["lat"])
    segment_times.append(d0 / speed)
    _fill_segment(result, waypoints[0], waypoints[1],
                  0.0, segment_times[0], dt)

    # --- remaining segments ---
    for i in range(1, n):
        a = waypoints[i]
        b = waypoints[(i + 1) % n]
        dist = haversine_distance(a["lng"], a["lat"], b["lng"], b["lat"])
        segment_times.append(dist / speed + segment_times[-1])
        _fill_segment(result, a, b, segment_times[i - 1],
                      segment_times[i], dt)

    return result


def _fill_segment(target: List[Dict[str, float]],
                  start: Dict[str, float],
                  end: Dict[str, float],
                  t_start: float,
                  t_end: float,
                  dt: float) -> None:
    """Append linearly-interpolated points between *start* and *end*.

    Points are generated at *dt* intervals between *t_start* and *t_end*.
    """
    segment_duration = t_end - t_start
    steps = max(1, int(segment_duration / dt))

    for step in range(steps):
        frac = step / steps
        target.append({
            "lat": start["lat"] + frac * (end["lat"] - start["lat"]),
            "lng": start["lng"] + frac * (end["lng"] - start["lng"]),
        })


# ---- random perturbation --------------------------------------------------

def randomize_route(waypoints: List[Dict[str, float]],
                    deviation: float = 0.000025,
                    segments: int = 5) -> List[Dict[str, float]]:
    """Add natural-looking random offsets to a route.

    The route is divided into *segments* contiguous blocks.  Each block
    receives a random perpendicular offset (scaled by *deviation*)
    weighted by a :math:`\\sin^2` envelope so that offsets are zero at
    block boundaries — producing smooth, continuous perturbations.

    The original waypoints are **not** modified; a new list is returned.

    Args:
        waypoints: Dense waypoint list from :func:`interpolate_route`.
        deviation: Maximum perpendicular offset in coordinate degrees.
        segments: How many blocks to divide the route into.

    Returns:
        New list of perturbed ``{"lat", "lng"}`` dicts.
    """
    n = len(waypoints)
    if n == 0:
        return []

    # Deep copy
    result = [pt.copy() for pt in waypoints]

    # Compute geometric centre for radial direction reference.
    center_lat = sum(p["lat"] for p in result) / n
    center_lng = sum(p["lng"] for p in result) / n

    # Seed with current time for variation across laps.
    random.seed(time.time())

    num_segments = random.choice((5, 6, 7, 8, 9)) if segments == 5 else segments

    for seg_idx in range(num_segments):
        i_start = int(seg_idx * n / num_segments)
        i_end = int((seg_idx + 1) * n / num_segments)

        # Random offset for this segment — scale & sign.
        offset = (2.0 * random.random() - 1.0) * deviation

        for j in range(i_start, i_end):
            # Radial direction from centre → point.
            dlat = result[j]["lat"] - center_lat
            dlng = result[j]["lng"] - center_lng
            dist = math.sqrt(dlat * dlat + dlng * dlng)
            if dist == 0.0:
                continue

            # Perpendicular unit vector.
            perp_lat = -dlng / dist
            perp_lng = dlat / dist

            # Sin² envelope: zero at boundaries, max at centre.
            weight = _smooth_envelope(i_start, i_end, j)

            result[j]["lat"] += perp_lat * offset * weight
            result[j]["lng"] += perp_lng * offset * weight

    return result


def _smooth_envelope(start: int, end: int, i: int) -> float:
    """Sin² weight that goes 0 → 1 → 0 over [*start*, *end*]."""
    span = end - start
    if span <= 0:
        return 0.0
    phase = (i - start) / span * math.pi
    return math.sin(phase) ** 2
