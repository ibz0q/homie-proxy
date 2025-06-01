FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application files
COPY . .

# Expose the default port
EXPOSE 8080

# Run the server
CMD ["python", "homie_proxy.py", "--host", "0.0.0.0", "--port", "8080"] 