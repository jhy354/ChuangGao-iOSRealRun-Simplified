"""
QUIC tunnel lifecycle management.

Starts ``pymobiledevice3 lockdown start-tunnel`` as an async subprocess,
parses the RSD (Remote Service Discovery) endpoint from its output,
and provides clean startup / shutdown semantics.
"""

import asyncio
import logging
import re
import sys
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Matches the line:  --rsd <address> <port>
_RSD_PATTERN = re.compile(r"--rsd\s+(\S+)\s+(\d+)")


class TunnelError(RuntimeError):
    """Raised when the tunnel fails to start."""


async def start_tunnel(
    timeout: float = 30.0,
) -> Tuple[asyncio.subprocess.Process, str, int]:
    """Start a QUIC tunnel to the connected iOS device.

    Spawns ``pymobiledevice3 lockdown start-tunnel`` and blocks until
    the RSD endpoint is advertised on stdout (or *timeout* seconds
    elapse).

    Args:
        timeout: Maximum seconds to wait for the tunnel to come up.

    Returns:
        ``(process, address, port)`` tuple.  *process* is the running
        :class:`~asyncio.subprocess.Process` that hosts the tunnel.

    Raises:
        TunnelError: If the tunnel cannot be established within the
            timeout window, or if no device is connected.
    """
    cmd = [sys.executable, "-m", "pymobiledevice3", "lockdown", "start-tunnel"]

    # On Windows, hide the console window that pops up for the subprocess.
    creationflags = 0x08000000 if sys.platform == "win32" else 0

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        creationflags=creationflags,
    )

    try:
        async with asyncio.timeout(timeout):
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break  # EOF — process exited prematurely

                text = line.decode(errors="replace").strip()
                if text:
                    logger.debug("[tunnel] %s", text)

                match = _RSD_PATTERN.search(text)
                if match:
                    address = match.group(1)
                    port = int(match.group(2))
                    logger.info("RSD endpoint: %s:%d", address, port)
                    return proc, address, port

    except asyncio.TimeoutError:
        await _kill_proc(proc)
        raise TunnelError(
            f"Tunnel startup timed out after {timeout}s. "
            "Is a device connected and unlocked?"
        )

    # EOF without a match — process died before advertising RSD.
    await _kill_proc(proc)
    raise TunnelError(
        "Tunnel process exited without advertising an RSD endpoint. "
        "Make sure a device is connected and unlocked, and that the "
        "Developer Disk Image is mounted:\n"
        "  pymobiledevice3 mounter auto-mount"
    )


async def stop_tunnel(proc: Optional[asyncio.subprocess.Process]) -> None:
    """Gracefully terminate a tunnel subprocess.

    Sends :data:`~signal.SIGTERM`, waits up to 5 s, then escalates to
    :data:`~signal.SIGKILL` if necessary.
    """
    if proc is None:
        return
    logger.info("Stopping tunnel …")
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except asyncio.TimeoutError:
        logger.warning("Tunnel did not exit gracefully — force-killing.")
        proc.kill()
        await proc.wait()
    logger.info("Tunnel stopped.")


async def _kill_proc(proc: asyncio.subprocess.Process) -> None:
    """Best-effort kill of a subprocess."""
    try:
        proc.kill()
        await proc.wait()
    except Exception:
        pass
