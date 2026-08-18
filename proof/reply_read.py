"""A reader, for the proof only.

The interactor writes replies and never reads one, so this is not shipped: it exists so a test
can assert on `{:error, {:res_below_minimum, ...}}` rather than on a byte pattern, on a machine
with no Erlang installed. `proof/elixir_compat.exs` is the authoritative check.

SPDX-License-Identifier: Apache-2.0
"""

import struct

TAG_IDENTIFIER = 39


class Atom(str):
    pass


def _argument(b, i):
    minor = b[i] & 0x1F
    i += 1
    if minor < 24:
        return minor, i
    width = {24: 1, 25: 2, 26: 4, 27: 8}.get(minor)
    if width is None:
        raise ValueError("indefinite or reserved length is not in a reply")
    return int.from_bytes(b[i:i + width], "big"), i + width


def _item(b, i):
    major = b[i] >> 5
    n, i = _argument(b, i)
    if major == 0:
        return n, i
    if major == 1:
        return -1 - n, i
    if major == 3:
        return b[i:i + n].decode("utf-8"), i + n
    if major == 4:  # an array is a tuple; a reply carries no lists
        out = []
        for _ in range(n):
            v, i = _item(b, i)
            out.append(v)
        return tuple(out), i
    if major == 5:
        out = {}
        for _ in range(n):
            k, i = _item(b, i)
            v, i = _item(b, i)
            out[k] = v
        return out, i
    if major == 6:
        if n != TAG_IDENTIFIER:
            raise ValueError(f"tag {n} is not one a reply uses")
        text, i = _item(b, i)
        return Atom(text), i
    raise ValueError(f"major type {major} is not in a reply")


def loads(b):
    v, i = _item(b, 0)
    if i != len(b):
        raise ValueError(f"{len(b) - i} bytes left over")
    return v
