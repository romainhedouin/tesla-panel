#!/bin/bash
set -e

## Copies this repo onto the Pi, ready for `pi_side_install.sh` to be run
## there. Targets the `teslapi` SSH host (add it to ~/.ssh/config, or pass a
## different host as $1) rather than a hardcoded IP, since that's the one
## thing guaranteed to go stale.
HOST="${1:-teslapi}"

## known_hosts is keyed by whatever `ssh -G` resolves HOST's HostName to, not
## the alias itself - reflashing the SD card gives the Pi a new host key at
## the same IP, so both need clearing or you get stuck on the old one.
ssh-keygen -R "$HOST" 2>/dev/null || true
RESOLVED_HOST=$(ssh -G "$HOST" | awk '/^hostname /{print $2}')
[ -n "$RESOLVED_HOST" ] && ssh-keygen -R "$RESOLVED_HOST" 2>/dev/null || true
## rsync, not scp -r: skips .git (the Pi doesn't need history, and re-syncing
## git's own read-only packed objects with plain scp fails on the second run
## with Permission denied) and only transfers what actually changed.
SSH_OPTS="-o StrictHostKeyChecking=accept-new"
rsync -a -e "ssh $SSH_OPTS" --exclude=.git --exclude=.github --exclude=.vscode \
  ./ "$HOST":/home/pi/
scp $SSH_OPTS conf/.bashrc "$HOST":/home/pi

echo "Copied. Now: ssh $HOST, then run ./pi_side_install.sh"
