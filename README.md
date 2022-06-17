```bash
docker volume create --name=ads_query_eval_mongo_data
docker volume create --name=ads_query_eval_dagster_postgres_data
docker volume create --name=ads_query_eval_nginx_conf
docker volume create --name=ads_query_eval_letsencrypt_certs
docker-compose up -d
docker-compose logs -f # to confirm resource readiness and certificate installation
```

See https://github.com/polyneme/letsencrypt-docker-compose for customization.
