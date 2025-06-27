# install incus-auto-snapshot
wget -O /usr/local/bin/incus-auto-snapshot https://raw.githubusercontent.com/ChrisStro/incus-tools/refs/heads/main/auto-snapshot/incus-auto-snapshot.py
chown root:incus-admin /usr/local/bin/incus-auto-snapshot
chmod 0700 /usr/local/bin/incus-auto-snapshot

# config file
cat << EOF > /etc/incus-auto-snapshot.conf
# 120 Minutes
frequent_expire = 120M
# 3  Days
hourly_expire   = 3d
# 14  Days
daily_expire    = 14d
# 4  Weeks
weekly_expire   = 4w
# 3  Mounths
monthly_expire  = 3m

# Include custom storage volumes
include_volumes  = True
EOF
chmod 0600 /etc/incus-auto-snapshot.conf
chown root:root /etc/incus-auto-snapshot.conf

# frequent snapshot
cat << EOF > /etc/systemd/system/incus-auto-snapshot-frequent.service
[Unit]
Description=Service for frequent incus snapshots

[Service]
EnvironmentFile=/etc/incus-auto-snapshot.conf
ExecStart=incus-auto-snapshot --prefix frequent --expiry \$frequent_expire --include-volumes=\$include_volumes
StandardOutput=append:/var/log/incus-auto-snapshot.log
StandardError=append:/var/log/incus-auto-snapshot.log
EOF
cat << EOF > /etc/systemd/system/incus-auto-snapshot-frequent.timer
[Unit]
Description=Timer for frequent incus snapshots

[Timer]
OnCalendar=*:0/20

[Install]
WantedBy=timers.target
EOF

# hourly snapshot
cat << EOF > /etc/systemd/system/incus-auto-snapshot-hourly.service
[Unit]
Description=Service for hourly incus snapshots

[Service]
EnvironmentFile=/etc/incus-auto-snapshot.conf
ExecStart=incus-auto-snapshot --prefix hourly --expiry \$hourly_expire --include-volumes=\$include_volumes
StandardOutput=append:/var/log/incus-auto-snapshot.log
StandardError=append:/var/log/incus-auto-snapshot.log
EOF
cat << EOF > /etc/systemd/system/incus-auto-snapshot-hourly.timer
[Unit]
Description=Timer for hourly incus snapshots

[Timer]
OnCalendar=*:05

[Install]
WantedBy=timers.target
EOF

# daily snapshot
cat << EOF > /etc/systemd/system/incus-auto-snapshot-daily.service
[Unit]
Description=Service for daily incus snapshots

[Service]
EnvironmentFile=/etc/incus-auto-snapshot.conf
ExecStart=incus-auto-snapshot --prefix daily --expiry \$daily_expire --include-volumes=\$include_volumes
StandardOutput=append:/var/log/incus-auto-snapshot.log
StandardError=append:/var/log/incus-auto-snapshot.log
EOF
cat << EOF > /etc/systemd/system/incus-auto-snapshot-daily.timer
[Unit]
Description=Timer for daily incus snapshots

[Timer]
OnCalendar=*-*-* 23:50:00

[Install]
WantedBy=timers.target
EOF

# weekly snapshot
cat << EOF > /etc/systemd/system/incus-auto-snapshot-weekly.service
[Unit]
Description=Service for weekly incus snapshots

[Service]
EnvironmentFile=/etc/incus-auto-snapshot.conf
ExecStart=incus-auto-snapshot --prefix weekly --expiry \$weekly_expire --include-volumes=\$include_volumes
StandardOutput=append:/var/log/incus-auto-snapshot.log
StandardError=append:/var/log/incus-auto-snapshot.log
EOF
cat << EOF > /etc/systemd/system/incus-auto-snapshot-weekly.timer
[Unit]
Description=Timer for weekly incus snapshots

[Timer]
OnCalendar=Sun *-*-* 01:50:00

[Install]
WantedBy=timers.target
EOF

# monthly snapshot
cat << EOF > /etc/systemd/system/incus-auto-snapshot-monthly.service
[Unit]
Description=Service for monthly incus snapshots

[Service]
EnvironmentFile=/etc/incus-auto-snapshot.conf
ExecStart=incus-auto-snapshot --prefix monthly --expiry \$monthly_expire --include-volumes=\$include_volumes
StandardOutput=append:/var/log/incus-auto-snapshot.log
StandardError=append:/var/log/incus-auto-snapshot.log
EOF
cat << EOF > /etc/systemd/system/incus-auto-snapshot-monthly.timer
[Unit]
Description=Timer for monthly incus snapshots

[Timer]
OnCalendar=Sun *-*-01..07 02:35:00

[Install]
WantedBy=timers.target
EOF

# enable timers
systemctl enable --now incus-auto-snapshot-{frequent,hourly,daily,weekly,monthly}.timer
