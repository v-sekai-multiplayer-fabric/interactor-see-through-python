"""What a reply is made of.

CBOR, not JSON, because the reply crosses the same bus the C++ interactor's replies cross and
a caller decodes both with one decoder. `contract-command`'s `weft/cbor.h` is the writer on
that side; this is the same encoding written again in Python rather than bound to that C, for
the reason the two interactors exist at all -- an implementation that shares the encoder cannot
disagree with it, and disagreeing is the job.

SPDX-License-Identifier: Apache-2.0
"""


def _head(major: int, n: int) -> bytes:
    """RFC 8949 3.1: the argument goes in the low five bits, or in the bytes that follow."""
    if n < 24:
        return bytes([major << 5 | n])
    if n < 0x100:
        return bytes([major << 5 | 24, n])
    if n < 0x10000:
        return bytes([major << 5 | 25]) + n.to_bytes(2, "big")
    if n < 0x100000000:
        return bytes([major << 5 | 26]) + n.to_bytes(4, "big")
    return bytes([major << 5 | 27]) + n.to_bytes(8, "big")


def text(s: str) -> bytes:
    b = s.encode("utf-8")
    return _head(3, len(b)) + b


def integer(v: int) -> bytes:
    return _head(0, v) if v >= 0 else _head(1, -v - 1)


def value(v) -> bytes:
    if isinstance(v, bool):
        raise TypeError("no reply here carries a bool; say what it is instead")
    if isinstance(v, int):
        return integer(v)
    if isinstance(v, str):
        return text(v)
    raise TypeError(f"no CBOR encoding here for {type(v).__name__}")


def mapping(pairs: dict) -> bytes:
    """A definite-length map. Indefinite would need a break byte and buys nothing: every reply
    this interactor writes knows its own size before it starts."""
    out = _head(5, len(pairs))
    for k, v in pairs.items():
        out += text(k) + value(v)
    return out


def error(message: str) -> bytes:
    return mapping({"error": message})
