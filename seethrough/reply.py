"""What a reply is: an Elixir term, carried in CBOR.

RFD 0124 decides the shape and this module writes it. Three shapes and nothing else:

    :ok                     nothing to report
    {:ok, value}            something to report
    {:error, reason}        the command failed

A `reason` is an atom, or a tuple of an atom and a map. The atom says what went wrong and the
map carries the numbers. Prose never appears in a reason, because a caller selects a branch on
the atom and no caller can match a sentence. Where a message helps a person it goes in the map
under `:detail`, and no program reads it.

## Why CBOR and not the External Term Format

Both reach the identical term on the BEAM; that was measured, not assumed. ETF is exact with no
adapter, and CBOR needs a decoder that knows this mapping. Three things decide it for CBOR:

- This stack already writes CBOR. `weft/cbor.h` exists, the fan-out path uses it, and
  `transport-bus-cli` reads it. Adding ETF would put two encodings in one tree, and the second
  copy of a decision is the one that drifts.
- Not every caller is a BEAM process. The CLI, the RunPod job output, and anything reading the
  volume decode CBOR with an off-the-shelf library; ETF would need an ETF reader in each.
- The C++ half already has a CBOR writer. Under ETF it would have needed a hand-rolled term
  encoder; under CBOR it needs one tag.

The cost is one decoder module on the Elixir side. It is written once, in the contract, so no
caller writes its own -- which is the objection to an adapter answered rather than dismissed.

## The mapping, which is closed and unambiguous

| Elixir | CBOR |
| --- | --- |
| atom | tag 39 (IANA "identifier") wrapping a text string |
| tuple | an array |
| map | a map |
| binary | a text string |
| integer | an integer |

A reply carries no lists, so an array is always a tuple and the mapping needs no second rule.
A decoder uses `String.to_existing_atom/1`, which refuses an atom the virtual machine does not
have -- the same guarantee `:erlang.binary_to_term/2`'s `[:safe]` gives, obtained by writing it
here instead of relying on it.

SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import struct

# IANA CBOR tag 39, "identifier": the tag Ruby symbols and Erlang atoms are carried under.
# Registered rather than invented, so a decoder that already knows it needs nothing from us.
TAG_IDENTIFIER = 39

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
    """A str that means an Elixir atom rather than a binary."""


def _head(major: int, n: int) -> bytes:
    if n < 24:
        return bytes([major << 5 | n])
    if n < 0x100:
        return bytes([major << 5 | 24, n])
    if n < 0x10000:
        return bytes([major << 5 | 25]) + struct.pack(">H", n)
    if n < 0x100000000:
        return bytes([major << 5 | 26]) + struct.pack(">I", n)
    return bytes([major << 5 | 27]) + struct.pack(">Q", n)


def _text(s: str) -> bytes:
    b = s.encode("utf-8")
    return _head(3, len(b)) + b


def _term(v) -> bytes:
    if isinstance(v, Atom):
        return _head(6, TAG_IDENTIFIER) + _text(str(v))
    if isinstance(v, bool):
        # A reply says what a thing is, not whether it is. A bool in a reason would be a field
        # whose name carries the meaning, and the atom is where meaning belongs.
        raise TypeError("no reply here carries a bool; name the state with an atom instead")
    if isinstance(v, int):
        return _head(0, v) if v >= 0 else _head(1, -v - 1)
    if isinstance(v, str):
        return _text(v)
    if isinstance(v, tuple):
        return _head(4, len(v)) + b"".join(_term(x) for x in v)
    if isinstance(v, dict):
        return _head(5, len(v)) + b"".join(_term(k) + _term(val) for k, val in v.items())
    raise TypeError(f"no encoding here for {type(v).__name__}; a reply's shapes are closed")


def ok(value=None) -> bytes:
    """`:ok`, or `{:ok, value}`. A map's keys are atoms, the way an Elixir caller expects."""
    return _term(Atom("ok")) if value is None else _term((Atom("ok"), value))


def error(reason: str, **detail) -> bytes:
    """`{:error, :reason}`, or `{:error, {:reason, %{...}}}`.

    An unlisted reason raises rather than being sent. A caller using `to_existing_atom` would
    reject it anyway; failing here names the bug at the place that wrote it.
    """
    if reason not in REASONS:
        raise ValueError(f"{reason!r} is not in REASONS; add it there in the same commit")
    if not detail:
        return _term((Atom("error"), Atom(reason)))
    return _term((Atom("error"), (Atom(reason), {Atom(k): v for k, v in detail.items()})))
