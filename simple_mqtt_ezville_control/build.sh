#!/bin/bash
docker build -t ezville:latest .
docker-compose up --remove-orphans