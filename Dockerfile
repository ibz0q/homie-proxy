FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY homie_proxy.py .
COPY proxy_config.json .

# Expose the port
EXPOSE 8080

# Run the proxy server
CMD ["python", "homie_proxy.py", "--host", "0.0.0.0", "--port", "8080"] 