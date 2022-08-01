# Best practice: Choose a stable base image and tag.
FROM python:3.9-slim-bullseye

# Install security updates, and some useful packages.
#
# Best practices:
# * Make sure apt-get doesn't run in interactive mode.
# * Update system packages.
# * Pre-install some useful tools.
# * Minimize system package installation.
RUN export DEBIAN_FRONTEND=noninteractive && \
  apt-get update && \
  apt-get -y upgrade && \
  apt-get install -y --no-install-recommends tini procps net-tools \
  build-essential git make zip && \
  apt-get -y clean && \
  rm -rf /var/lib/apt/lists/*


COPY requirements/main.txt /tmp/requirements-main.txt
COPY requirements/dev.txt /tmp/requirements-dev.txt

# Don't save pip packages locally; still use Docker cache if requirements unchanged.
RUN pip install --no-cache-dir --upgrade -r/tmp/requirements-main.txt  -r /tmp/requirements-dev.txt

WORKDIR /code

COPY ads_query_eval/ /code/ads_query_eval/
COPY setup.py /code/

RUN pip install --editable /code

# Set $DAGSTER_HOME and copy dagster instance and workspace YAML there
ENV DAGSTER_HOME=/opt/dagster/home/
RUN mkdir -p $DAGSTER_HOME
COPY dagster/ $DAGSTER_HOME

# Best practices: Prepare for C crashes.
ENV PYTHONFAULTHANDLER=1
