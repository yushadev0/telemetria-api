# Python'ın hafif bir sürümünü taban alıyoruz
FROM python:3.11-slim

# Konteyner içindeki çalışma klasörümüz
WORKDIR /app

# Kütüphane listemizi kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Projedeki tüm kodlarımızı kopyala
COPY . .

# FastAPI'nin çalışacağı portu belirtiyoruz
EXPOSE 8000

# Konteyner ayağa kalktığında çalışacak nihai komut (0.0.0.0 Docker için kritiktir)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]