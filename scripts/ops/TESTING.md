# Testing SSL Scripts

Руководство по тестированию SSL скриптов локально и на сервере.

## Локальное тестирование

### 1. Тест ssl-check.sh синтаксиса
```bash
cd /Users/ivanilin/Documents/ivanilin/agentiq
bash -n scripts/ops/ssl-check.sh
# Должно вывести: (ничего) — значит синтаксис валиден
```

### 2. Тест ssl-check.sh на реальном домене
```bash
./scripts/ops/ssl-check.sh agentiq.ru 14
# Expected output:
# [INFO] Checking SSL certificate for agentiq.ru...
# [INFO] Certificate expires: Mar 10 23:59:59 2026 GMT
# [INFO] Days until expiry: 23
# [INFO] Certificate is valid (23 days remaining)
# Exit code: 0
```

### 3. Тест с кастомным порогом
```bash
# Тест warning (если cert истекает < 30 дней)
./scripts/ops/ssl-check.sh agentiq.ru 30

# Тест с очень высоким порогом (100 дней) — должен показать warning
./scripts/ops/ssl-check.sh agentiq.ru 100
# Expected: [WARN] Certificate expires in X days (threshold: 100)
# Exit code: 1
```

### 4. Тест с несуществующим доменом
```bash
./scripts/ops/ssl-check.sh invalid-domain.test 14
# Expected: [ERROR] Failed to retrieve certificate
# Exit code: 1
```

### 5. Тест webhook alert (mock)
```bash
export ALERT_WEBHOOK="https://example.com/webhook"
./scripts/ops/ssl-check.sh agentiq.ru 100
# Должен попытаться отправить curl POST (может упасть с timeout, это норма для mock URL)
```

## Unit тесты (pytest)

### Запуск всех тестов
```bash
cd /Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend
source venv/bin/activate
pytest -v tests/test_ssl_check.py
```

### Запуск конкретного теста
```bash
pytest -v tests/test_ssl_check.py::TestSSLCheck::test_valid_certificate_no_alert
pytest -v tests/test_ssl_check.py::TestSSLCheck::test_expiring_soon_certificate_warning
pytest -v tests/test_ssl_check.py::TestSSLCheck::test_expired_certificate_error
```

### Запуск с coverage
```bash
pytest --cov=app.services --cov-report=term tests/test_ssl_check.py
```

## Тестирование на сервере

### 1. Загрузка скрипта на сервер
```bash
cd /Users/ivanilin/Documents/ivanilin/agentiq
scp -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem \
    scripts/ops/ssl-check.sh \
    ubuntu@79.137.175.164:/tmp/
```

### 2. Установка и первый запуск
```bash
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164

# Установить
sudo mkdir -p /opt/agentiq/scripts/ops
sudo cp /tmp/ssl-check.sh /opt/agentiq/scripts/ops/
sudo chmod +x /opt/agentiq/scripts/ops/ssl-check.sh

# Тест
sudo /opt/agentiq/scripts/ops/ssl-check.sh agentiq.ru 14
```

### 3. Dry-run тест certbot
```bash
# На сервере
sudo certbot renew --dry-run
# Expected: "Congratulations, all simulated renewals succeeded"
```

### 4. Проверка systemd timer
```bash
sudo systemctl list-timers | grep certbot
# Expected: certbot.timer с следующим запуском через ~12 часов
```

### 5. Ручное продление (форсированное)
```bash
# ВНИМАНИЕ: Только для теста! Может вызвать rate limit от Let's Encrypt
sudo certbot renew --force-renewal --dry-run  # Dry-run безопасно
# Если все ок:
# sudo certbot renew --force-renewal  # Реальное продление
# sudo systemctl reload nginx
```

### 6. Проверка логов
```bash
# Логи certbot
sudo tail -50 /var/log/letsencrypt/letsencrypt.log

# Логи systemd timer
sudo journalctl -u certbot.timer -n 50

# Логи nginx
sudo tail -50 /var/log/nginx/error.log
```

## Тестирование cron (если установили кастомный)

### 1. Загрузка crontab на сервер
```bash
scp -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem \
    scripts/ops/ssl-renew-cron.conf \
    ubuntu@79.137.175.164:/tmp/

ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164
sudo cp /tmp/ssl-renew-cron.conf /etc/cron.d/agentiq-ssl-renew
sudo chmod 644 /etc/cron.d/agentiq-ssl-renew
```

### 2. Проверка синтаксиса crontab
```bash
# Показать активные cron задачи
sudo crontab -l

# Проверить что наш файл читается
sudo cat /etc/cron.d/agentiq-ssl-renew
```

