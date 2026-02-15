# AgentIQ PostgreSQL Backup System

## Overview

Automated backup system for the `agentiq_chat` PostgreSQL database with daily incremental backups, weekly full backups, and 30-day retention.

## Components

- **db-backup.sh** - Main backup script with compression and rotation
- **db-backup-cron.conf** - Cron configuration for automated backups
- **db-restore.sh** - Interactive restore script with validation

## Server Setup

### 1. Initial Configuration

```bash
# On VPS (ubuntu@79.137.175.164)
cd /opt/agentiq

# Create backup directories
sudo mkdir -p /var/backups/agentiq
sudo mkdir -p /var/log/agentiq
sudo chown ubuntu:ubuntu /var/backups/agentiq
sudo chown ubuntu:ubuntu /var/log/agentiq

# Make scripts executable
chmod +x scripts/ops/db-backup.sh
chmod +x scripts/ops/db-restore.sh
```

### 2. PostgreSQL Authentication

Choose one method:

#### Option A: .pgpass file (recommended)

```bash
# Create .pgpass file in ubuntu user's home directory
echo "localhost:5432:agentiq_chat:agentiq:YOUR_PASSWORD" > ~/.pgpass
chmod 600 ~/.pgpass
```

#### Option B: Environment variable

```bash
# Add to /etc/environment or cron configuration
export PGPASSWORD="YOUR_PASSWORD"
```

### 3. Install Cron Jobs

```bash
# Copy cron configuration
sudo cp scripts/ops/db-backup-cron.conf /etc/cron.d/agentiq-backup

# Ensure proper permissions
sudo chmod 644 /etc/cron.d/agentiq-backup

# Restart cron service
sudo systemctl restart cron

# Verify cron is running
sudo systemctl status cron
```

### 4. Verify Installation

```bash
# Test backup script manually
./scripts/ops/db-backup.sh

# Check log file
tail -f /var/log/agentiq/backup.log

# List backups
ls -lh /var/backups/agentiq/
```

## Backup Schedule

| Type | Frequency | Time (UTC) | Options |
|------|-----------|------------|---------|
| Daily | Every day | 03:00 | Standard dump |
| Weekly | Sunday | 02:00 | Full dump with --clean --if-exists |

## Backup Retention

- Backups older than **30 days** are automatically deleted
- Retention is checked on every backup run
- Weekly full backups are kept for the same 30-day period

## Backup File Format

```
agentiq_chat_YYYY-MM-DD_HHMMSS.sql.gz        # Daily backup
agentiq_chat_weekly_YYYY-MM-DD_HHMMSS.sql.gz # Weekly backup
```

Example:
```
agentiq_chat_2026-02-15_030000.sql.gz
agentiq_chat_weekly_2026-02-16_020000.sql.gz
```

## Manual Operations

### Create Manual Backup

```bash
# Standard backup
./scripts/ops/db-backup.sh

# Weekly full backup
./scripts/ops/db-backup.sh --weekly
```

### List All Backups

```bash
ls -lth /var/backups/agentiq/

# With sizes
du -h /var/backups/agentiq/*
```

### Restore from Backup

```bash
# Interactive restore (with confirmation)
./scripts/ops/db-restore.sh /var/backups/agentiq/agentiq_chat_2026-02-15_030000.sql.gz

# Non-interactive restore (skip confirmation)
./scripts/ops/db-restore.sh /var/backups/agentiq/agentiq_chat_2026-02-15_030000.sql.gz --yes
```

### Test Backup Integrity

```bash
# Verify gzip file is not corrupted
gunzip -t /var/backups/agentiq/agentiq_chat_2026-02-15_030000.sql.gz

# View backup contents (first 50 lines)
gunzip -c /var/backups/agentiq/agentiq_chat_2026-02-15_030000.sql.gz | head -n 50
```

### Manual Cleanup

```bash
# Delete backups older than 30 days
find /var/backups/agentiq -name "agentiq_chat_*.sql.gz" -type f -mtime +30 -delete

# Delete specific backup
rm /var/backups/agentiq/agentiq_chat_2026-02-15_030000.sql.gz
```

## Monitoring

