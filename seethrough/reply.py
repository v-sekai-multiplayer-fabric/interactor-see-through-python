"""What a reply is: an Erlang term, in the External Term Format.

RFD 0124 decides this. Three shapes and nothing else:

    :ok                             nothing to report
    {:ok, value}                    something to report
    {:error, reason}                the command failed

A `reason` is an atom, or a tuple of an atom and a map. The atom says what went wrong and the
map carries the numbers. Prose never appears in the reason, because a caller selects a branch
on the atom and no caller can match a sentence. Where a message helps a person it goes in the
map under `:detail`, and no program reads it.

The caller decodes with `:erlang.binary_to_term(bin, [:safe])`, which refuses to create an atom
the virtual machine does not already have. That is why the reason set below is closed: an atom
a caller has no clause for is one it cannot decode, and a clause is exactly what makes the atom
exist. See this RFD's DETAILS.md for the test that established it, including the first reading
of `[:safe]`, which was wrong.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import struct

VERSION = 131
SMALL_INTEGER, INTEGER = 97, 98
ATOM_UTF8, SMALL_ATOM_UTF8 = 118, 119
SMALL_TUPLE, NIL, BINARY, MAP = 104, 106, 109, 116

# Every reason this interactor may send. A new one is a change to this tuple, in the same commit
# that first sends it, and the C++ half's list must match -- two implementations that report
# different reasons for the same refusal are not answering the same question.
REASONS = (
    "res_below_minimum",     # --res under the production setting
    "steps_below_minimum",   # --steps under the production setting
    "unknown_command",       # a verb this interactor does not answer
    "unknown_flag",
    "missing_value",         # a flag with no value after it
    "missing_input_path",
    "too_many_input_paths",
    "not_a_number",
    "no_engine",             # the weights were never loaded
    "decompose_failed",      # the pipeline ran and did not succeed
)


class Atom(str):
    """A str that means an Erlang atom rather than a binary."""


def _atom(name: str) -> bytes:
    b = name.encode("utf-8")
    if len(b) < 256:
        return bytes([SMALL_ATOM_UTF8, len(b)]) + b
    return bytes([ATOM_UTF8]) + struct.pack(">H", len(b)) + b


def _term(v) -> bytes:
    if isinstance(v, Atom):
        return _atom(v)
    if isinstance(v, bool):
        return _atom("true" if v else "false")
    if isinstance(v, int):
        if 0 <= v < 256:
            return bytes([SMALL_INTEGER, v])
        if -(2**31) <= v < 2**31:
            return bytes([INTEGER]) + struct.pack(">i", v)
        # A reply needing a bignum is a reply shape nobody agreed on. Refusing it here is the
        # check: it cannot reach a caller in a form that decodes to something unexpected.
        raise ValueError(f"{v} is outside the integer subset a reply carries")
    if isinstance(v, (str, bytes)):
        b = v.encode("utf-8") if isinstance(v, str) else v
        return bytes([BINARY]) + struct.pack(">I", len(b)) + b
    if isinstance(v, tuple):
        return bytes([SMALL_TUPLE, len(v)]) + b"".join(_term(x) for x in v)
    if isinstance(v, dict):
        out = bytes([MAP]) + struct.pack(">I", len(v))
        for k, val in v.items():
            out += _term(k) + _term(val)
        return out
    if isinstance(v, list) and not v:
        return bytes([NIL])
    raise TypeError(f"no term encoding here for {type(v).__name__}")


def encode(v) -> bytes:
    return bytes([VERSION]) + _term(v)


def ok(value=None) -> bytes:
    """`:ok`, or `{:ok, value}`. A map's keys are atoms, the way an Elixir caller expects."""
    if value is None:
        return encode(Atom("ok"))
    return encode((Atom("ok"), value))


def error(reason: str, **detail) -> bytes:
    """`{:error, :reason}`, or `{:error, {:reason, %{...}}}`.

    An unlisted reason raises rather than being sent. A caller decoding with `[:safe]` would
    reject it anyway; failing here names the bug at the place that wrote it.
    """
    if reason not in REASONS:
        raise ValueError(f"{reason!r} is not in REASONS; add it there in the same commit")
    if not detail:
        return encode((Atom("error"), Atom(reason)))
    return encode((Atom("error"), (Atom(reason), {Atom(k): v for k, v in detail.items()})))
