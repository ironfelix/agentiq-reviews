#!/bin/bash
set -euo pipefail

# AgentIQ PostgreSQL Backup Script
# Usage: ./db-backup.sh [--weekly]

# Configuration
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-agentiq}"
PGDATABASE="${PGDATABASE:-agentiq_chat}"

BACKUP_DIR="/var/backups/agentiq"
LOG_FILE="/var/log/agentiq/backup.log"
RETENTION_DAYS=30

# Parse arguments
WEEKLY_BACKUP=false
if [[ "${1:-}" == "--weekly" ]]; then
    WEEKLY_BACKUP=true
fi

# Ensure directories exist
mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Error handler
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Generate backup filename
TIMESTAMP=$(date '+%Y-%m-%d_%H%M%S')
if $WEEKLY_BACKUP; then
    BACKUP_FILE="${BACKUP_DIR}/agentiq_chat_weekly_${TIMESTAMP}.sql.gz"
else
    BACKUP_FILE="${BACKUP_DIR}/agentiq_chat_${TIMESTAMP}.sql.gz"
fi

log "Starting PostgreSQL backup: ${BACKUP_FILE}"

# Check PostgreSQL connection
if ! PGPASSWORD="${PGPASSWORD:-}" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c '\q' 2>/dev/null; then
    error_exit "Cannot connect to PostgreSQL database"
fi

# Perform backup
log "Creating database dump..."
PG_DUMP_OPTIONS=""
if $WEEKLY_BACKUP; then
    # Full backup with clean and if-exists options
    PG_DUMP_OPTIONS="--clean --if-exists --create"
    log "Weekly full backup mode enabled"
fi

if PGPASSWORD="${PGPASSWORD:-}" pg_dump \
    -h "$PGHOST" \
    -p "$PGPORT" \
    -U "$PGUSER" \
    -d "$PGDATABASE" \
    $PG_DUMP_OPTIONS \
    -F p \
    | gzip > "$BACKUP_FILE"; then

    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup completed successfully: ${BACKUP_FILE} (${BACKUP_SIZE})"
else
    error_exit "pg_dump failed"
fi

# Verify backup file
if [[ ! -f "$BACKUP_FILE" ]]; then
    error_exit "Backup file not created"
fi

if [[ ! -s "$BACKUP_FILE" ]]; then
    error_exit "Backup file is empty"
fi

# Rotate old backups
log "Rotating backups older than ${RETENTION_DAYS} days..."
DELETED_COUNT=0

while IFS= read -r old_backup; do
    if [[ -f "$old_backup" ]]; then
        rm -f "$old_backup"
        log "Deleted old backup: $(basename "$old_backup")"
        ((DELETED_COUNT++))
    fi
done < <(find "$BACKUP_DIR" -name "agentiq_chat_*.sql.gz" -type f -mtime "+${RETENTION_DAYS}")

if [[ $DELETED_COUNT -gt 0 ]]; then
    log "Deleted ${DELETED_COUNT} old backup(s)"
else
    log "No old backups to delete"
fi

# Summary
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "agentiq_chat_*.sql.gz" -type f | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "Backup completed. Total backups: ${TOTAL_BACKUPS}, Total size: ${TOTAL_SIZE}"

exit 0
