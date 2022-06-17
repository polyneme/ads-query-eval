```bash
docker volume create --name=ads_query_eval_nginx_conf
docker volume create --name=ads_query_eval_letsencrypt_certs
docker-compose up -d
docker-compose logs -f # to confirm certificate installation
```

See https://github.com/polyneme/letsencrypt-docker-compose for customization.
