```bash
source .env
docker volume create --name=${COMPOSE_PROJECT_NAME}_nginx_conf
docker volume create --name=${COMPOSE_PROJECT_NAME}_letsencrypt_certs
docker volume create --name=${COMPOSE_PROJECT_NAME}_mongo_data
docker volume create --name=${COMPOSE_PROJECT_NAME}_dagster_postgres_data
docker-compose up -d
docker-compose logs -f # to confirm resource readiness and certificate installation
```

See https://github.com/polyneme/letsencrypt-docker-compose for customization.
