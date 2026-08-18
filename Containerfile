# The Python half of the A/B, as one RunPod Serverless worker.
#
# Two processes, because that is the shape being tested: the transport layer takes jobs from
# the endpoint queue and the interactor holds the model, and they meet on the bus rather than
# in one address space. A job that kills the pipeline therefore does not take the worker's HTTP
# loop with it, and the weights load once at start instead of once per job.
#
# The transport arrives as a base image rather than as source, so this repository holds no copy
# of a job loop it does not own. Override TRANSPORT_IMAGE to build against a local one.
ARG TRANSPORT_IMAGE=ghcr.io/v-sekai-multiplayer-fabric/transport-runpod-python:main
FROM ${TRANSPORT_IMAGE}

# No weights in the image. They are cached on the network volume RunPod mounts at
# /runpod-volume, written once and read by every worker in the data center; an image carrying
# them re-downloads gigabytes into each cold worker instead.
ENV ST_WEIGHTS_DIR=/runpod-volume/see-through/weights \
    ST_OUT_DIR=/runpod-volume/see-through/out \
    ST_ENGINE=reference

COPY seethrough /app/interactor/seethrough
COPY proof /app/interactor/proof
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

ENV PYTHONPATH=/app/interactor:/app/transport:/app/harness

# The gate, in the build. An image whose interactor would serve a 512px run is not one this
# endpoint should be able to produce, and that is cheaper to find here than in a job result.
RUN chmod +x /usr/local/bin/entrypoint.sh && python /app/interactor/proof/test_command.py

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
