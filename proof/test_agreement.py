"""The A/B's own control: the two implementations must be answering the same question.

A timing comparison between two interactors is meaningful only if they refuse the same runs,
carry the same envelope and speak on the same services. Nothing in either repository forces
that -- both were written twice on purpose -- so this is the check that would have caught the
drift, and it names how many things it compared, because zero comparisons read exactly like
agreement.

SPDX-License-Identifier: Apache-2.0
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "third_party/harness/python"))

from seethrough import command  # noqa: E402
from weft_harness import check_matches_header  # noqa: E402

# The C++ interactor, when it is on disk. `default.xml` puts both on side 3, so a workspace
# has it beside this one; a CI runner checks it out wherever it likes and says where through
# ST_CPP_ROOT. A runner cannot use the sibling path -- Actions refuses a checkout above the
# workspace directory, which is how this check first went red rather than quiet.
CPP = Path(os.environ.get("ST_CPP_ROOT") or (ROOT.parent / "see-through-cpp"))

FAILURES = []
COMPARED = 0


def check(ok, what):
    global COMPARED
    COMPARED += 1
    print(f"{'ok  ' if ok else 'FAIL'} {what}")
    if not ok:
        FAILURES.append(what)


def main():
    # The bus. This header is vendored here, so this half always runs.
    problems = check_matches_header(ROOT / "third_party/harness/include/weft/command.hpp")
    check(not problems, f"the Python bus agrees with weft/command.hpp{': ' + '; '.join(problems) if problems else ''}")

    # The gate. Only when the C++ interactor is on disk.
    header = CPP / "include/seethrough/command.h"
    if not header.exists():
        print(f"note: {CPP.name} is not checked out; the gate comparison made 0 of its checks")
    else:
        text = header.read_text()
        for name, mine in (("ST_MIN_RES", command.MIN_RES), ("ST_MIN_STEPS", command.MIN_STEPS)):
            match = re.search(rf"#define {name} (\d+)", text)
            theirs = int(match.group(1)) if match else None
            check(theirs == mine, f"{name}: C++ says {theirs}, Python says {mine}")

        for name, mine in (
            ("ST_WEIGHTS_DIR_DEFAULT", command.WEIGHTS_DIR_DEFAULT),
        ):
            match = re.search(rf'#define {name} "([^"]+)"', text)
            theirs = match.group(1) if match else None
            check(theirs == mine, f"{name}: C++ says {theirs!r}, Python says {mine!r}")

    print(f"agreement: {len(FAILURES)} failed of {COMPARED} compared")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
