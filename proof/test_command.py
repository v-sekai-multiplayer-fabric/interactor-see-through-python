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
sys.path.insert(0, str(ROOT / "proof"))
sys.path.insert(0, str(ROOT / "third_party/harness/python"))

from dataclasses import dataclass  # noqa: E402

from etf_read import Atom, loads  # noqa: E402
from seethrough import command  # noqa: E402
from seethrough.engine import Result  # noqa: E402

FAILURES = []


def check(ok, what):
    print(f"{'ok  ' if ok else 'FAIL'} {what}")
    if not ok:
        FAILURES.append(what)


def refuses(line, reason=None, **detail):
    """A refusal is checked by its reason atom and its numbers, never by its wording.

    That is the same rule the interactor now follows: a caller selects a branch on the atom,
    so a test that matched the sentence would pass for a reply no caller could act on.
    """
    try:
        command.parse(line)
        return False
    except command.Refused as why:
        if reason is not None and why.reason != reason:
            return False
        return all(why.detail.get(k) == v for k, v in detail.items())


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

    check(refuses("decompose /in.png --res 512 --steps 30", "res_below_minimum", got=512, minimum=1280),
          "512px is refused as :res_below_minimum, carrying the number it saw")
    check(refuses("decompose /in.png --res 1280 --steps 8", "steps_below_minimum", got=8, minimum=30),
          "8 steps is refused as :steps_below_minimum, carrying the number it saw")
    check(refuses("decompose /in.png", "res_below_minimum"),
          "a command with no settings is refused, not defaulted")
    check(refuses("decompose --res 1280 --steps 30", "missing_input_path"),
          "a command with no input path is refused")
    check(refuses("decompose /in.png --res 1280 --steps", "missing_value", flag="steps"),
          "a flag with no value is :missing_value, naming the flag rather than the count")
    check(refuses("render /in.png --res 1280 --steps 30", "unknown_command", verb="render"),
          "another verb is refused, and the reason says which")

    rec = Recorder()
    state = State(engine=rec, out_root=command.OUT_DIR_DEFAULT, opened=True)

    term = loads(command.ask(state, "decompose /in.png --res 512 --steps 8"))
    check(term == (Atom("error"), (Atom("res_below_minimum"), {Atom("got"): 512, Atom("minimum"): 1280})),
          "a refusal is {:error, {:res_below_minimum, %{got: _, minimum: _}}}")
    check(rec.calls == 0, "a refused command never reaches the engine")

    term = loads(command.ask(state, "decompose /in/a.png --res 1280 --steps 30"))
    check(rec.calls == 1, "a production command reaches the engine")
    check(rec.seen_out == "/runpod-volume/see-through/out", "output defaults to the network volume")
    check(term[0] == Atom("ok") and len(term) == 2, "a success is {:ok, value}")
    value = term[1]
    check(value[Atom("sidecar")] == "res.psd.json", "the reply names the sidecar")
    check(value[Atom("layers")] == 7 and value[Atom("ms")] == 359000,
          "layers and ms are integers, not text")
    check(all(isinstance(k, Atom) for k in value), "every key is an atom, not a binary")

    closed = State(engine=rec, out_root=command.OUT_DIR_DEFAULT, opened=False)
    check(loads(command.ask(closed, "decompose /in/a.png --res 1280 --steps 30"))
          == (Atom("error"), Atom("no_engine")),
          "a worker with no weights answers {:error, :no_engine}")

    # A reason nobody listed cannot be sent. A caller decoding with [:safe] would refuse it, so
    # failing here names the bug where it was written instead of where it arrived.
    from seethrough import reply as reply_mod
    try:
        reply_mod.error("invented_reason")
        check(False, "an unlisted reason is refused")
    except ValueError:
        check(True, "an unlisted reason is refused before it reaches the wire")

    print("command: FAILED" if FAILURES else "command: all checks passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
