# Інструкція з встановлення WebQuiz

Цей документ містить повну інструкцію з встановлення та налаштування системи WebQuiz на різних операційних системах.

## Системні вимоги

### Мінімальні вимоги:
- **Python**: версія 3.9 або новіша
- **Оперативна пам'ять**: мінімум 512 MB RAM
- **Дисковий простір**: 100 MB для програми + додатковий простір для даних
- **Мережа**: доступ до портів 8080-8090 (або інших за налаштуваннями)

### Рекомендовані вимоги:
- **Python**: версія 3.11+
- **Оперативна пам'ять**: 1 GB RAM або більше
- **Дисковий простір**: 1 GB для комфортної роботи
- **Процесор**: 1 GHz або швидший

## Встановлення

### Метод 1: Встановлення через PyPI (Рекомендовано)

```bash
# Встановлення останньої версії
pip install webquiz

# Запуск сервера
webquiz

# Доступ через браузер
http://localhost:8080
```

### Метод 2: Встановлення з вихідного коду

```bash
# Клонування репозиторію
git clone https://github.com/oduvan/webquiz.git
cd webquiz

# Встановлення через Poetry (рекомендовано)
pip install poetry
poetry install
poetry run webquiz

# Або через pip
pip install -r requirements.txt
python -m webquiz.cli
```

### Метод 3: Використання готового бінарного файлу

```bash
# Завантажте останній реліз з GitHub
wget https://github.com/oduvan/webquiz/releases/latest/download/webquiz

# Додайте права на виконання (Linux/macOS)
chmod +x webquiz

# Запустіть програму
./webquiz
```

## Конфігурація після встановлення

### Базова конфігурація

При першому запуску система автоматично створює:

```bash
# Перший запуск створює структуру папок
webquiz

# Структура, що створюється:
├── quizzes/          # Тести
├── logs/             # Логи
├── csv_data/         # Дані користувачів
├── static/           # Веб-файли
└── webquiz.yaml      # Конфігурація
```

### Налаштування адміністративної панелі

```bash
# Встановлення ключа адміністратора
webquiz --master-key your_secret_key

# Або через змінну середовища
export WEBQUIZ_MASTER_KEY="your_secret_key"
webquiz
```

### Налаштування мережі

```bash
# Зміна порту
webquiz --port 9090

# Зміна IP адреси
webquiz --host 127.0.0.1

# Комбіновані налаштування
webquiz --host 0.0.0.0 --port 8080 --master-key admin123
```

## Інсталяція на різних ОС

### Ubuntu/Debian

```bash
# Оновлення пакетів
sudo apt update

# Встановлення Python та pip
sudo apt install python3 python3-pip python3-venv

# Створення віртуального середовища
python3 -m venv webquiz-env
source webquiz-env/bin/activate

# Встановлення WebQuiz
pip install webquiz

# Запуск
webquiz
```

### CentOS/RHEL/Fedora

```bash
# Встановлення Python
sudo dnf install python3 python3-pip

# Створення віртуального середовища
python3 -m venv webquiz-env
source webquiz-env/bin/activate

# Встановлення WebQuiz
pip install webquiz

# Запуск
webquiz
```

### macOS

```bash
# Встановлення через Homebrew
brew install python3

# Або встановлення Python з офіційного сайту
# https://www.python.org/downloads/

# Встановлення WebQuiz
pip3 install webquiz

# Запуск
webquiz
```

### Windows

```cmd
# Завантажте Python з https://www.python.org/downloads/
# Переконайтеся, що pip встановлений

# Відкрийте Command Prompt або PowerShell
pip install webquiz

# Запуск
webquiz
```

## Запуск як служба

### Linux (systemd)

Створіть файл служби:

```bash
sudo nano /etc/systemd/system/webquiz.service
```

