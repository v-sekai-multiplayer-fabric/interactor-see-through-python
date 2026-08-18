"""The interactor: the harness command loop, with the reference pipeline behind it.

No socket, no HTTP, no RunPod. What reaches this process is a command off the bus and what
leaves it is reply bytes, which is the same contract `interactor-see-through-cpp` answers --
the transport layer in front cannot tell the two apart, and that is what makes the A/B an A/B.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from weft_harness import Bus, serve

from . import command
from .engine import EngineAbsent, engine_from_env


@dataclass
class State:
    engine: object
    out_root: str
    opened: bool


def main() -> int:
    weights = os.environ.get("ST_WEIGHTS_DIR") or command.WEIGHTS_DIR_DEFAULT
    out_root = os.environ.get("ST_OUT_DIR") or command.OUT_DIR_DEFAULT
    engine = engine_from_env(os.environ.get("ST_ENGINE", "reference"))

    state = State(engine=engine, out_root=out_root, opened=False)
    try:
        engine.open(weights)
        state.opened = True
    except EngineAbsent as why:
        # Not fatal, and that is the point. A worker that exits here takes its explanation
        # with it: RunPod records a worker that died before its first job, and the job it
        # would have refused is retried against another worker that dies the same way.
        # Answering every command with this line puts the reason in the job result instead.
        print(f"see-through: {why}", file=sys.stderr, flush=True)

    print(f"see-through: serving, weights={weights} out={out_root}", file=sys.stderr, flush=True)
    return serve(Bus("server"), lambda line: command.ask(state, line.decode("utf-8", "replace")))


if __name__ == "__main__":
    raise SystemExit(main())
