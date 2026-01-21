# install incus-auto-snapshot
wget -O /usr/local/bin/incus-entity-backup https://raw.githubusercontent.com/ChrisStro/incus-tools/refs/heads/main/entity-backup/incus-entity-backup.sh
chown root:incus-admin /usr/local/bin/incus-entity-backup
chmod 0700 /usr/local/bin/incus-entity-backup

# create target directory
if command -v zfs >/dev/null 2>&1; then
    ROOTDATASET=$(zfs list -Honame -d0|head -n1)
    zfs create -o mountpoint=/incus-entities $ROOTDATASET/incus-entities
    else
    mkdir -p /incus-entities
fi

# config file
cat << EOF > /etc/incus-entitiy-backup.conf
KEEP            =   5
BASE_BACKUP_DIR =   "/incus-entities"
COMPRESS        =   no
EOF
chmod 0600 /etc/incus-entitiy-backup.conf
chown root:root /etc/incus-entitiy-backup.conf

# entity entity
cat << EOF > /etc/systemd/system/incus-entity-backup.service
[Unit]
Description=Service for frequent entity incus entity

[Service]
EnvironmentFile=/etc/incus-entitiy-backup.conf
ExecStart=incus-entity-backup \$KEEP \$BASE_BACKUP_DIR \$COMPRESS
EOF
cat << EOF > /etc/systemd/system/incus-entity-backup.timer
[Unit]
Description=Timer for frequent incus backup of entities

[Timer]
OnCalendar=*:0/20

[Install]
WantedBy=timers.target
EOF

# enable timers
systemctl enable --now incus-entity-backup.timer
