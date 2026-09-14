ARG BUILD_ARCH
FROM ghcr.io/home-assistant/${BUILD_ARCH}-base-python:3.11-alpine3.21

ARG KICKBASE_REF=main
RUN apk add --no-cache build-base gfortran git lapack-dev linux-headers openblas-dev && \
    git clone --depth=1 --branch "${KICKBASE_REF}" https://github.com/bastiwe/Kickbase-Kane.git /app && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    apk del build-base gfortran git linux-headers
COPY run.sh /run.sh
COPY schedule_reports.py /app/addon_schedule_reports.py
RUN chmod a+x /run.sh
CMD [ "/run.sh" ]
