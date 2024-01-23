#!/bin/sh
docker stop burrow
docker rm burrow
docker run -d --restart unless-stopped --name burrow --env TZ=America/New_York -v /opt/burrow/config.yaml:/app/config.yaml burrow:latest