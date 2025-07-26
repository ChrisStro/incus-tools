#!/bin/bash
set -e

KEEP=${1:-5}
BASE_BACKUP_DIR=${2:-"$HOME/incus-entities"}
COMPRESS=${3:-"yes"}

echo "Keep Copies   : $KEEP"
echo "Backup dir    : $BASE_BACKUP_DIR"
echo "Compress dir  : $COMPRESS"

# Falls kein Projekt existiert, sichert der Default "default"
projects=$(incus project list -c n --format csv|sed 's/(current)//g')
if [ -z "$projects" ]; then
  projects="default"
fi

SUB_BACKUP_DIR="${BASE_BACKUP_DIR}/incus-backup-$(date '+%Y-%m-%d_%H-%M-%S')"

for project in $projects; do
  echo "Sichere Projekt: $project"

  # Projekt-spezifisches Backup-Verzeichnis mit Zeitstempel
  BACKUP_DIR="${SUB_BACKUP_DIR}/${project}"
  mkdir -p "$BACKUP_DIR"

  # Setze Projekt-Umgebungsvariable für alle incus-Befehle in diesem Durchlauf
  export INCUS_PROJECT=$project

  # --- Backup: Profiles ---
  for profile in $(incus profile list -c n --format csv); do
    incus profile show "$profile" > "$BACKUP_DIR/profile-${profile}.yaml"
  done

  # --- Backup: Instanzen ---
  for instance in $(incus list --format csv -c n); do
    incus config show "$instance" --expanded > "$BACKUP_DIR/instance-${instance}.yaml"
  done

  # --- Backup: Images ---
  for image in $(incus image list --format csv -c f); do
    incus image show "$image" > "$BACKUP_DIR/image-${image}.yaml"
  done

  # --- Backup: Netzwerke ---
  for net in $(incus network list -c n --format csv); do
    incus network show "$net" > "$BACKUP_DIR/network-${net}.yaml"
  done

  # --- Backup: Storage Pools & Custom Volumes ---
  for pool in $(incus storage list -c n --format csv); do
    incus storage show "$pool" > "$BACKUP_DIR/storage-pool-${pool}.yaml"
    for volume in $(incus storage volume list "$pool" --format csv -c n type=custom); do
      incus storage volume show "$pool" "$volume" > "$BACKUP_DIR/storage-volume-${pool}_${volume}.yaml"
    done
  done

  echo "Backup Projekt '$project' abgeschlossen"
done

# subuid
cp /etc/subuid $SUB_BACKUP_DIR/
cp /etc/subgid $SUB_BACKUP_DIR/

cd "$BASE_BACKUP_DIR"
if [[ $COMPRESS == "yes" ]];then
  # Archivieren & Zwischenordner löschen
  ARCHIV_NAME="$(basename "$SUB_BACKUP_DIR").tar.gz"
  tar -czf "$ARCHIV_NAME" "$(basename "$SUB_BACKUP_DIR")"
  rm -rf "$SUB_BACKUP_DIR"
fi
echo "Alle Projekt-Backups abgeschlossen."

# Purge
echo "Purge older backups based on \$KEEP: $KEEP"
ls -1t $BASE_BACKUP_DIR 2>/dev/null | tail -n +$((1 + $KEEP)) | xargs -r rm -rf --
