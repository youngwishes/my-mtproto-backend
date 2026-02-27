# Dockerfile
FROM python:3.13-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы с зависимостями
COPY requirements.txt .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Устанавливаем зависимости через uv
RUN pip install -r requirements.txt

# Копируем исходный код
COPY src/ .

# Открываем порт
EXPOSE 8000

# Запускаем приложение через uv