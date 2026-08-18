"""Write one file per reply shape, for proof/elixir_compat.exs to read.

Two programs rather than one because the writer is Python and the reader must be Erlang. A
single program in either language could only check itself.

SPDX-License-Identifier: Apache-2.0
"""

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from seethrough import command  # noqa: E402
from seethrough.engine import Result  # noqa: E402


@dataclass
class State:
    engine: object
    out_root: str
    opened: bool


class Recorder:
    def decompose(self, req, out_dir):
        return Result(layers=7, ms=359000, sidecar="res.psd.json")


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/replies")
    out.mkdir(parents=True, exist_ok=True)
    live = State(engine=Recorder(), out_root=command.OUT_DIR_DEFAULT, opened=True)
    dead = State(engine=Recorder(), out_root=command.OUT_DIR_DEFAULT, opened=False)

    for name, state, line in [
        ("res.cbor", live, "decompose /in.png --res 512 --steps 30"),
        ("no_engine.cbor", dead, "decompose /in.png --res 1280 --steps 30"),
        ("ok.cbor", live, "decompose /in.png --res 1280 --steps 30"),
        ("verb.cbor", live, "render /in.png"),
    ]:
        (out / name).write_bytes(command.ask(state, line))
    print(f"wrote 4 replies to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
