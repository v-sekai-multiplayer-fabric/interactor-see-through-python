#!/bin/sh
# The interactor first, then the transport layer.
#
# Order matters only for how the first job reads. Both ends `open_or_create` their services, so
# either may start first without the other failing -- but the interactor is the slow one to
# come up, since it loads weights, and a worker that took a job before it was ready would spend
# that time inside the job's own clock rather than before it.
#
# If either process exits, so does the container. A worker whose interactor has died answers
# every job with a deadline, which RunPod records as slow rather than as broken; exiting makes
# it a worker failure, which is the true statement and the one that gets it replaced.
set -eu

python -m seethrough &
interactor=$!

python -m rp_bus &
worker=$!

# `wait -n` returns as soon as either exits. POSIX sh has no -n, and this image has no bash, so
# poll instead: one second of lag on a container teardown costs nothing.
while kill -0 "$interactor" 2>/dev/null && kill -0 "$worker" 2>/dev/null; do
    sleep 1
done

kill "$interactor" "$worker" 2>/dev/null || true
wait "$interactor" 2>/dev/null || true
wait "$worker" 2>/dev/null || true
echo "see-through: a process exited; the worker is going down with it" >&2
exit 1
