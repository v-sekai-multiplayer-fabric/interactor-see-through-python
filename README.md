# interactor-see-through-python

Single-image layer decomposition for anime characters, after
[See-through](https://doi.org/10.1145/3799902.3811209), as an interactor on the harness command
bus. The Python half of a pair; `interactor-see-through-cpp` is the other.

## Why there are two

The same reason `transport-gateway-python` exists beside `transport-gateway-c`: a second
implementation that shares nothing with the first can disagree with it, and one that shares a
parser cannot. This half is the reference pipeline over PyTorch and reaches the bus through
iceoryx2's Python binding; that half is ggml and the C ABI through a dlsym table. What they
share is the wire between them, and `weft_harness/bus.py` is written against
`weft/command.hpp` so they agree on the service names, the `weft::byte` payload and the 8-byte
request-id envelope.

`proof/test_agreement.py` is the A/B's own control. A timing comparison between two interactors
means nothing unless they refuse the same runs, so it reads the gate's two numbers back out of
the C++ header and fails when they differ. It also prints how many things it compared, because
a check that looked at nothing reads exactly like agreement.

## The gate

**A run below 1280px or 30 steps is refused, not served.** Low step counts make degenerate
layers — undifferentiated depth medians, soft detail — that look plausible in a viewer and say
nothing about output quality, and a 512px/8-step artefact that vanished at 1280/30 is what the
see-through project's MADR 0009 was written about. `proof/test_command.py` runs the same cases
its C++ twin runs, against different code.

The timing in the reply is measured by the engine around its own work. A duration taken from
anywhere else has been wrong here before, confidently, in the direction of a defect that did
not exist.

## Where the weights are

On the network volume RunPod mounts at `/runpod-volume`, never in the image: an image carrying
them re-downloads gigabytes into every cold worker, where the volume is written once and read
by all. A worker that cannot find them answers every job with the path it looked in rather than
exiting, so the reason reaches the job result instead of dying with the worker.
