# AgentIQ Reviews — Деплой на VPS

## Требования

- Ubuntu 22.04+ VPS (2GB RAM minimum)
- Домен `app.agentiq.ru` с DNS A-record на IP сервера
- Docker и Docker Compose
- Nginx + Certbot (SSL)

## 1. Установка зависимостей

```bash
# Docker
sudo apt update && sudo apt install -y docker.io docker-compose

# Nginx + Certbot
sudo apt install -y nginx certbot python3-certbot-nginx

# Запуск Docker
sudo systemctl enable docker
sudo systemctl start docker
```

## 2. Клонирование репозитория

```bash
cd /opt
sudo git clone <repo-url> agentiq
cd agentiq
```

## 3. Настройка .env

```bash
cp apps/reviews/.env.example apps/reviews/.env
nano apps/reviews/.env
```

Обязательно заполнить:
- `SECRET_KEY` — сгенерировать: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- `ENVIRONMENT=production`
- `TELEGRAM_BOT_TOKEN` — от @BotFather
- `TELEGRAM_BOT_USERNAME` — без @
- `WBCON_TOKEN` — JWT токен для 19-fb.wbcon.su
- `DEEPSEEK_API_KEY` — ключ от DeepSeek
- `FRONTEND_URL=https://app.agentiq.ru`
- `REDIS_URL=redis://redis:6379/0` (Redis внутри Docker)

## 4. Создание инвайт-кодов

Инвайт-коды нужно создать вручную в БД после первого запуска:

```bash
# После docker-compose up:
docker-compose -f infra/docker-compose.yml exec web python3 -c "
from backend.database import InviteCode, engine
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

eng = create_engine('sqlite:///./data/agentiq.db')
with Session(eng) as s:
    code = InviteCode(code='BETA-2026-A3F7', max_uses=50, created_by='admin')
    s.add(code)
    s.commit()
    print(f'Created invite code: {code.code}')
"
```

## 5. Telegram Bot настройка

В @BotFather:
1. `/setdomain` → `app.agentiq.ru`
2. Это нужно для Telegram Login Widget

## 6. Запуск Docker

```bash
cd /opt/agentiq
sudo docker-compose -f infra/docker-compose.yml up -d --build
```

Проверка:
```bash
docker-compose -f infra/docker-compose.yml ps          # Все 3 сервиса running
docker-compose -f infra/docker-compose.yml logs web    # Логи FastAPI
docker-compose -f infra/docker-compose.yml logs worker # Логи Celery
curl http://localhost:8000/health  # {"status":"ok","version":"mvp2"}
```

## 7. Nginx + SSL

```bash
# Скопировать конфиг
sudo cp infra/deploy/nginx.conf /etc/nginx/sites-available/agentiq
sudo ln -s /etc/nginx/sites-available/agentiq /etc/nginx/sites-enabled/

# Сначала убрать SSL-блок (certbot добавит сам)
# Оставить только server { listen 80; server_name app.agentiq.ru; location / { proxy_pass ... } }
sudo nginx -t
sudo systemctl reload nginx

# Получить SSL сертификат
sudo certbot --nginx -d app.agentiq.ru

# Проверить
curl https://app.agentiq.ru/health
```

## 8. Проверка

1. Открыть `https://app.agentiq.ru` — должна быть landing page
2. Telegram Login → ввод инвайт-кода → dashboard
3. Ввести артикул → дождаться готовности → открыть оба отчёта
4. Скачать PDF → проверить тёмную тему
5. Удалить задачу → проверить

## Обновление

```bash
cd /opt/agentiq
git pull
sudo docker-compose up -d --build
```

## Мониторинг

```bash
# Логи в реальном времени
docker-compose logs -f web
docker-compose logs -f worker

# Перезапуск
docker-compose restart web
docker-compose restart worker

# Полный перезапуск
docker-compose down && docker-compose up -d
```

## Бэкап БД

```bash
# SQLite файл лежит в Docker volume
docker cp $(docker-compose ps -q web):/app/data/agentiq.db ./backup-agentiq.db
```

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| `redis connection refused` | `docker-compose restart redis` |
| `WBCON 401` | Обновить `WBCON_TOKEN` в `.env`, рестарт worker |
| `Playwright timeout` | Увеличить RAM или добавить `--disable-gpu` |
| `Telegram login не работает` | Проверить домен в BotFather и `FRONTEND_URL` |
| БД заблокирована | Перезапуск: `docker-compose restart web worker` |
