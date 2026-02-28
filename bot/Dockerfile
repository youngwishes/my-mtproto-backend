FROM python:3.13-slim

# Устанавливаем uv

WORKDIR /app

# Копируем файлы с зависимостями
COPY requirements.txt .

# Устанавливаем зависимости без создания виртуального окружения
RUN pip install -r requirements.txt

# Копируем остальной код
COPY . .

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Запускаем бота
CMD ["python", "src/bot.py"]