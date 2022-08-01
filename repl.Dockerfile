FROM jupyter/minimal-notebook

COPY requirements/main.txt /tmp/requirements-main.txt
COPY requirements/dev.txt /tmp/requirements-dev.txt
# Don't save pip packages locally; still use Docker cache if requirements unchanged.
RUN pip install --no-cache-dir --upgrade -r/tmp/requirements-main.txt  -r /tmp/requirements-dev.txt
