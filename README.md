# Incus-Tools
-----

* [Description](#description)
* [incus-auto-snapshot](#incus-auto-snapshot)
* [incus-repl-instance](#incus-repl-instance)

# Description

This repo contains some usefull script for my [`incus`](https://github.com/lxc/incus/) deployments. Incus is awesome btw!!!

## Incus-auto-snapshot

Since the automatic snapshot engine in incus is not sufficient for me, I have created a small script + some systemd unit files to configure auto-snapshotting with different retention policies.

```
# Install snapshot-engine
curl https://raw.githubusercontent.com/ChrisStro/incus-auto-snapshot/refs/heads/main/auto-snapshot/install-incus-snapshot.sh | bash -
```

Every instance(or custom storage volume) with the custom user config user.auto-snapshot=true will be targeted by the snapshot-engine, you can apply these settings via instance or profiles

```
# Profile
incus profile set default user.auto-snapshot=true

# Instance
incus config set MYINSTANCE user.auto-snapshot=true

# Exclude instance if applied via profile
incus config set MYINSTANCE user.auto-snapshot=false # other value than 'true'

# Check which instances are targeted
incus ls user.auto-snapshot=true
```



## Incus-repl-instance

Script and systemd service + timer to trigger pull copy from remote instances.

```
# Install repl-engine
curl https://raw.githubusercontent.com/ChrisStro/incus-auto-snapshot/refs/heads/main/repl-instance/install-repl-instance.sh | bash -
```
