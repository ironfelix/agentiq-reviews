# Operations Scripts

Операционные скрипты для обслуживания AgentIQ VPS.

## Структура

```
scripts/ops/
├── README.md                      # Этот файл — обзор всех ops инструментов
│
├── SSL Certificate Management
│   ├── ssl-check.sh               # Проверка состояния SSL сертификата
│   ├── ssl-renew-cron.conf        # Crontab для автопродления SSL
│   ├── README-ssl.md              # Документация SSL мониторинга
│   ├── DEPLOYMENT_CHECKLIST.md    # Чеклист развёртывания SSL
│   ├── QUICK_REFERENCE.md         # Быстрая справка команд SSL
│   └── TESTING.md                 # Руководство по тестированию
│
├── Database Backups
│   ├── db-backup.sh               # Бэкап PostgreSQL базы
│   ├── db-restore.sh              # Восстановление из бэкапа
│   ├── db-backup-cron.conf        # Crontab для автоматических бэкапов
│   └── README-backups.md          # Документация бэкапов
│
└── Service Monitoring
    └── celery-check.sh            # Мониторинг Celery worker/beat
```

## Quick Start

### SSL Monitoring
```bash
# Проверить SSL сертификат
./ssl-check.sh agentiq.ru 14

# Установить на сервере
scp -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem \
    ssl-check.sh ubuntu@79.137.175.164:/tmp/
ssh ubuntu@79.137.175.164
sudo mkdir -p /opt/agentiq/scripts/ops
sudo cp /tmp/ssl-check.sh /opt/agentiq/scripts/ops/
sudo chmod +x /opt/agentiq/scripts/ops/ssl-check.sh

# Документация
# README-ssl.md — полная инструкция по настройке SSL
# DEPLOYMENT_CHECKLIST.md — пошаговый чеклист
# QUICK_REFERENCE.md — быстрая справка команд
```

### Database Backups
```bash
# Создать бэкап
./db-backup.sh

# Восстановить из бэкапа
./db-restore.sh /path/to/backup.sql.gz

# Документация
# README-backups.md — инструкция по бэкапам
```

### Celery Monitoring
```bash
# Проверить состояние Celery
./celery-check.sh
```

## VPS Information

- **IP**: 79.137.175.164
- **Domain**: agentiq.ru
- **SSH Key**: `~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem`
- **OS**: Ubuntu 20.04 LTS
- **User**: ubuntu (sudo access)

### Services

| Service | Description | Port | Status Command |
|---------|-------------|------|----------------|
| nginx | Web server | 80, 443 | `sudo systemctl status nginx` |
| agentiq-chat | FastAPI backend | 8001 | `sudo systemctl status agentiq-chat` |
| agentiq-celery | Celery worker | - | `sudo systemctl status agentiq-celery` |
| agentiq-celery-beat | Celery scheduler | - | `sudo systemctl status agentiq-celery-beat` |
| postgresql | Database | 5432 | `sudo systemctl status postgresql` |
| redis | Cache/broker | 6379 | `sudo systemctl status redis` |

### File Paths

| Path | Description |
|------|-------------|
| `/var/www/agentiq/` | Frontend static files |
| `/opt/agentiq/` | Backend code |
| `/etc/nginx/sites-available/agentiq` | nginx config |
| `/etc/letsencrypt/live/agentiq.ru/` | SSL certificates |
| `/etc/cron.d/agentiq-*` | Cron jobs |
| `/var/log/letsencrypt/` | Certbot logs |
| `/var/log/nginx/` | nginx logs |

## Common Tasks

### SSH Access
```bash
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164
```

### Upload Files
```bash
scp -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem \
    local_file.sh \
    ubuntu@79.137.175.164:/tmp/
```

### Service Management
```bash
# Status
sudo systemctl status agentiq-chat

# Restart
sudo systemctl restart agentiq-chat

# Logs
sudo journalctl -u agentiq-chat -f
```

### SSL Management
```bash
# Check certificate
sudo certbot certificates

# Renew (dry-run)
sudo certbot renew --dry-run

# Renew (force)
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

### Database Management
```bash
# Connect to DB
sudo -u postgres psql -d agentiq_chat

# Backup
/opt/agentiq/scripts/ops/db-backup.sh

# Restore
/opt/agentiq/scripts/ops/db-restore.sh backup.sql.gz
```

### Logs Monitoring
```bash
# nginx
sudo tail -f /var/log/nginx/error.log

# Backend
sudo journalctl -u agentiq-chat -f

# Celery
sudo journalctl -u agentiq-celery -f

# Certbot
sudo tail -f /var/log/letsencrypt/letsencrypt.log
```

## Automation Schedule

### Daily
- **6:00 AM** — SSL certificate check (`ssl-check.sh`)
- **3:15 AM, 3:15 PM** — SSL renewal attempt (`certbot renew`)
- **2:00 AM** — Database backup (`db-backup.sh`)

### Weekly
- **Monday 7:00 AM** — Certbot dry-run test

### On-Demand
- Celery health check (`celery-check.sh`)
- Manual backups (`db-backup.sh`)
- Service restarts

## Monitoring

### Health Checks
```bash
# Site up?
curl -I https://agentiq.ru

