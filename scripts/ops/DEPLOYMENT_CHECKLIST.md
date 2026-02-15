# SSL Auto-Renewal Deployment Checklist

Краткий чеклист для развёртывания SSL автопродления на VPS.

## Pre-deployment (локально)

- [x] Создан `ssl-check.sh` — скрипт проверки сертификата
- [x] Создан `ssl-renew-cron.conf` — crontab для автопродления
- [x] Создан `README-ssl.md` — полная документация
- [x] Создан `TESTING.md` — руководство по тестированию
- [x] Создан `test_ssl_check.py` — unit тесты
- [x] Обновлён `nginx.conf` — добавлены комментарии про SSL
- [ ] Прочитать `README-ssl.md` — понять процесс

## Deployment (на сервере)

### 1. Подключение к VPS
```bash
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164
```

### 2. Установка certbot (если ещё не установлен)
```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

### 3. Получение SSL сертификата (первый раз)
```bash
sudo certbot --nginx -d agentiq.ru -d www.agentiq.ru
# Следовать интерактивным инструкциям
# Email: admin@agentiq.ru (или ваш)
# Agree to ToS: Yes
# Redirect HTTP to HTTPS: Yes
```

### 4. Проверка что сертификат получен
```bash
sudo certbot certificates
# Должно показать:
# Certificate Name: agentiq.ru
# Domains: agentiq.ru www.agentiq.ru
# Expiry Date: 2026-05-... (3 месяца от сегодня)
```

### 5. Загрузка ssl-check.sh на сервер
```bash
# На локальной машине
cd /Users/ivanilin/Documents/ivanilin/agentiq
scp -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem \
    scripts/ops/ssl-check.sh \
    ubuntu@79.137.175.164:/tmp/
```

### 6. Установка ssl-check.sh на сервере
```bash
# На сервере
sudo mkdir -p /opt/agentiq/scripts/ops
sudo cp /tmp/ssl-check.sh /opt/agentiq/scripts/ops/
sudo chmod +x /opt/agentiq/scripts/ops/ssl-check.sh
sudo chown root:root /opt/agentiq/scripts/ops/ssl-check.sh
```

### 7. Тест ssl-check.sh
```bash
sudo /opt/agentiq/scripts/ops/ssl-check.sh agentiq.ru 14
# Expected: [INFO] Certificate is valid (XX days remaining)
# Exit code: 0
```

### 8. Проверка автопродления (systemd timer)
```bash
# Certbot автоматически создаёт systemd timer
sudo systemctl list-timers | grep certbot
# Должно показать: certbot.timer — next run в ближайшие 12 часов
```

### 9. Dry-run тест автопродления
```bash
sudo certbot renew --dry-run
# Expected: "Congratulations, all simulated renewals succeeded"
```

### 10. (Опционально) Установка кастомного cron
```bash
# На локальной машине
scp -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem \
    scripts/ops/ssl-renew-cron.conf \
    ubuntu@79.137.175.164:/tmp/

# На сервере
sudo cp /tmp/ssl-renew-cron.conf /etc/cron.d/agentiq-ssl-renew
sudo chmod 644 /etc/cron.d/agentiq-ssl-renew
sudo chown root:root /etc/cron.d/agentiq-ssl-renew

# ВАЖНО: Отредактировать MAILTO
sudo nano /etc/cron.d/agentiq-ssl-renew
# Изменить: MAILTO=admin@agentiq.ru на ваш email
```

### 11. Проверка nginx конфигурации
```bash
sudo nginx -t
# Expected: nginx: configuration file /etc/nginx/nginx.conf test is successful

sudo systemctl status nginx
# Expected: active (running)

# Проверить что SSL работает
curl -I https://agentiq.ru
# Expected: HTTP/2 200
```

### 12. Проверка доступности сайта
```bash
# В браузере
# https://agentiq.ru — должен работать с зелёным замком
# https://agentiq.ru/app/ — Chat Center
# https://agentiq.ru/api/health — API health check

