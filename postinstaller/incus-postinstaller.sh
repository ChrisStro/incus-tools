#!/usr/bin/env bash

# install incus if not installed
if ! which incus;then
    echo "Installing incus"
    curl https://pkgs.zabbly.com/get/incus-stable | bash -
    incus admin init --auto
fi

# zfs-autosnapshots
if ! which zfs-auto-snapshot;then
    echo "Install zfs autosnapshots"
    apt install -y zfs-auto-snapshot

    # optimize zfs-auto-snapshot
    sed -i "s/keep=4/keep=8/g" /etc/cron.d/zfs-auto-snapshot # frequent
    sed -i "s/keep=24/keep=32/g" /etc/cron.hourly/zfs-auto-snapshot
    sed -i "s/keep=31/keep=10/g" /etc/cron.daily/zfs-auto-snapshot
    sed -i "s/keep=8/keep=4/g" /etc/cron.weekly/zfs-auto-snapshot
    sed -i "s/keep=12/keep=3/g" /etc/cron.monthly/zfs-auto-snapshot
fi

# oci registry
if ! incus remote ls -fcsv |grep docker;then
    echo "Add docker registry to remote"
    incus remote add docker https://docker.io --protocol=oci
fi

# entity backup
if ! which incus-entity-backup;then
    echo "Install incus-entity-backup"
    curl https://raw.githubusercontent.com/ChrisStro/incus-tools/refs/heads/main/entity-backup/install-incus-entity-backup.sh | bash -
fi

# create some profiles
incus profile create snap-weekly << EOF
config:
  snapshots.expiry: 4w
  snapshots.pattern: weekly-{{ creation_date|date:'01-02-2006_15:04' }}
  snapshots.schedule: '@weekly'
EOF
incus profile create snap-daily << EOF
config:
  snapshots.expiry: 10d
  snapshots.pattern: daily-{{ creation_date|date:'01-02-2006_15:04' }}
  snapshots.schedule: '@daily'
EOF
incus profile create snap-hourly << EOF
config:
  snapshots.expiry: 26H
  snapshots.pattern: hourly-{{ creation_date|date:'01-02-2006_15:04' }}
  snapshots.schedule: '@hourly'
EOF
incus profile create snap-frequent << EOF
config:
  snapshots.expiry: 120M
  snapshots.pattern: frequent-{{ creation_date|date:'01-02-2006_15:04' }}
  snapshots.schedule: '*/20 * * * *'
EOF
incus profile create ch << EOF
config:
  security.nesting: "true"
  security.syscalls.intercept.mknod: "true"
  security.syscalls.intercept.setxattr: "true"
description: LXC Container for Docker/Podman
EOF
incus profile create windows << EOF
config:
  limits.cpu: "6"
  limits.memory: 6GiB
description: Default Windows profile
devices:
  agent:
    source: agent:config
    type: disk
  root:
    io.bus: nvme
    path: /
    pool: rpool
    size: 80GiB
    type: disk
  virtio:
    io.bus: usb
    pool: remote
    source: virtio-win.iso
    type: disk
  vtpm:
    path: /dev/tpm0
    type: tpm
EOF
incus profile create windows-install << EOF
config:
  limits.cpu: "6"
  limits.memory: 6GiB
description: Default Windows profile
devices:
  agent:
    source: agent:config
    type: disk
  root:
    io.bus: nvme
    path: /
    pool: rpool
    size: 80GiB
    type: disk
  vtpm:
    path: /dev/tpm0
    type: tpm
EOF
incus profile create windows-install << EOF
description: Windows install profile
devices:
  install:
    source: /PATH/TO/WINDOWS/ISO
    type: disk
  virtio:
    io.bus: usb
    pool: rpool
    source: virtio-win.iso
    type: disk
EOF