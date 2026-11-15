# Use Python 3.14 as the base image
FROM python:3.14

# Set the working directory inside the container
WORKDIR /auth_service

# Copy project files into the working directory
COPY . .

# Install the dependencies listed in requirements.txt
RUN pip install -r requirements.txt

# Run the application when the container starts
CMD ["python", "app.py"]