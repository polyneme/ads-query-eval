#!/usr/bin/env bash
for i in `docker-compose logs repl | grep ':8888/lab?token=' | tail -1 | cut -d '=' -f 2`
do
open "http://localhost:8998/lab?token=${i}"
done