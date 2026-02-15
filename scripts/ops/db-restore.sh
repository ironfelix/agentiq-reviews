#!/bin/bash
set -euo pipefail

# AgentIQ PostgreSQL Restore Script
# Usage: ./db-restore.sh <backup_file> [--yes]

# Configuration
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-agentiq}"
PGDATABASE="${PGDATABASE:-agentiq_chat}"

# Parse arguments
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <backup_file> [--yes]"
    echo ""
    echo "Arguments:"
    echo "  backup_file    Path to backup file (.sql.gz or .sql)"
    echo "  --yes          Skip confirmation prompt"
    echo ""
    echo "Example:"
    echo "  $0 /var/backups/agentiq/agentiq_chat_2026-02-15_030000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"
SKIP_CONFIRMATION=false

if [[ "${2:-}" == "--yes" ]]; then
    SKIP_CONFIRMATION=true
fi

# Validate backup file
if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

if [[ ! -r "$BACKUP_FILE" ]]; then
    echo "ERROR: Cannot read backup file: ${BACKUP_FILE}"
    exit 1
fi

# Check file extension
if [[ ! "$BACKUP_FILE" =~ \.(sql|sql\.gz)$ ]]; then
    echo "ERROR: Backup file must have .sql or .sql.gz extension"
    exit 1
fi

# Display backup information
echo "========================================="
echo "AgentIQ Database Restore"
echo "========================================="
echo "Backup file:  ${BACKUP_FILE}"
echo "File size:    $(du -h "$BACKUP_FILE" | cut -f1)"
echo "Modified:     $(stat -c '%y' "$BACKUP_FILE" 2>/dev/null || stat -f '%Sm' "$BACKUP_FILE")"
echo ""
echo "Target database:"
echo "  Host:       ${PGHOST}"
echo "  Port:       ${PGPORT}"
echo "  Database:   ${PGDATABASE}"
echo "  User:       ${PGUSER}"
echo "========================================="
echo ""

# Check PostgreSQL connection
echo "Checking database connection..."
if ! PGPASSWORD="${PGPASSWORD:-}" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c '\q' 2>/dev/null; then
    echo "ERROR: Cannot connect to PostgreSQL database"
    exit 1
fi
echo "Connection successful."
echo ""

# Confirmation prompt
if ! $SKIP_CONFIRMATION; then
    echo "WARNING: This will overwrite the current database!"
    echo "All existing data in '${PGDATABASE}' will be replaced."
    echo ""
    read -p "Do you want to continue? (yes/no): " -r
    echo ""
    if [[ ! "$REPLY" =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Restore cancelled."
        exit 0
    fi
fi

# Perform restore
echo "Starting database restore..."
echo ""

if [[ "$BACKUP_FILE" =~ \.gz$ ]]; then
    # Compressed backup
    echo "Decompressing and restoring..."
    if gunzip -c "$BACKUP_FILE" | PGPASSWORD="${PGPASSWORD:-}" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 2>&1; then
        echo ""
        echo "========================================="
        echo "Restore completed successfully!"
        echo "========================================="
        exit 0
    else
        echo ""
        echo "ERROR: Restore failed"
        exit 1
    fi
else
    # Uncompressed backup
    echo "Restoring from uncompressed file..."
    if PGPASSWORD="${PGPASSWORD:-}" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -v ON_ERROR_STOP=1 -f "$BACKUP_FILE" 2>&1; then
        echo ""
        echo "========================================="
        echo "Restore completed successfully!"
        echo "========================================="
        exit 0
    else
        echo ""
        echo "ERROR: Restore failed"
        exit 1
    fi
fi
