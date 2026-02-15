# SSL Certificate Auto-Renewal & Monitoring

Автоматическое продление SSL сертификатов Let's Encrypt и мониторинг их состояния.

## Компоненты

### 1. `ssl-check.sh` — Проверка состояния сертификата
Скрипт проверяет дату истечения SSL сертификата и алертит если осталось < 14 дней.

**Использование:**
```bash
./ssl-check.sh [domain] [alert_threshold_days]

# Примеры
./ssl-check.sh                    # Проверка agentiq.ru (по умолчанию)
./ssl-check.sh agentiq.ru 7       # Алерт если < 7 дней
```

**Exit codes:**
- `0` — сертификат валиден, до истечения > threshold
- `1` — сертификат истекает скоро (< threshold дней)
- `2` — сертификат уже истёк

**Webhook alerts (опционально):**
```bash
export ALERT_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
./ssl-check.sh
```

### 2. `ssl-renew-cron.conf` — Crontab для автопродления
Crontab entry для автоматического продления сертификатов Let's Encrypt.

**Расписание:**
- **Продление:** 2 раза в день (3:15 AM, 3:15 PM) — стандарт Let's Encrypt
- **Проверка:** ежедневно в 6:00 AM
- **Dry-run тест:** каждый понедельник в 7:00 AM

## Установка на сервере

### 1. Первичная настройка SSL (разово)

```bash
# Подключиться к VPS
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164

# Установить certbot
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# Получить сертификат (интерактивно)
sudo certbot --nginx -d agentiq.ru -d www.agentiq.ru

# Проверить что автопродление работает (dry-run)
sudo certbot renew --dry-run
```

Certbot автоматически:
- Создаст сертификаты в `/etc/letsencrypt/live/agentiq.ru/`
- Обновит nginx конфиг (добавит SSL блок + redirect 80→443)
- Настроит автопродление через systemd timer (альтернатива cron)

### 2. Установка скриптов мониторинга

```bash
# На локальной машине — загрузить скрипты на сервер
cd /Users/ivanilin/Documents/ivanilin/agentiq
scp -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem \
    scripts/ops/ssl-check.sh \
    ubuntu@79.137.175.164:/tmp/

# На сервере — установить скрипт
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164
sudo mkdir -p /opt/agentiq/scripts/ops
sudo cp /tmp/ssl-check.sh /opt/agentiq/scripts/ops/
sudo chmod +x /opt/agentiq/scripts/ops/ssl-check.sh
sudo chown root:root /opt/agentiq/scripts/ops/ssl-check.sh

# Тестовый запуск
sudo /opt/agentiq/scripts/ops/ssl-check.sh agentiq.ru
```

### 3. Настройка cron (опционально)

> **Важно:** Certbot уже настраивает автопродление через systemd timer (`certbot.timer`).
> Cron нужен только если хотите кастомное расписание или дополнительный мониторинг.

```bash
# На локальной машине — загрузить crontab config
scp -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem \
    scripts/ops/ssl-renew-cron.conf \
    ubuntu@79.137.175.164:/tmp/

# На сервере — установить crontab
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164
sudo cp /tmp/ssl-renew-cron.conf /etc/cron.d/agentiq-ssl-renew
sudo chmod 644 /etc/cron.d/agentiq-ssl-renew
sudo chown root:root /etc/cron.d/agentiq-ssl-renew

# Настроить email для алертов (опционально)
# Отредактируйте MAILTO в /etc/cron.d/agentiq-ssl-renew
sudo nano /etc/cron.d/agentiq-ssl-renew
```

### 4. Проверка автопродления

```bash
# Проверить systemd timer (стандартный метод certbot)
sudo systemctl list-timers | grep certbot
# Должно быть: certbot.timer — следующий запуск через ~12 часов

# Проверить cron (если установили кастомный)
sudo ls -la /etc/cron.d/agentiq-ssl-renew

# Тест dry-run (симуляция продления без изменений)
sudo certbot renew --dry-run
# Успешный output: "Congratulations, all simulated renewals succeeded"

# Ручное продление (форсированное, для теста)
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

## Мониторинг и диагностика

### Логи
```bash
# Логи certbot
sudo tail -f /var/log/letsencrypt/letsencrypt.log

