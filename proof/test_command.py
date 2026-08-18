"""The gate and the parse, with no GPU, no weights and no bus.

The same cases `interactor-see-through-cpp`'s `proof/decompose.c` runs, against different code.
Two implementations that agree because they share a parser would prove nothing; these agree
because they were written twice and checked against each other.

SPDX-License-Identifier: Apache-2.0
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "third_party/harness/python"))

from dataclasses import dataclass  # noqa: E402

from seethrough import cbor, command  # noqa: E402
from seethrough.engine import Result  # noqa: E402

FAILURES = []


def check(ok, what):
    print(f"{'ok  ' if ok else 'FAIL'} {what}")
    if not ok:
        FAILURES.append(what)


def refuses(line, needle=None):
    try:
        command.parse(line)
        return False
    except command.Refused as why:
        return needle is None or needle in str(why)


class Recorder:
    """Stands in for see-through. It never looks at a file."""

    def __init__(self):
        self.calls = 0
        self.seen_out = None

    def decompose(self, req, out_dir):
        self.calls += 1
        self.seen_out = out_dir
        return Result(layers=7, ms=359000, sidecar="res.psd.json")


@dataclass
class State:
    engine: object
    out_root: str
    opened: bool


def main():
    req = command.parse("decompose /in.png --res 1280 --steps 30")
    check(req.res == 1280 and req.steps == 30 and req.in_path == "/in.png",
          "the production settings parse")

    check(refuses("decompose /in.png --res 512 --steps 30", "512"), "512px is refused, by number")
    check(refuses("decompose /in.png --res 1280 --steps 8", "8"), "8 steps is refused, by number")
    check(refuses("decompose /in.png"), "a command with no settings is refused, not defaulted")
    check(refuses("decompose --res 1280 --steps 30"), "a command with no input path is refused")
    check(refuses("decompose /in.png --res 1280 --steps", "needs a value"),
          "a flag with no value is refused as a missing argument")
    check(refuses("render /in.png --res 1280 --steps 30"), "another verb is refused")

    rec = Recorder()
    state = State(engine=rec, out_root=command.OUT_DIR_DEFAULT, opened=True)

    reply = command.ask(state, "decompose /in.png --res 512 --steps 8")
    check(reply.startswith(cbor.mapping({"error": ""})[:2]), "a refusal is a CBOR error reply")
    check(rec.calls == 0, "a refused command never reaches the engine")

    reply = command.ask(state, "decompose /in/a.png --res 1280 --steps 30")
    check(rec.calls == 1, "a production command reaches the engine")
    check(rec.seen_out == "/runpod-volume/see-through/out", "output defaults to the network volume")
    check(b"res.psd.json" in reply, "the reply names the sidecar")
    check(b"sidecar" in reply and b"layers" in reply, "the reply carries the keys a caller decodes")

    closed = State(engine=rec, out_root=command.OUT_DIR_DEFAULT, opened=False)
    check(b"error" in command.ask(closed, "decompose /in/a.png --res 1280 --steps 30"),
          "a worker with no weights still answers its job")

    print("command: FAILED" if FAILURES else "command: all checks passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
