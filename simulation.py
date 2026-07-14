"""
iOS location simulation engine.

Connects to an iOS device over the QUIC tunnel (via
:mod:`pymobiledevice3`), sets up the DVT secure-socket proxy, and
streams simulated GPS positions at a fixed cadence.
"""

import asyncio
import logging
import random
import time
from typing import List, Dict, Optional

from pymobiledevice3.remote.remote_service_discovery import \
    RemoteServiceDiscoveryService
from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import \
    DvtSecureSocketProxyService
from pymobiledevice3.services.dvt.instruments.location_simulation import \
    LocationSimulation

from route import interpolate_route, randomize_route

logger = logging.getLogger(__name__)


class LocationSimulator:
    """Manages the iOS DVT connection and streams simulated GPS positions.

    Typical usage::

        async with LocationSimulator(host, port) as sim:
            await sim.run_forever(waypoints, speed)
    """

    def __init__(self, address: str, port: int):
        self._address = address
        self._port = port
        self._rsd: Optional[RemoteServiceDiscoveryService] = None
        self._dvt: Optional[DvtSecureSocketProxyService] = None

    # -- connection management -----------------------------------------------

    async def connect(self) -> None:
        """Establish RSD and DVT connections to the device."""
        logger.info("Connecting to device at %s:%d …",
                    self._address, self._port)

        self._rsd = RemoteServiceDiscoveryService((self._address, self._port))
        await asyncio.sleep(2)  # allow tunnel to stabilise
        await self._rsd.connect()

        self._dvt = DvtSecureSocketProxyService(self._rsd)
        self._dvt.perform_handshake()

        # Clear any previous location simulation so we start fresh.
        try:
            LocationSimulation(self._dvt).clear()
            logger.debug("Cleared previous location simulation state.")
        except Exception:
            logger.debug("Could not clear previous location simulation "
                         "(may not be running).", exc_info=True)

        logger.info("DVT handshake complete — ready to simulate location.")

    async def disconnect(self) -> None:
        """Tear down connections gracefully."""
        if self._rsd is not None:
            try:
                await self._rsd.close()
            except Exception:
                logger.debug("Error closing RSD", exc_info=True)
        self._rsd = None
        self._dvt = None
        logger.info("Disconnected from device.")

    async def __aenter__(self) -> "LocationSimulator":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.disconnect()

    # -- location streaming --------------------------------------------------

    def _set_location(self, lng: float, lat: float) -> bool:
        """Send a single GPS position to the device (synchronous call).

        Returns:
            True if the call succeeded without raising, False otherwise.
        """
        if self._dvt is None:
            raise RuntimeError("Not connected — call connect() first.")
        try:
            LocationSimulation(self._dvt).set(lat, lng)
            return True
        except Exception:
            logger.debug("LocationSimulation.set() failed", exc_info=True)
            return False

    async def run_lap(self,
                      waypoints: List[Dict[str, float]],
                      dt: float = 0.2) -> None:
        """Stream *waypoints* to the device at *dt*-second intervals.

        Blocks until the last waypoint has been sent.  Each update is
        timed so the simulated movement appears to travel at the speed
        used when the waypoints were generated.

        Args:
            waypoints: List of ``{"lat", "lng"}`` dicts (WGS-84).
            dt: Time in seconds between consecutive position updates.
        """
        total = len(waypoints)
        failures = 0
        report_every = max(1, total // 10)  # progress every 10%

        clock = time.monotonic()
        for idx, pt in enumerate(waypoints):
            ok = self._set_location(pt["lng"], pt["lat"])
            if not ok:
                failures += 1

            # Progress indicator — show every 10% so the user sees movement.
            if idx > 0 and idx % report_every == 0:
                pct = idx * 100 // total
                print(f"  ... {pct}%  ({idx}/{total})", flush=True)

            elapsed = time.monotonic() - clock
            if elapsed < dt:
                await asyncio.sleep(dt - elapsed)
            clock = time.monotonic()

        if failures:
            logger.warning("%d / %d location updates failed this lap.",
                           failures, total)
            if failures == total:
                print("⚠  ALL location updates failed this lap! "
                      "Check that Developer Mode is enabled on the device "
                      "and the Developer Disk Image is mounted.",
                      flush=True)

    # -- high-level runner ---------------------------------------------------

    async def run_forever(self,
                          waypoints: List[Dict[str, float]],
                          speed: float,
                          speed_variation: float = 15.0,
                          dt: float = 0.2) -> None:
        """Run the simulation in an infinite loop with varying speed.

        Each lap uses a slightly different speed (randomised around
        *speed* by ±*speed_variation* %) to keep the movement looking
        natural.  Press :kbd:`Ctrl+C` to exit.

        Args:
            waypoints: Base route waypoints (sparse, WGS-84).
            speed: Target speed in m/s.
            speed_variation: Max ± deviation applied to *speed* each lap.
            dt: Position-update interval in seconds.
        """
        lap = 0
        try:
            while True:
                # Vary speed per lap:  v_eff = 1 / (1/v + Δ)
                # where Δ ∈ [-speed_variation, +speed_variation].
                delta = (2.0 * random.random() - 1.0) * speed_variation
                effective_speed = 1000.0 / (1000.0 / speed - delta)

                # Generate dense + perturbed waypoints for this lap.
                dense = interpolate_route(waypoints, effective_speed, dt)
                perturbed = randomize_route(dense)

                lap += 1
                eta_s = len(perturbed) * dt
                print(f"Lap {lap} — {len(perturbed)} points, "
                      f"~{eta_s:.0f}s at {effective_speed:.1f} m/s",
                      flush=True)

                try:
                    await self.run_lap(perturbed, dt)
                except Exception as exc:
                    logger.error("Lap %d aborted: %s", lap, exc,
                                 exc_info=True)
                    print(f"Lap {lap} error — {exc}. Retrying next lap …")
                    await asyncio.sleep(1)
                    continue

                logger.info("Lap %d finished (speed=%.2f m/s).",
                            lap, effective_speed)
                print(f"Lap {lap} finished — speed {effective_speed:.1f} m/s")

        except asyncio.CancelledError:
            logger.info("Simulation cancelled.")
        finally:
            print("\nSimulation stopped.")
