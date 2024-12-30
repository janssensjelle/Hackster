#!/bin/bash

cd /opt/hackster

# Pull latest changes
git pull origin develop

# Set GIT_COMMIT env var
export GIT_COMMIT=$(git rev-parse HEAD)

# Update dependencies
poetry install --no-cache

# Run startup script
exec /opt/hackster/startup.sh