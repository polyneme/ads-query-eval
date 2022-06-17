# Start from the official Python base image.
FROM python:3.9

# Set the current working directory to /code.
# This is where we'll put the requirements.txt file and the app directory.
WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

# Don't save pip packages locally; still use Docker cache if requirements.txt unchanged.
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
