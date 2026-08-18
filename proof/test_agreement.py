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
import subprocess
import sys
import tempfile
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


def stale(binary, src_root):
    """True when the built writer is older than anything it is built from."""
    newest = max(
        (f.stat().st_mtime for d in ("src", "include", "third_party/interactor")
         for f in (src_root / d).rglob("*") if f.is_file()),
        default=0,
    )
    return binary.stat().st_mtime < newest


def reasons_from_header(path):
    """The C++ half's reason list, read out of its X-macro. Returns None when it is not there."""
    if not Path(path).exists():
        return None
    text = Path(path).read_text()
    block = re.search(r"#define ST_REASONS\(X\)(.*?)\n\n", text, re.S)
    if not block:
        return None
    return re.findall(r"X\((\w+)\)", block.group(1))


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

    # The reply shape. Comparing the gate's numbers is not enough: two halves can refuse the
    # same runs and describe the refusal differently, and a caller that has to branch on which
    # interactor answered is a caller the A/B has failed. This was a real gap -- the C++ half
    # replied in prose for a while after the Python half stopped, and nothing here noticed.
    reasons_cpp = reasons_from_header(CPP / "include/seethrough/command.h")
    if reasons_cpp is None:
        print("note: the C++ reason list was not read; the reply comparison made 0 of its checks")
    else:
        from seethrough.reply import REASONS

        check(reasons_cpp == list(REASONS),
              f"the two halves keep the same reason set ({len(REASONS)} reasons)")

    writer = CPP / "build/seethrough-write-replies"
    if not writer.is_file():
        print("note: seethrough-write-replies is not built; the byte comparison made 0 of its "
              "checks. Build the C++ half to run it.")
    elif stale(writer, CPP):
        # A binary older than its sources reports the bytes of a tree nobody has. That is worse
        # than not running: it invents a divergence, or hides one. Found the hard way -- a
        # cached object file kept an old field name alive through a restore and this check
        # stayed red against sources that were correct.
        print(f"note: {writer.name} is older than the C++ sources; the byte comparison made 0 "
              "of its checks. Rebuild the C++ half and run this again.")
        FAILURES.append("stale C++ binary")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            cpp_dir, py_dir = Path(tmp) / "cpp", Path(tmp) / "py"
            cpp_dir.mkdir()
            py_dir.mkdir()
            subprocess.run([str(writer), str(cpp_dir)], check=True, capture_output=True)
            subprocess.run([sys.executable, str(ROOT / "proof/write_replies.py"), str(py_dir)],
                           check=True, capture_output=True)
            for name in ("res.cbor", "no_engine.cbor", "ok.cbor", "verb.cbor"):
                a, b = (cpp_dir / name).read_bytes(), (py_dir / name).read_bytes()
                check(a == b, f"{name}: both halves emit the same bytes")

    print(f"agreement: {len(FAILURES)} failed of {COMPARED} compared")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
