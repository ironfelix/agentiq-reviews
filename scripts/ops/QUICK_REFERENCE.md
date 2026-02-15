# SSL Auto-Renewal Quick Reference

Быстрая справка по командам SSL мониторинга и автопродления.

## SSH Connection

```bash
# Connect to VPS
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164
```

## Certbot Commands

```bash
# Get new certificate
sudo certbot --nginx -d agentiq.ru -d www.agentiq.ru

# List all certificates
sudo certbot certificates

# Renew all certificates (automatic, only if < 30 days to expiry)
sudo certbot renew

# Force renewal (for testing)
sudo certbot renew --force-renewal

# Dry-run test (simulation, no changes)
sudo certbot renew --dry-run

# Delete certificate
sudo certbot delete --cert-name agentiq.ru

# Expand certificate (add new domain)
sudo certbot --nginx -d agentiq.ru -d www.agentiq.ru -d api.agentiq.ru --expand
```

## SSL Check Script

```bash
# Basic check (default: agentiq.ru, threshold 14 days)
sudo /opt/agentiq/scripts/ops/ssl-check.sh

# Custom domain
sudo /opt/agentiq/scripts/ops/ssl-check.sh example.com

# Custom threshold (30 days)
sudo /opt/agentiq/scripts/ops/ssl-check.sh agentiq.ru 30

# With webhook alert
ALERT_WEBHOOK="https://hooks.slack.com/..." sudo /opt/agentiq/scripts/ops/ssl-check.sh
```

## Systemd Timer (Certbot)

```bash
# List all timers
sudo systemctl list-timers

# List certbot timer specifically
sudo systemctl list-timers | grep certbot

# Check timer status
sudo systemctl status certbot.timer

# Check service status
sudo systemctl status certbot.service

# View logs
sudo journalctl -u certbot.timer
sudo journalctl -u certbot.service -n 50
```

## Cron (if using custom crontab)

```bash
# List cron jobs
sudo crontab -l

# Edit cron
sudo crontab -e

# List cron files
ls -la /etc/cron.d/

# View our cron config
sudo cat /etc/cron.d/agentiq-ssl-renew

# Cron logs
sudo grep CRON /var/log/syslog | tail -20
sudo tail -f /var/log/syslog | grep CRON
```

## Nginx Commands

```bash
# Test config
sudo nginx -t

# Reload (graceful, no downtime)
sudo systemctl reload nginx

# Restart (hard restart, brief downtime)
sudo systemctl restart nginx

# Status
sudo systemctl status nginx

# Logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## Certificate Files

```bash
# View certificate info
sudo openssl x509 -in /etc/letsencrypt/live/agentiq.ru/fullchain.pem -text -noout

# Check expiry date
sudo openssl x509 -in /etc/letsencrypt/live/agentiq.ru/fullchain.pem -noout -dates

# Certificate chain
ls -la /etc/letsencrypt/live/agentiq.ru/
# fullchain.pem  — Certificate + chain
# privkey.pem    — Private key
# cert.pem       — Certificate only
# chain.pem      — Chain only
```

## Testing SSL

```bash
# From server
curl -I https://agentiq.ru

# Test SSL connection
openssl s_client -connect agentiq.ru:443 -servername agentiq.ru

# Check certificate expiry
echo | openssl s_client -servername agentiq.ru -connect agentiq.ru:443 2>/dev/null | openssl x509 -noout -dates

# Test redirect (80 → 443)
curl -I http://agentiq.ru
```

## Logs

```bash
# Certbot logs
sudo tail -50 /var/log/letsencrypt/letsencrypt.log
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# Nginx logs
sudo tail -50 /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Systemd logs
sudo journalctl -u certbot.service -n 50 --no-pager
sudo journalctl -u nginx -n 50 --no-pager

# Cron logs
sudo grep certbot /var/log/syslog | tail -20
```

## File Locations

```bash
# Certificates
/etc/letsencrypt/live/agentiq.ru/

