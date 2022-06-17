```bash
docker volume create --name=ads_query_eval_nginx_conf
docker volume create --name=ads_query_eval_letsencrypt_certs
docker-compose up -d
docker-compose logs -f
```

Wait for the following log messages:

```
Switching Nginx to use Let's Encrypt certificate
Reloading Nginx configuration
```

See https://github.com/polyneme/letsencrypt-docker-compose for customization.
