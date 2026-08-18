"""The decomposition engine, as a seam.

The reference see-through pipeline is diffusion over PyTorch, and its weights live on the
network volume rather than in this repository or its image. So this module holds the seam and
the engine that is honestly absent; `ReferenceEngine` is where the pipeline is loaded when the
weights are there.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Result:
    layers: int
    ms: int
    sidecar: str


class EngineAbsent(Exception):
    """Raised at open, naming the directory that was looked in.

    Not a stub that returns a plausible layer set. This pipeline is judged by compositing its
    layers and looking at them, so a fabricated result is not caught by checking that a result
    arrived, and a missing model must stay distinguishable from a bad one.
    """


class AbsentEngine:
    """What a worker with no weights on the volume gets."""

    def open(self, weights_dir: str) -> None:
        raise EngineAbsent(
            f"no see-through weights were read from {weights_dir}; "
            "the network volume holds them and nothing downloaded them into this worker"
        )

    def decompose(self, req, out_dir: str) -> Result:
        raise EngineAbsent("no see-through engine is loaded")

    def close(self) -> None:
        pass


class ReferenceEngine:
    """The reference pipeline, loaded from the network volume.

    Imports are inside `open` on purpose: torch and diffusers cost seconds to import and a
    worker that cannot find its weights should fail with the path rather than after paying
    that. It is also what lets every test in `proof/` run on a machine with neither.
    """

    def __init__(self) -> None:
        self.pipe = None

    def open(self, weights_dir: str) -> None:
        root = Path(weights_dir)
        if not root.is_dir():
            raise EngineAbsent(f"no see-through weights at {root}")
        # The load itself belongs to whichever revision of the pipeline is on the volume, and
        # this repository does not pin it: the volume is the cache and its contents are what
        # the A/B is run against. What is fixed here is where it is looked for.
        raise EngineAbsent(
            f"{root} exists, but this build has no reference pipeline wired to it yet"
        )

    def decompose(self, req, out_dir: str) -> Result:
        # The timing is taken around the engine's own work and reported by the program that
        # did it. A duration inferred anywhere else has been wrong here before, confidently
        # and in the direction of a defect that did not exist.
        start = time.monotonic()
        raise EngineAbsent("no reference pipeline")
        elapsed_ms = int((time.monotonic() - start) * 1000)  # noqa: F841 - kept with the shape

    def close(self) -> None:
        self.pipe = None


def engine_from_env(kind: str):
    return ReferenceEngine() if kind == "reference" else AbsentEngine()
