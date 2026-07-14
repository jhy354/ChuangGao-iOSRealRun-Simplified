#!/usr/bin/env python3
"""
iOSRealRun — Simulate GPS movement on a developer-mode iOS device.

Connects to an iOS device (≥ 17) via a QUIC tunnel, then streams
simulated WGS-84 GPS positions along a user-provided route in an
infinite loop.  Route coordinates are expected in BD-09 (Baidu Maps)
format; the tool converts them to WGS-84 automatically.

Usage
-----

1. Make sure the Developer Disk Image is mounted::

       pymobiledevice3 mounter auto-mount

2. Run this script **as Administrator / root** (required for tunnel)::

       python main.py

   Or with a custom config file::

       python main.py -c my_config.yaml

3. Press :kbd:`Ctrl+C` to stop — the tunnel is cleaned up automatically.
"""

import argparse
import asyncio
import logging
import sys
from typing import Optional

import coloredlogs

from config import Config, load_config
from route import load_route
from tunnel import start_tunnel, stop_tunnel, TunnelError
from simulation import LocationSimulator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Simulate GPS movement on a connected iOS device.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python main.py                        # use defaults / config.yaml
  python main.py -s 5.0                 # run at 5 m/s (~ 11 mph)
  python main.py -r my_route.txt        # custom route file
  python main.py --manual               # manual tunnel (enter host:port)
        """,
    )
    p.add_argument("-c", "--config", default="config.yaml",
                   help="Path to YAML config file (default: config.yaml).")
    p.add_argument("-s", "--speed", type=float,
                   help="Speed in m/s (default: 3.3, ~12 min/mile).")
    p.add_argument("-r", "--route", help="Path to route file.")
    p.add_argument("--dt", type=float, default=0.2,
                   help="Location update interval in seconds (default: 0.2).")
    p.add_argument("--deviation", type=float, default=0.000025,
                   help="Randomisation deviation (default: 0.000025).")
    p.add_argument("--debug", action="store_true",
                   help="Enable debug logging.")
    p.add_argument("--manual", action="store_true",
                   help="Use manual tunnel mode (enter host:port).")
    return p


# ---------------------------------------------------------------------------
#  Runners
# ---------------------------------------------------------------------------

async def run_manual(config: Config) -> None:
    """Manual-tunnel path: user supplies host & port interactively."""
    print("Manual tunnel mode.")
    print("Start the tunnel in another terminal with:")
    print("  python -m pymobiledevice3 lockdown start-tunnel")
    print()

    host = input("HOST: ").strip()
    port = int(input("PORT: ").strip())

    waypoints = load_route(config.route_file)
    print(f"Loaded {len(waypoints)} route points from {config.route_file}.")

    async with LocationSimulator(host, port) as sim:
        await sim.run_forever(waypoints, config.speed,
                              config.speed_variation, config.dt)


async def run_auto(config: Config) -> None:
    """Automatic-tunnel path: start tunnel as async subprocess."""
    print("Starting QUIC tunnel …")
    proc, address, port = await start_tunnel(timeout=config.tunnel_timeout)
    logger.info("Tunnel up — %s:%d", address, port)

    waypoints = load_route(config.route_file)
    print(f"Loaded {len(waypoints)} route points from {config.route_file}.")
    print(f"Speed: ~{config.speed:.1f} m/s  |  update interval: {config.dt}s")
    print("Simulating — press Ctrl+C to stop.\n")

    sim = LocationSimulator(address, port)

    try:
        await sim.connect()
        await sim.run_forever(waypoints, config.speed,
                              config.speed_variation, config.dt)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received — shutting down.")
    finally:
        await sim.disconnect()
        await stop_tunnel(proc)
        print("Bye.")


# ---------------------------------------------------------------------------
#  Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = build_parser().parse_args()

    # -- logging ----------------------------------------------------------
    level = logging.DEBUG if args.debug else logging.INFO
    coloredlogs.install(level=level,
                        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Silence noisy third-party loggers unless debugging.
    if not args.debug:
        for noisy in ("wintun", "quic", "asyncio", "zeroconf",
                      "parso.cache", "parso.cache.pickle",
                      "parso.python.diff", "humanfriendly.prompts",
                      "blib2to3.pgen2.driver", "urllib3.connectionpool"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    # -- config -----------------------------------------------------------
    config = load_config(args.config)

    # CLI overrides
    if args.speed is not None:
        config.speed = args.speed
    if args.route is not None:
        config.route_file = args.route
    if args.dt is not None:
        config.dt = args.dt
    if args.deviation is not None:
        config.route_deviation = args.deviation
    if args.debug:
        config.debug = True

    logger.debug("Config: speed=%.1f m/s  route=%s  dt=%.2fs",
                 config.speed, config.route_file, config.dt)

    # -- run --------------------------------------------------------------
    try:
        if args.manual:
            asyncio.run(run_manual(config))
        else:
            asyncio.run(run_auto(config))
    except TunnelError as exc:
        logger.error(str(exc))
        logger.info(
            "Tip: make sure the Developer Disk Image is mounted first:\n"
            "  pymobiledevice3 mounter auto-mount"
        )
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as exc:
        logger.error("Fatal error: %s", exc, exc_info=args.debug)
        sys.exit(1)


if __name__ == "__main__":
    main()
