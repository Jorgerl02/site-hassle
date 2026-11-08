"""Single launcher for Blender: ``BLENDER_BIN --background --python <script> -- <args>``.

Never ``import bpy`` in the main process; every Blender job goes through here.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from harness.core.config import Settings


class BlenderNotAvailable(RuntimeError):
    """``BLENDER_BIN`` is unset or does not point to an existing file."""


@dataclass(frozen=True)
class BlenderRun:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str
    seconds: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_blender_script(
    script: Path,
    args: list[str],
    timeout: int = 600,
    blender_bin: Path | None = None,
) -> BlenderRun:
    """Run ``script`` inside headless Blender and capture its output.

    ``blender_bin`` defaults to ``Settings.load().blender_bin``. Raises ``BlenderNotAvailable``
    if there is no binary and ``subprocess.TimeoutExpired`` if ``timeout`` (s) is exceeded.
    A non-zero exit code is returned in ``BlenderRun.returncode``, not raised.
    """
    binary = blender_bin if blender_bin is not None else Settings.load().blender_bin
    if binary is None:
        raise BlenderNotAvailable("BLENDER_BIN no está definido (.env o entorno)")
    if not Path(binary).is_file():
        raise BlenderNotAvailable(f"BLENDER_BIN no existe: {binary}")

    cmd = [str(binary), "--background", "--python", str(script), "--", *map(str, args)]
    start = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    return BlenderRun(
        cmd=cmd,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        seconds=time.monotonic() - start,
    )
