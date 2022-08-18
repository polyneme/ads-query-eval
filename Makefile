include .env

init:
	pip install --upgrade pip-tools pip setuptools
	pip install --editable .
	pip install --upgrade -r requirements/main.txt  -r requirements/dev.txt

update-deps:
	pip install --upgrade pip-tools pip setuptools
	pip-compile --upgrade --build-isolation --generate-hashes --output-file \
		requirements/main.txt requirements/main.in
	pip-compile --upgrade --build-isolation --generate-hashes --output-file \
		requirements/dev.txt requirements/dev.in

update: update-deps init

lint:
	# Python syntax errors or undefined names
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --extend-ignore=F722
	# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 \
		--statistics --extend-exclude="./build/" --extend-ignore=F722

schema-inspect:
	docker-compose exec app \
		python -c 'import json; from ads_query_eval.config import get_terminus_config; c = get_terminus_config(); print(json.dumps(c["schema_objects"], indent=2))'

up-dev:
	docker-compose up -d --build --force-recreate

up-dagster-dev:
	docker-compose up -d --build --force-recreate dagster-dagit dagster-daemon

reset-dev:
	docker-compose down
	docker volume rm $(COMPOSE_PROJECT_NAME)_dagster_postgres_data
	docker volume create --name=$(COMPOSE_PROJECT_NAME)_dagster_postgres_data
	docker volume rm $(COMPOSE_PROJECT_NAME)_terminus_data
	docker volume create --name=$(COMPOSE_PROJECT_NAME)_terminus_data
	docker-compose up -d --build --force-recreate