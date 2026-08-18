"""The decomposition engine, as a seam.

The reference see-through pipeline is diffusion over PyTorch, and its weights live on the
network volume rather than in this repository or its image. So this module holds the seam and
the engine that is honestly absent; `ReferenceEngine` is where the pipeline is loaded when the
weights are there.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import os
import subprocess
import sys
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
    """Upstream's pipeline, run as it is documented to be run.

    `shitagaki-lab/see-through` (Apache-2.0) is the paper's own implementation, and this calls
    its `inference_psd.py` rather than reimplementing the stratification. That is deliberate:
    the working system came first and this wraps it, so a difference between what an endpoint
    produces and what upstream produces is this repository's fault and nowhere else's.

    Run directly on an RTX 4090 it takes about 171 s at 1280 and writes a layered PSD beside a
    depth PSD. Those are the numbers `service-see-through` measures against.

    A subprocess rather than an import, for the reason the two-process split exists at all: the
    pipeline loads several gigabytes and can die on a bad input, and a worker whose HTTP loop
    shares that address space dies with it.
    """

    def __init__(self) -> None:
        self.root = None
        self.hf_home = None

    def open(self, weights_dir: str) -> None:
        # `weights_dir` is the HuggingFace cache on the network volume. It is not downloaded
        # here: a worker that fetched 14 GB on its first job would pay for it on every cold
        # start, which is what the volume exists to stop.
        cache = Path(weights_dir)
        if not cache.is_dir():
            raise EngineAbsent(
                f"no see-through weight cache at {cache}; the network volume holds it and "
                "nothing downloads it into a worker"
            )
        src = Path(os.environ.get("ST_UPSTREAM") or "/opt/see-through")
        if not (src / "inference/scripts/inference_psd.py").is_file():
            raise EngineAbsent(f"no see-through checkout at {src}")
        self.root, self.hf_home = src, cache

    def decompose(self, req, out_dir: str) -> Result:
        if self.root is None:
            raise EngineAbsent("open() was not called or did not succeed")

        env = dict(os.environ, HF_HOME=str(self.hf_home))
        cmd = [
            sys.executable, "-u", "inference/scripts/inference_psd.py",
            "--srcp", req.in_path, "--save_to_psd",
        ]

        # The timing is taken around the work by the process that waits for it, and it is the
        # only clock in the reply. A duration inferred from anywhere else has been wrong here
        # before, confidently, in the direction of a defect that did not exist.
        start = time.monotonic()
        done = subprocess.run(cmd, cwd=self.root, env=env, capture_output=True, text=True)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if done.returncode != 0:
            tail = (done.stderr or done.stdout or "").strip().splitlines()[-3:]
            raise EngineAbsent(f"inference_psd.py exited {done.returncode}: {' / '.join(tail)}")

        produced = sorted((self.root / "workspace/layerdiff_output").glob("*.psd"))
        if not produced:
            # Exiting zero and writing nothing is the failure mode a return code cannot catch,
            # and the one that would let an empty result be measured as a fast one.
            raise EngineAbsent("inference_psd.py exited 0 and wrote no PSD")

        psd = produced[0]
        layers = len(list((psd.parent / psd.stem).glob("*.png"))) if (psd.parent / psd.stem).is_dir() else 0
        return Result(layers=layers, ms=elapsed_ms, sidecar=psd.name)

    def close(self) -> None:
        self.root = None


def engine_from_env(kind: str):
    return ReferenceEngine() if kind == "reference" else AbsentEngine()
