FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install boto3 --no-cache-dir

# Copy processor
COPY processor.py .

# Run the processor
CMD ["python", "processor.py"]