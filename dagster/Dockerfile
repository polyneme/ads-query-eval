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


WORKDIR /opt/dagster/lib
COPY ./requirements.txt  /opt/dagster/lib/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /opt/dagster/lib/requirements.txt

COPY ./repo /opt/dagster/lib/repo

# Set $DAGSTER_HOME and copy dagster instance and workspace YAML there
ENV DAGSTER_HOME=/opt/dagster/dagster_home/
RUN mkdir -p $DAGSTER_HOME
COPY ./repo/dagster.yaml $DAGSTER_HOME
COPY ./repo/workspace.yaml $DAGSTER_HOME
WORKDIR $DAGSTER_HOME

# Best practices: Prepare for C crashes.
ENV PYTHONFAULTHANDLER=1

# Run dagit server on port 3000
EXPOSE 3000

ENTRYPOINT ["tini", "--", "../lib/repo/entrypoint-dagit.sh"]