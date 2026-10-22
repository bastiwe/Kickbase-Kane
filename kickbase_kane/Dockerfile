ARG BUILD_ARCH
FROM ghcr.io/home-assistant/${BUILD_ARCH}-base-python:3.11-alpine3.21

ARG KICKBASE_REF=main

# This layer changes only when Python dependencies change. It is the expensive
# part on a Raspberry Pi and stays cached across ordinary dashboard updates.
COPY requirements-addon.txt /tmp/requirements.txt
RUN apk add --no-cache build-base gfortran lapack-dev linux-headers openblas-dev && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    apk del build-base gfortran linux-headers

# An app version bump refreshes only the shallow source checkout. The runtime
# packages above remain cached, but every release still gets current GitHub code.
COPY config.yaml /tmp/kickbase-addon-config.yaml
RUN apk add --no-cache git && \
    git clone --depth=1 --branch "${KICKBASE_REF}" https://github.com/bastiwe/Kickbase-Kane.git /app && \
    apk del git
COPY run.sh /run.sh
COPY schedule_reports.py /app/addon_schedule_reports.py
RUN chmod a+x /run.sh
CMD [ "/run.sh" ]
