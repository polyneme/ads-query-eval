Demo up at <https://ads-query-eval.polyneme.xyz>.


# Local Development

```bash
cp .env.example .env # and modify .env as appropriate
source .env
docker volume create --name=${COMPOSE_PROJECT_NAME}_terminus_data
docker volume create --name=${COMPOSE_PROJECT_NAME}_dagster_postgres_data
docker-compose up -d
# Confirm resource readiness
docker-compose logs -f
```

To get an interactive shell:
```
docker-compose exec repl bash
ipython
```

# Production

```bash
# Optional: cp .env.example .env # and modify .env as appropriate
source .env
docker volume create --name=${COMPOSE_PROJECT_NAME}_terminus_data
docker volume create --name=${COMPOSE_PROJECT_NAME}_dagster_postgres_data
docker volume create --name=${COMPOSE_PROJECT_NAME}_nginx_conf
docker volume create --name=${COMPOSE_PROJECT_NAME}_letsencrypt_certs
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
# Confirm resource readiness and certificate installation
docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
```

See https://github.com/polyneme/letsencrypt-docker-compose for customization.
