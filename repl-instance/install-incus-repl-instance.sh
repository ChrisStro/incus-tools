# install incus-auto-snapshot
wget -O /usr/local/bin/incus-repl-instance https://raw.githubusercontent.com/ChrisStro/incus-tools/refs/heads/main/repl-instance/incus-repl-instance.py
chown root:root /usr/local/bin/incus-repl-instance
chmod 0700 /usr/local/bin/incus-repl-instance

# config file
cat << EOF > /etc/incus-repl-instance.conf
source_server               =   MYREMOTESERVER
repl_prefix                 =   repl
target_project              =   offsite-replication
target_custom_volume_pool   =   default
snap_name_to_clear          =   "None"
EOF
chmod 0600 /etc/incus-repl-instance.conf
chown root:root /etc/incus-repl-instance.conf

# daily replication
cat << EOF > /etc/systemd/system/incus-repl-instance.service
[Unit]
Description=Service incus replication

[Service]
EnvironmentFile=/etc/incus-repl-instance.conf
ExecStart=incus-repl-instance --source-server \$source_server --repl-prefix \$repl_prefix --target-project \$target_project --target-custom-volume-pool \$target_custom_volume_pool --snap-name-to-clear \$snap_name_to_clear
#StandardOutput=append:/var/log/incus-auto-snapshot.log
#StandardError=append:/var/log/incus-auto-snapshot.log
EOF
cat << EOF > /etc/systemd/system/incus-repl-instance.timer
[Unit]
Description=Timer for incus replication

[Timer]
OnCalendar=*-*-* 23:45:00

[Install]
WantedBy=timers.target
EOF

# enable timers
systemctl status incus-repl-instance.timer
