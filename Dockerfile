# Use Python 3.9 slim image as base
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app \
    DATA_DIR=/app/data \
    FLASK_APP=SimpleBankingSystem.app \
    FLASK_ENV=development

# Create directory for CSV files
RUN mkdir -p /app/data

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application files
COPY SimpleBankingSystem/ SimpleBankingSystem/

# Expose port
EXPOSE 5000

# Run the application
CMD ["flask", "run", "--host=0.0.0.0"] 