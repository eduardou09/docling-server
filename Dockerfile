FROM python:3.11-slim

# Instalar dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar docling
RUN pip install docling[default]

# Criar diretório de trabalho
WORKDIR /app

# Copiar arquivos da aplicação
COPY . .

# Expor porta
EXPOSE 8080

# Comando para iniciar o servidor
CMD ["python", "-m", "docling_serve", "--host", "0.0.0.0", "--port", "8080"]