# Certbot config
/etc/letsencrypt/renewal/agentiq.ru.conf

# nginx config
/etc/nginx/sites-available/agentiq
/etc/nginx/sites-enabled/agentiq

# SSL check script
/opt/agentiq/scripts/ops/ssl-check.sh

# Cron config
/etc/cron.d/agentiq-ssl-renew

# Logs
/var/log/letsencrypt/letsencrypt.log
/var/log/nginx/error.log
/var/log/nginx/access.log
```

## Troubleshooting

```bash
# Port 443 listening?
sudo netstat -tlnp | grep :443
sudo lsof -i :443

# Port 80 listening?
sudo netstat -tlnp | grep :80

# DNS check
dig agentiq.ru +short
nslookup agentiq.ru

# Firewall status
sudo ufw status
sudo iptables -L -n

# Test domain accessibility
ping agentiq.ru
curl -I http://agentiq.ru
telnet agentiq.ru 443
```

## Deployment

```bash
# Upload ssl-check.sh from local machine
cd /Users/ivanilin/Documents/ivanilin/agentiq
scp -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem \
    scripts/ops/ssl-check.sh \
    ubuntu@79.137.175.164:/tmp/

# Install on server
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164
sudo mkdir -p /opt/agentiq/scripts/ops
sudo cp /tmp/ssl-check.sh /opt/agentiq/scripts/ops/
sudo chmod +x /opt/agentiq/scripts/ops/ssl-check.sh
```

## Exit Codes

```bash
# ssl-check.sh exit codes:
# 0 — Certificate valid (> threshold days)
# 1 — Certificate expiring soon (< threshold days)
# 2 — Certificate expired

# Check last command exit code
echo $?
```

## Rate Limits (Let's Encrypt)

- **50** certificates per registered domain per week
- **5** duplicate certificates per week
- **300** new orders per account per 3 hours
- **10** accounts per IP per 3 hours
- **500** accounts per IP range per 3 hours

More: https://letsencrypt.org/docs/rate-limits/

## Emergency Procedures

### Certificate Expired
```bash
# 1. Force renewal
sudo certbot renew --force-renewal

# 2. Reload nginx
sudo systemctl reload nginx

# 3. Verify
curl -I https://agentiq.ru
```

### Renewal Failed
```bash
# 1. Check logs
sudo tail -100 /var/log/letsencrypt/letsencrypt.log

# 2. Test nginx config
sudo nginx -t

# 3. Check ports
sudo netstat -tlnp | grep -E '(:80|:443)'

# 4. Check DNS
dig agentiq.ru +short

# 5. Manual renewal with verbose output
sudo certbot renew --force-renewal -v
```

### nginx Won't Start
```bash
# 1. Check config
sudo nginx -t

# 2. Check logs
sudo tail -50 /var/log/nginx/error.log

# 3. Check if port in use
sudo lsof -i :443

# 4. Restart nginx
sudo systemctl restart nginx
```

## Monitoring URLs

- **SSL Labs Test**: https://www.ssllabs.com/ssltest/analyze.html?d=agentiq.ru
- **Let's Encrypt Status**: https://letsencrypt.status.io/
- **Certificate Transparency**: https://crt.sh/?q=agentiq.ru

## Useful Aliases (add to ~/.bashrc)

```bash
alias ssl-check='sudo /opt/agentiq/scripts/ops/ssl-check.sh'
alias certbot-list='sudo certbot certificates'
alias certbot-renew='sudo certbot renew --dry-run'
alias nginx-reload='sudo nginx -t && sudo systemctl reload nginx'
alias nginx-logs='sudo tail -f /var/log/nginx/error.log'
```

## Contact Information

- **VPS IP**: 79.137.175.164
- **Domain**: agentiq.ru
- **SSH Key**: ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem
- **Certbot Support**: https://community.letsencrypt.org/
- **nginx Support**: https://forum.nginx.org/

---

**Last Updated**: 2026-02-15
**Version**: 1.0
**Maintainer**: AgentIQ DevOps Team