```ini
[Unit]
Description=WebQuiz Server
After=network.target

[Service]
Type=simple
User=webquiz
WorkingDirectory=/opt/webquiz
Environment=WEBQUIZ_MASTER_KEY=your_secret_key
ExecStart=/opt/webquiz/venv/bin/webquiz --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Активація служби
sudo systemctl daemon-reload
sudo systemctl enable webquiz
sudo systemctl start webquiz

# Перевірка статусу
sudo systemctl status webquiz
```

### Windows (як служба)

```cmd
# Встановлення NSSM (Non-Sucking Service Manager)
# Завантажте з https://nssm.cc/download

# Реєстрація служби
nssm install WebQuiz
nssm set WebQuiz Application "C:\Python\Scripts\webquiz.exe"
nssm set WebQuiz Parameters "--host 0.0.0.0 --port 8080"
nssm set WebQuiz DisplayName "WebQuiz Server"
nssm set WebQuiz Description "WebQuiz Testing System"

# Запуск служби
nssm start WebQuiz
```

## Docker

### Використання готового образу

```bash
# Запуск контейнера
docker run -d \
  --name webquiz \
  -p 8080:8080 \
  -e WEBQUIZ_MASTER_KEY=your_secret_key \
  -v webquiz_data:/app/data \
  oduvan/webquiz:latest
```

### Створення власного образу

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8080

CMD ["python", "-m", "webquiz.cli", "--host", "0.0.0.0"]
```

```bash
# Збірка образу
docker build -t my-webquiz .

# Запуск
docker run -d -p 8080:8080 my-webquiz
```

## Nginx як реверс-проксі

```nginx
# /etc/nginx/sites-available/webquiz
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket підтримка для живої статистики
    location /ws/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
# Активація конфігурації
sudo ln -s /etc/nginx/sites-available/webquiz /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## SSL/HTTPS налаштування

### Використання Let's Encrypt

```bash
# Встановлення Certbot
sudo apt install certbot python3-certbot-nginx

# Отримання сертифіката
sudo certbot --nginx -d your-domain.com

# Автоматичне поновлення
sudo crontab -e
# Додайте: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Налагодження та усунення проблем

### Перевірка логів

```bash
# Перегляд останніх логів
tail -f logs/server_latest.log

# Пошук помилок
grep ERROR logs/server_*.log
```

### Перевірка портів

```bash
# Linux/macOS
netstat -tulpn | grep 8080
ss -tulpn | grep 8080

# Windows
netstat -an | findstr 8080
```

### Тестування підключення

```bash
# Перевірка доступності
curl http://localhost:8080/

# Перевірка API
curl -X POST http://localhost:8080/api/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test_user"}'
```

## Оновлення

### Оновлення через PyPI

```bash
pip install --upgrade webquiz
```

### Оновлення з вихідного коду

```bash
cd webquiz
git pull origin master
poetry install
# або pip install -r requirements.txt
```

## Резервне копіювання

### Важливі папки для резервування:

```bash
# Створення архіву
tar -czf webquiz-backup-$(date +%Y%m%d).tar.gz \
  quizzes/ \
  csv_data/ \
  webquiz.yaml \
  logs/

# Відновлення
tar -xzf webquiz-backup-20240115.tar.gz
```

### Автоматичне резервування

```bash
#!/bin/bash
# backup-webquiz.sh
BACKUP_DIR="/backups/webquiz"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/webquiz-$DATE.tar.gz \
  /opt/webquiz/quizzes/ \
  /opt/webquiz/csv_data/ \
  /opt/webquiz/webquiz.yaml

# Видалення старих архівів (старше 30 днів)
find $BACKUP_DIR -name "webquiz-*.tar.gz" -mtime +30 -delete
```

## Моніторинг

### Базовий моніторинг

```bash
# Перевірка статусу процесу
ps aux | grep webquiz

# Перевірка використання ресурсів
top -p $(pgrep -f webquiz)

# Перевірка дискового простору
df -h
du -sh quizzes/ csv_data/ logs/
```

Після встановлення перейдіть до [посібника користувача](user-guide.md) для детальної інформації про використання системи.