# API up?
curl https://agentiq.ru/api/health

# SSL valid?
/opt/agentiq/scripts/ops/ssl-check.sh

# Services running?
sudo systemctl status agentiq-chat agentiq-celery agentiq-celery-beat
```

### Metrics
- SSL certificate days until expiry
- Database backup age
- Celery queue length
- nginx response times
- Disk space usage

## Security

### Best Practices
- All scripts run as root (via sudo)
- SSH key-based authentication only
- Firewall configured (ufw)
- SSL/TLS enabled (Let's Encrypt)
- Database backups encrypted (optional)
- Secrets in environment variables

### Permissions
```bash
# Scripts in /opt/agentiq/scripts/ops/
# Owner: root:root
# Permissions: 755 (rwxr-xr-x)

# Crontab files in /etc/cron.d/
# Owner: root:root
# Permissions: 644 (rw-r--r--)

# SSL certificates
# Owner: root:root
# Permissions: 600 (privkey.pem), 644 (fullchain.pem)
```

## Troubleshooting

### Common Issues

#### SSL Certificate Not Renewing
1. Check certbot logs: `sudo tail -100 /var/log/letsencrypt/letsencrypt.log`
2. Test renewal: `sudo certbot renew --dry-run`
3. Check nginx config: `sudo nginx -t`
4. Check ports: `sudo netstat -tlnp | grep -E '(:80|:443)'`
5. Check DNS: `dig agentiq.ru +short`

#### Service Not Starting
1. Check logs: `sudo journalctl -u SERVICE_NAME -n 50`
2. Check config: `sudo systemctl cat SERVICE_NAME`
3. Check dependencies: `sudo systemctl list-dependencies SERVICE_NAME`
4. Restart: `sudo systemctl restart SERVICE_NAME`

#### Database Backup Failed
1. Check disk space: `df -h`
2. Check PostgreSQL: `sudo systemctl status postgresql`
3. Check logs: `sudo journalctl -u postgresql -n 50`
4. Manual backup: `sudo -u postgres pg_dump agentiq_chat > test.sql`

#### Out of Disk Space
1. Check usage: `df -h`
2. Clean old backups: `sudo find /opt/agentiq/backups/ -type f -mtime +30 -delete`
3. Clean logs: `sudo journalctl --vacuum-time=7d`
4. Clean apt cache: `sudo apt clean`

## Documentation

### Detailed Guides
- **SSL**: `README-ssl.md` — SSL certificate management
- **Backups**: `README-backups.md` — Database backup/restore
- **Testing**: `TESTING.md` — Testing procedures
- **Quick Ref**: `QUICK_REFERENCE.md` — Command cheatsheet
- **Deployment**: `DEPLOYMENT_CHECKLIST.md` — SSL deployment steps

### External Resources
- [Let's Encrypt Docs](https://letsencrypt.org/docs/)
- [nginx Docs](https://nginx.org/en/docs/)
- [Celery Docs](https://docs.celeryproject.org/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)

## Contributing

При добавлении новых ops скриптов:

1. Следовать naming convention: `feature-action.sh`
2. Добавить executable права: `chmod +x script.sh`
3. Добавить shebang: `#!/usr/bin/env bash`
4. Использовать `set -euo pipefail` для safety
5. Добавить usage comments в начале файла
6. Создать соответствующую документацию (README-*.md)
7. Добавить unit тесты (если применимо)
8. Обновить этот README.md

### Script Template
```bash
#!/usr/bin/env bash
# Script Name — Short description
# Usage: ./script-name.sh [args]

set -euo pipefail

# Configuration
VAR="${1:-default_value}"

# Logging functions
log_info() { echo "[INFO] $1"; }
log_warn() { echo "[WARN] $1"; }
log_error() { echo "[ERROR] $1"; }

# Main logic
main() {
    log_info "Starting..."
    # Your code here
}

# Run
main "$@"
```

## Support

Для вопросов и проблем:

1. Проверить логи (см. секцию "Logs Monitoring")
2. Прочитать соответствующую документацию (README-*.md)
3. Проверить "Troubleshooting" секцию
4. Проверить external resources (Let's Encrypt, nginx docs, etc.)

## Version History

- **1.0** (2026-02-15) — Initial ops scripts
  - SSL certificate monitoring (`ssl-check.sh`)
  - Database backups (`db-backup.sh`, `db-restore.sh`)
  - Celery monitoring (`celery-check.sh`)
  - Comprehensive documentation

---

**Last Updated**: 2026-02-15
**Maintainer**: AgentIQ DevOps Team
**Repository**: `/Users/ivanilin/Documents/ivanilin/agentiq/scripts/ops/`