### 3. Ручной запуск cron задачи
```bash
# Запустить команду из crontab вручную
sudo certbot renew --quiet --post-hook "systemctl reload nginx"

# Запустить ssl-check вручную
sudo /opt/agentiq/scripts/ops/ssl-check.sh agentiq.ru 14
```

### 4. Мониторинг cron логов
```bash
# Логи cron (в реальном времени)
sudo tail -f /var/log/syslog | grep CRON

# Последние запуски
sudo grep CRON /var/log/syslog | tail -20
```

## Expected Results

### Здоровый сертификат (> 14 дней до истечения)
```
[INFO] Checking SSL certificate for agentiq.ru...
[INFO] Certificate expires: Mar 10 23:59:59 2026 GMT
[INFO] Days until expiry: 23
[INFO] Certificate is valid (23 days remaining)
Exit code: 0
```

### Сертификат истекает скоро (< 14 дней)
```
[INFO] Checking SSL certificate for agentiq.ru...
[INFO] Certificate expires: Feb 28 23:59:59 2026 GMT
[INFO] Days until expiry: 13
[WARN] Certificate expires in 13 days (threshold: 14)
======================================
⚠️  SSL Certificate expiring soon for agentiq.ru (13 days left)
Domain: agentiq.ru
Expires: Feb 28 23:59:59 2026 GMT
Days left: 13
======================================
Exit code: 1
```

### Сертификат истёк
```
[INFO] Checking SSL certificate for agentiq.ru...
[INFO] Certificate expires: Feb 10 23:59:59 2026 GMT
[INFO] Days until expiry: -5
[ERROR] Certificate EXPIRED 5 days ago!
======================================
🚨 SSL Certificate EXPIRED for agentiq.ru (expired 5 days ago)
Domain: agentiq.ru
Expires: Feb 10 23:59:59 2026 GMT
Days left: -5
======================================
Exit code: 2
```

## Troubleshooting Tests

### Ошибка: "command not found: openssl"
```bash
# На Mac
brew install openssl

# На Ubuntu/Debian
sudo apt install openssl
```

### Ошибка: "Failed to retrieve certificate"
```bash
# Проверить что домен доступен
curl -I https://agentiq.ru

# Проверить DNS
dig agentiq.ru +short
nslookup agentiq.ru

# Проверить что порт 443 открыт
telnet agentiq.ru 443
# Или
nc -zv agentiq.ru 443
```

### Ошибка: "date: illegal time format"
```bash
# macOS и Linux используют разные флаги для date
# Скрипт поддерживает обе платформы через fallback:
# date -j (macOS) || date -d (Linux)

# Если всё равно не работает — проверить версию date:
date --version  # GNU date
date -j          # BSD date (macOS)
```

### pytest ошибка: "ModuleNotFoundError"
```bash
# Убедиться что venv активирован
cd apps/chat-center/backend
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
pip install pytest pytest-cov

# Проверить PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest -v tests/test_ssl_check.py
```

## CI/CD Integration

Для интеграции в CI/CD pipeline:

### GitHub Actions
```yaml
name: SSL Check
on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM
  workflow_dispatch:

jobs:
  check-ssl:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Check SSL Certificate
        run: |
          chmod +x scripts/ops/ssl-check.sh
          ./scripts/ops/ssl-check.sh agentiq.ru 14
      - name: Alert on failure
        if: failure()
        run: |
          curl -X POST ${{ secrets.SLACK_WEBHOOK }} \
            -H 'Content-Type: application/json' \
            -d '{"text":"SSL certificate check failed for agentiq.ru"}'
```

### Monitoring (Prometheus/Grafana)
```bash
# Экспорт метрик для Prometheus
./scripts/ops/ssl-check.sh agentiq.ru | \
  grep "Days until expiry" | \
  awk '{print "ssl_days_until_expiry{domain=\"agentiq.ru\"} " $5}' \
  > /var/lib/node_exporter/ssl_cert.prom
```

## Maintenance Checklist

Ежемесячная проверка:
- [ ] Запустить `sudo certbot certificates` — проверить даты истечения
- [ ] Запустить `sudo certbot renew --dry-run` — проверить что auto-renewal работает
- [ ] Проверить логи: `/var/log/letsencrypt/letsencrypt.log`
- [ ] Запустить ssl-check.sh вручную — проверить алерты
- [ ] Проверить что nginx перезагружается после продления
- [ ] Проверить сертификат в браузере: https://agentiq.ru

Ежеквартальная проверка:
- [ ] Обновить certbot: `sudo apt update && sudo apt upgrade certbot`
- [ ] Проверить rate limits: https://letsencrypt.org/docs/rate-limits/
- [ ] Проверить SSL configuration: https://www.ssllabs.com/ssltest/analyze.html?d=agentiq.ru
- [ ] Обновить документацию если изменились процедуры
