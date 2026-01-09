#!/bin/sh
set -eu

PORT_VALUE="${PORT:-8080}"

exec reflex run --env prod --single-port --backend-host 0.0.0.0 --frontend-port "$PORT_VALUE"