# Из командной строки
curl https://agentiq.ru
curl https://agentiq.ru/api/health
```

## Post-deployment Verification

### 13. Тест SSL в браузере
1. Открыть https://agentiq.ru
2. Кликнуть на замок в адресной строке
3. "Certificate" → проверить:
   - Issued to: agentiq.ru
   - Issued by: Let's Encrypt
   - Valid from / to: проверить даты

### 14. Проверка SSL через SSLLabs (опционально)
1. Открыть https://www.ssllabs.com/ssltest/
2. Ввести: agentiq.ru
3. Подождать 2-3 минуты
4. Проверить рейтинг (должен быть A или A+)

### 15. Проверка логов certbot
```bash
sudo tail -50 /var/log/letsencrypt/letsencrypt.log
# Проверить на наличие ошибок
```

### 16. Настройка email алертов (опционально)
```bash
# Установить postfix для email уведомлений от cron
sudo apt install -y postfix
# Выбрать: Internet Site
# System mail name: agentiq.ru
```

### 17. Документация
```bash
# Сохранить информацию о сертификате
sudo certbot certificates > /opt/agentiq/ssl-cert-info.txt
cat /opt/agentiq/ssl-cert-info.txt
```

## Maintenance Schedule

Настроить напоминания:

### Еженедельно (автоматически через cron)
- Certbot renew проверяет сертификат 2 раза в день
- ssl-check.sh запускается ежедневно в 6 AM

### Ежемесячно (вручную)
- Проверить `/var/log/letsencrypt/letsencrypt.log`
- Запустить `sudo certbot certificates`
- Проверить https://agentiq.ru в браузере

### Ежеквартально (вручную)
- Обновить certbot: `sudo apt update && sudo apt upgrade certbot`
- Запустить SSL test: https://www.ssllabs.com/ssltest/
- Обновить документацию если были изменения

## Rollback Plan

Если что-то пошло не так:

### 1. Откатить nginx конфиг
```bash
sudo cp /etc/nginx/sites-available/agentiq.bak /etc/nginx/sites-available/agentiq
sudo systemctl reload nginx
```

### 2. Удалить сертификат
```bash
sudo certbot delete --cert-name agentiq.ru
```

### 3. Удалить cron задачи
```bash
sudo rm /etc/cron.d/agentiq-ssl-renew
```

### 4. Удалить скрипты
```bash
sudo rm -rf /opt/agentiq/scripts/ops/
```

## Emergency Contacts

- **VPS Provider:** Check VPS dashboard
- **Let's Encrypt Status:** https://letsencrypt.status.io/
- **Domain Registrar:** Проверить DNS записи
- **nginx Docs:** https://nginx.org/en/docs/

## Success Criteria

✅ Deployment успешен если:
- [ ] `curl -I https://agentiq.ru` возвращает `HTTP/2 200`
- [ ] `sudo certbot certificates` показывает валидный сертификат
- [ ] `sudo certbot renew --dry-run` проходит успешно
- [ ] `sudo /opt/agentiq/scripts/ops/ssl-check.sh agentiq.ru` exit code 0
- [ ] Browser показывает зелёный замок на https://agentiq.ru
- [ ] SSLLabs test возвращает рейтинг A или A+

## Timeline

Estimated time: **30-45 минут**

- Setup certbot: 5 мин
- Get certificate: 2 мин
- Upload scripts: 3 мин
- Configure cron: 5 мин
- Testing: 10 мин
- Verification: 10 мин
- Documentation: 5 мин

## Next Steps

После успешного деплоя:

1. Обновить `apps/chat-center/nginx.conf` на сервере (раскомментировать SSL блок)
2. Добавить мониторинг метрик (Prometheus/Grafana)
3. Настроить webhook алерты в Slack/Telegram
4. Создать runbook для команды
5. Добавить в onboarding для новых devops

## Notes

- Let's Encrypt сертификаты валидны 90 дней
- Автопродление происходит за 30 дней до истечения
- Rate limit: 50 сертификатов на домен в неделю
- Если домен недоступен — продление не сработает
- nginx должен быть запущен для challenge verification
- Порты 80 и 443 должны быть открыты в firewall
