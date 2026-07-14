"""
Application configuration.

Reads from config.yaml if present, otherwise uses sensible defaults.
Configuration can also be overridden via command-line arguments.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class Config:
    """Runtime configuration for iOSRealRun."""

    #: Walking/running speed in meters per second (default ~12 min/mile)
    speed: float = 3.3

    #: Path to the route file containing BD-09 coordinate pairs
    route_file: str = "route.txt"

    #: Time step between location updates in seconds
    dt: float = 0.2

    #: Maximum random speed variation in m/s (±var applied each lap)
    speed_variation: float = 15.0

    #: Perpendicular deviation for route randomization (degrees)
    route_deviation: float = 0.000025

    #: Number of segments for route randomization
    route_segments: int = 5

    #: Tunnel startup timeout in seconds
    tunnel_timeout: float = 30.0

    #: Enable debug logging
    debug: bool = False


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from a YAML file, falling back to defaults.

    The config file is optional — if it doesn't exist, a default
    configuration is returned.  Supported keys in YAML map to
    :class:`Config` fields.

    Args:
        config_path: Path to a YAML configuration file.

    Returns:
        A populated Config instance.
    """
    config = Config()

    # Apply environment variable overrides
    if os.environ.get("DEBUG"):
        config.debug = True

    if not os.path.exists(config_path):
        return config

    with open(config_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    # Map flat YAML keys to dataclass fields
    _field_map = {
        "v": "speed",
        "speed": "speed",
        "routeConfig": "route_file",
        "route_file": "route_file",
        "dt": "dt",
        "speed_variation": "speed_variation",
        "route_deviation": "route_deviation",
        "route_segments": "route_segments",
        "tunnel_timeout": "tunnel_timeout",
        "debug": "debug",
    }

    for yaml_key, attr_name in _field_map.items():
        if yaml_key in data:
            setattr(config, attr_name, data[yaml_key])

    return config
