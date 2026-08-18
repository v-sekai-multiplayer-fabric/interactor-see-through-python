"""The command this interactor answers, and the one rule it refuses to bend.

The same line the C++ interactor answers, parsed again by different code:

    decompose <in-path> --res <px> --steps <n> [--out <dir>]

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from dataclasses import dataclass

from . import cbor

# Production settings. A run below either bound is refused rather than served: low step counts
# make degenerate layers -- undifferentiated depth medians, soft detail -- that look plausible
# in a viewer and say nothing about quality, and a 512px/8-step artefact that vanished at
# 1280/30 is what the see-through project's MADR 0009 was written about.
#
# These two numbers are also the A/B's control. If this pair and the C++ pair ever disagree,
# the two implementations are answering different questions and every timing comparison
# between them is void, so `proof/test_gate_agrees.py` reads them out of the C++ header and
# fails when they differ.
MIN_RES = 1280
MIN_STEPS = 30

# RunPod mounts the network volume here in every worker. Weights are cached on it rather than
# baked into the image: an image carrying them re-downloads gigabytes into every cold worker,
# and the volume is written once and read by all of them.
WEIGHTS_DIR_DEFAULT = "/runpod-volume/see-through/hf"
OUT_DIR_DEFAULT = "/runpod-volume/see-through/out"


class Refused(Exception):
    """The command will not be run, and the message says which number was refused."""


@dataclass
class Request:
    in_path: str
    res: int
    steps: int
    out_dir: str | None = None


def parse(line: str) -> Request:
    tokens = line.split()
    if not tokens or tokens[0] != "decompose":
        raise Refused("unknown command; this interactor answers `decompose`")

    in_path = None
    res = 0
    steps = 0
    out_dir = None

    rest = tokens[1:]
    i = 0
    while i < len(rest):
        tok = rest[i]
        if tok.startswith("--"):
            flag = tok[2:]
            # The value is required. `--steps` with nothing after it used to read as 0, which
            # the gate refuses -- with a message about the step count rather than about the
            # argument that was left off, which is the harder one to act on.
            if i + 1 >= len(rest) or rest[i + 1].startswith("--"):
                raise Refused(f"--{flag} needs a value")
            val = rest[i + 1]
            i += 2
            if flag == "res":
                res = _int(val, "--res")
            elif flag == "steps":
                steps = _int(val, "--steps")
            elif flag == "out":
                out_dir = val
            else:
                raise Refused(f"unknown flag --{flag}")
            continue
        if in_path is not None:
            raise Refused("decompose takes one input path")
        in_path = tok
        i += 1

    if in_path is None:
        raise Refused("decompose needs an input path")
    if res < MIN_RES:
        raise Refused(
            f"--res {res} is below the production setting {MIN_RES}; "
            "a smaller run is not evidence"
        )
    if steps < MIN_STEPS:
        raise Refused(
            f"--steps {steps} is below the production setting {MIN_STEPS}; "
            "a smaller run is not evidence"
        )
    return Request(in_path=in_path, res=res, steps=steps, out_dir=out_dir)


def _int(val: str, flag: str) -> int:
    try:
        return int(val)
    except ValueError:
        raise Refused(f"{flag} takes a number, not {val!r}") from None


def ask(state, command: str) -> bytes:
    """`weft_interactor_t::ask`, in Python. One command in, reply bytes out.

    Never raises: a worker's job result is the only place some of these failures are ever
    seen, so each one is answered rather than thrown.
    """
    try:
        req = parse(command)
    except Refused as why:
        return cbor.error(str(why))

    out_dir = req.out_dir or state.out_root
    if not state.opened:
        return cbor.error("no engine: the weights were never loaded")

    try:
        result = state.engine.decompose(req, out_dir)
    except Exception as why:  # noqa: BLE001 - the job result is the only log some runs leave
        return cbor.error(f"decompose failed: {why}")

    # Where the layers are, how many, and how long the engine says it took. Not the pixels:
    # the bus carries one value of at most 128 KiB and a layer set is larger than that, so the
    # artefacts stay on the volume and this says where they are.
    return cbor.mapping(
        {
            "in": req.in_path,
            "out": out_dir,
            "sidecar": result.sidecar,
            "layers": result.layers,
            "ms": result.ms,
        }
    )
