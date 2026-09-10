#!/usr/bin/env bash
# Compat wrapper — prefer sync-router-worker-skills.sh
exec "$(cd "$(dirname "$0")" && pwd)/sync-router-worker-skills.sh"
