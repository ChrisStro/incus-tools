# install incus-auto-snapshot
wget -O /usr/local/bin/incus-entity-backup https://raw.githubusercontent.com/ChrisStro/incus-tools/refs/heads/main/entity-backup/incus-entity-backup.sh
chown root:incus-admin /usr/local/bin/incus-entity-backup
chmod 0700 /usr/local/bin/incus-entity-backup

# create target directory
which zfs && zfs create -o mountpoint=/incus-backup rpool/incus-backup || mkdir -p /incus-backup;

# frequent snapshot
cat << EOF > /etc/systemd/system/incus-entity-backup.service
[Unit]
Description=Service for frequent entity incus backups

[Service]
ExecStart=incus-entity-backup 5 /incus-backup
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
