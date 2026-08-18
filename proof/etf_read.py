"""A reader, for the proof only.

The interactor writes terms and never reads one, so this is not shipped: it exists so a test
can assert on `{:error, {:res_below_minimum, ...}}` rather than on a byte pattern. The
authoritative check is `proof/elixir_compat.exs`, which uses a real virtual machine; this one
runs where there is no Erlang installed.

SPDX-License-Identifier: Apache-2.0
"""

import struct


class Atom(str):
    pass


def _read(b, i):
    tag = b[i]
    i += 1
    if tag == 97:
        return b[i], i + 1
    if tag == 98:
        return struct.unpack(">i", b[i:i + 4])[0], i + 4
    if tag in (118, 119):
        n, i = (struct.unpack(">H", b[i:i + 2])[0], i + 2) if tag == 118 else (b[i], i + 1)
        return Atom(b[i:i + n].decode()), i + n
    if tag == 109:
        n = struct.unpack(">I", b[i:i + 4])[0]
        i += 4
        return b[i:i + n].decode(), i + n
    if tag == 104:
        n, i = b[i], i + 1
        out = []
        for _ in range(n):
            v, i = _read(b, i)
            out.append(v)
        return tuple(out), i
    if tag == 116:
        n = struct.unpack(">I", b[i:i + 4])[0]
        i += 4
        out = {}
        for _ in range(n):
            k, i = _read(b, i)
            v, i = _read(b, i)
            out[k] = v
        return out, i
    if tag == 106:
        return [], i
    raise ValueError(f"tag {tag} is not in the subset a reply uses")


def loads(b):
    if not b or b[0] != 131:
        raise ValueError("not an external term")
    v, i = _read(b, 1)
    if i != len(b):
        raise ValueError(f"{len(b) - i} bytes left over")
    return v
