FROM jupyter/minimal-notebook

COPY --chown=${NB_UID}:${NB_GID} requirements/main.txt /tmp/requirements-main.txt
COPY --chown=${NB_UID}:${NB_GID} requirements/dev.txt /tmp/requirements-dev.txt

RUN pip install --no-cache-dir --upgrade \
    -r /tmp/requirements-main.txt \
    -r /tmp/requirements-dev.txt && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"

COPY --chown=${NB_UID}:${NB_GID} ads_query_eval/ /home/jovyan/code/ads_query_eval/
COPY --chown=${NB_UID}:${NB_GID} setup.py /home/jovyan/code/

RUN pip install --no-cache-dir --editable /home/jovyan/code/ && \
    fix-permissions "${CONDA_DIR}" && \
    fix-permissions "/home/${NB_USER}"
