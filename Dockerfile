# Use Python 3.9 slim image as base
FROM python:3.9-slim
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create directory for CSV files
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data
ENV FLASK_APP=SimpleBankingSystem.app
# debugging
ENV FLASK_ENV=development 

# Expose port
EXPOSE 5000

# Run the application
CMD ["flask", "run", "--host=0.0.0.0"] 