# Логи cron (если используете cron вместо systemd)
sudo grep -i certbot /var/log/syslog

# Логи systemd timer
sudo journalctl -u certbot.timer
sudo journalctl -u certbot.service
```

### Ручная проверка состояния сертификата
```bash
# Локально через скрипт
/opt/agentiq/scripts/ops/ssl-check.sh agentiq.ru

# Через openssl напрямую
echo | openssl s_client -servername agentiq.ru -connect agentiq.ru:443 2>/dev/null | openssl x509 -noout -dates

# Проверка из браузера
# https://agentiq.ru → DevTools → Security → Certificate
```

### Что делать если продление не сработало

1. **Проверить nginx конфиг:**
```bash
sudo nginx -t
sudo systemctl status nginx
```

2. **Проверить доступность домена:**
```bash
curl -I https://agentiq.ru
dig agentiq.ru +short
```

3. **Проверить certbot конфиг:**
```bash
sudo certbot certificates
# Должно показать домены и даты истечения
```

4. **Ручное продление:**
```bash
sudo certbot renew --force-renewal --nginx
sudo systemctl reload nginx
```

5. **Если домен не отвечает (DNS issue):**
```bash
# Проверить A-record
dig agentiq.ru A +short
# Должен быть 79.137.175.164

# Проверить firewall
sudo ufw status
# Порты 80 и 443 должны быть открыты
```

## Webhook интеграция (опционально)

Для отправки алертов в Slack/Discord/Telegram:

### Slack
```bash
# Создать Incoming Webhook в Slack: https://api.slack.com/messaging/webhooks
# Добавить в crontab environment
sudo nano /etc/cron.d/agentiq-ssl-renew

# Добавить строку (перед задачами):
ALERT_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Telegram
```bash
# Создать бота через @BotFather
# Получить chat_id через https://api.telegram.org/botTOKEN/getUpdates
# Webhook URL формат:
ALERT_WEBHOOK=https://api.telegram.org/botTOKEN/sendMessage?chat_id=CHAT_ID&text=
```

## Безопасность

- Все скрипты в `/opt/agentiq/scripts/ops/` должны быть `root:root` с правами `755`
- Crontab файлы в `/etc/cron.d/` должны быть `root:root` с правами `644`
- Сертификаты Let's Encrypt хранятся в `/etc/letsencrypt/` с ограниченным доступом (только root)
- Приватные ключи (`privkey.pem`) должны иметь права `600`

## Troubleshooting

### Ошибка: "Failed to retrieve certificate"
```bash
# Проверить что домен доступен
curl -I https://agentiq.ru

# Проверить что nginx слушает 443
sudo netstat -tlnp | grep :443

# Проверить что сертификат существует
sudo ls -la /etc/letsencrypt/live/agentiq.ru/
```

### Ошибка: "openssl command not found"
```bash
sudo apt install -y openssl
```

### Ошибка: "Permission denied"
```bash
# Убедиться что скрипт исполняемый
sudo chmod +x /opt/agentiq/scripts/ops/ssl-check.sh

# Убедиться что запускается от root
sudo /opt/agentiq/scripts/ops/ssl-check.sh
```

### Cron не запускается
```bash
# Проверить синтаксис crontab
sudo crontab -l | grep certbot

# Проверить systemd timer (альтернатива cron)
sudo systemctl status certbot.timer

# Проверить логи cron
sudo grep CRON /var/log/syslog | tail -20
```

## Дополнительные ресурсы

- [Let's Encrypt: Certbot Instructions](https://certbot.eff.org/instructions?ws=nginx&os=ubuntufocal)
- [Let's Encrypt: Rate Limits](https://letsencrypt.org/docs/rate-limits/)
- [nginx SSL Configuration](https://ssl-config.mozilla.org/)
- [SSL Labs Server Test](https://www.ssllabs.com/ssltest/)

## Контакты

- VPS IP: `79.137.175.164`
- Domain: `agentiq.ru`
- SSH Key: `~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem`
- Admin: См. CLAUDE.md для контактов
