FROM python:3.11-slim

WORKDIR /app

# 1. Install system tools (Securely)
RUN apt-get update && apt-get install -y build-essential curl

# 2. SECURITY FIX: Trust the Corporate Network
# We copy the corporate certificate you exported into the container's trust store.
COPY corporate_root.crt /usr/local/share/ca-certificates/corporate_root.crt

# 3. Update the container's certificate bundle
# This command regenerates /etc/ssl/certs/ca-certificates.crt to include your corporate root
RUN chmod 644 /usr/local/share/ca-certificates/corporate_root.crt && update-ca-certificates

# 4. Tell Python/Pip to use this new trusted bundle
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# 5. Install Python dependencies (Now working securely!)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy application code
COPY . .

# Default command
CMD ["python", "guardian_demo.py"]