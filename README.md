```bash
docker volume create --name=ads_query_eval_mongo_data
docker volume create --name=ads_query_eval_dagster_postgres_data
docker-compose up -d
docker-compose logs -f # to confirm resource readiness
```

See https://github.com/polyneme/letsencrypt-docker-compose for customization.