### Check Backup Logs

```bash
# View recent logs
tail -n 100 /var/log/agentiq/backup.log

# Follow logs in real-time
tail -f /var/log/agentiq/backup.log

# Search for errors
grep ERROR /var/log/agentiq/backup.log
```

### Verify Cron Execution

```bash
# Check cron logs (Ubuntu/Debian)
grep CRON /var/log/syslog | grep agentiq

# List cron jobs
sudo crontab -l -u root
```

### Backup Statistics

```bash
# Count total backups
find /var/backups/agentiq -name "agentiq_chat_*.sql.gz" -type f | wc -l

# Total disk usage
du -sh /var/backups/agentiq

# Backup sizes over time
ls -lth /var/backups/agentiq/ | head -n 20
```

## Troubleshooting

### Backup Script Fails

1. Check PostgreSQL connection:
   ```bash
   psql -h localhost -U agentiq -d agentiq_chat -c '\q'
   ```

2. Verify .pgpass file:
   ```bash
   ls -la ~/.pgpass
   cat ~/.pgpass
   ```

3. Check permissions:
   ```bash
   ls -ld /var/backups/agentiq
   ls -ld /var/log/agentiq
   ```

4. Run backup manually to see errors:
   ```bash
   ./scripts/ops/db-backup.sh
   ```

### Restore Fails

1. Verify backup file integrity:
   ```bash
   gunzip -t /path/to/backup.sql.gz
   ```

2. Check available disk space:
   ```bash
   df -h
   ```

3. Ensure database exists:
   ```bash
   psql -h localhost -U agentiq -l
   ```

### Cron Not Running

1. Check cron service:
   ```bash
   sudo systemctl status cron
   sudo systemctl restart cron
   ```

2. Verify cron file syntax:
   ```bash
   cat /etc/cron.d/agentiq-backup
   ```

3. Check system logs:
   ```bash
   sudo journalctl -u cron -n 50
   ```

## Environment Variables

All scripts support the following environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| PGHOST | localhost | PostgreSQL host |
| PGPORT | 5432 | PostgreSQL port |
| PGUSER | agentiq | PostgreSQL user |
| PGDATABASE | agentiq_chat | Database name |
| PGPASSWORD | (none) | Database password (use .pgpass instead) |

## Security Considerations

1. **Never commit .pgpass files** to version control
2. **Set proper permissions** on .pgpass (600) and backup directory (700)
3. **Rotate passwords** and update .pgpass accordingly
4. **Monitor backup logs** for unauthorized access attempts
5. **Test restores regularly** to ensure backup integrity
6. **Consider encryption** for backups containing sensitive data

## Disaster Recovery

### Complete System Restore

1. Install PostgreSQL on new server
2. Create database and user:
   ```bash
   sudo -u postgres psql
   CREATE DATABASE agentiq_chat;
   CREATE USER agentiq WITH PASSWORD 'password';
   GRANT ALL PRIVILEGES ON DATABASE agentiq_chat TO agentiq;
   ```

3. Restore from weekly full backup:
   ```bash
   ./scripts/ops/db-restore.sh /path/to/weekly_backup.sql.gz --yes
   ```

4. Verify data integrity:
   ```bash
   psql -h localhost -U agentiq -d agentiq_chat -c "SELECT COUNT(*) FROM conversations;"
   ```

## Local Development

For local testing on macOS/Linux:

```bash
# Set custom backup location
export BACKUP_DIR="/tmp/agentiq-backups"
export LOG_FILE="/tmp/agentiq-backup.log"

# Run backup
./scripts/ops/db-backup.sh

# Restore to local database
./scripts/ops/db-restore.sh /tmp/agentiq-backups/agentiq_chat_*.sql.gz
```

## Support

For issues or questions:
1. Check logs: `/var/log/agentiq/backup.log`
2. Verify script permissions and PostgreSQL connectivity
3. Review this documentation

## Changelog

- **2026-02-15**: Initial backup system implementation
  - Daily backups at 03:00 UTC
  - Weekly full backups on Sunday 02:00 UTC
  - 30-day retention policy
  - Automated rotation
  - Comprehensive logging
