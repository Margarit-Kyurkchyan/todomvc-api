# TodoMVC Backend API

A rococo-based backend for TodoMVC web app built with Flask, PostgreSQL, and RabbitMQ.

## Prerequisites

- Docker and Docker Compose installed on your system
- Git (to clone the repository)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd todomvc-api
```

### 2. Set Up Environment Files

Copy the environment files from the example/template files:

```bash
# Copy environment configuration
cp local.env .env

# Copy secrets template (if .env.secrets.example exists)
cp .env.secrets.example .env.secrets
```

**Important:** After copying `.env.secrets.example` to `.env.secrets`, you need to:
- Set `APP_ENV=local` (or your desired environment)
- Replace any placeholder values with actual secrets (passwords, API keys, etc.)
- Never commit `.env.secrets` to version control

### 3. Configure Environment Variables

The `.env` file (copied from `local.env`) contains environment-specific variables. The default `local.env` file should already be present in the repository with the necessary configuration.

### 4. Build and Run the Backend

After setting up the environment files, build and start the Docker containers:

```bash
# Build Docker images
docker-compose build

# Start all services
docker-compose up
```

**Alternative:** You can also use the provided `run.sh` script:

```bash
# Start the backend (uses existing Docker images)
./run.sh

# Or rebuild Docker images if needed
./run.sh --rebuild true
```

This will start the following services:
- **PostgreSQL** database (port 5432)
- **RabbitMQ** message queue (port 5672)
- **API** server (port 5000)
- **Email Transmitter** service

### 5. Run Database Migrations

Migrations run automatically when the API container starts. If you need to run them manually:

```bash
docker exec todomvc_api rococo-postgres rf
```

### 6. Verify Installation

Check that all containers are running:

```bash
docker ps
```

You should see containers for:
- `todomvc_postgres`
- `todomvc_rabbitmq`
- `todomvc_api`
- `todomvc_email_transmitter`

## API Documentation

Once the backend is running, you can access the interactive API documentation at:

**http://localhost:5000/api-doc**

This Swagger UI provides:
- Complete API endpoint documentation
- Interactive testing interface
- Request/response schemas
- Authentication details

## Running Tests

To run the test suite:

```bash
# Run all tests
docker exec todomvc_api pytest

# Run specific test file
docker exec todomvc_api pytest flask/tests/test_task_api.py -v

# Run with verbose output
docker exec todomvc_api pytest -v
```

## Project Structure

```
todomvc-api/
├── common/              # Shared code (models, services, repositories)
├── flask/               # Flask application
│   ├── app/
│   │   ├── views/      # API endpoints
│   │   └── migrations/  # Database migrations
│   └── tests/          # Test files
├── services/           # Docker service configurations
├── docker-compose.yml  # Docker Compose configuration
└── run.sh             # Startup script
```

## API Endpoints

### Authentication
- `POST /auth/signup` - User registration
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `POST /auth/forgot_password` - Request password reset
- `POST /auth/reset_password/<token>/<uidb64>` - Reset password

### Person
- `GET /person/me` - Get current user info
- `PUT /person/me` - Update current user name

### Tasks
- `GET /tasks` - List all tasks (ordered by changed_on, most recent first)
- `POST /tasks` - Create a new task
- `PUT /tasks/<task_id>` - Update a task
- `DELETE /tasks/<task_id>` - Delete a task

## Troubleshooting

### Containers won't start
- Check that Docker is running: `docker ps`
- Verify `.env.secrets` file exists and contains `APP_ENV=local`
- Check logs: `docker-compose logs`

### Database connection issues
- Ensure PostgreSQL container is healthy: `docker ps`
- Check database credentials in `local.env`
- Verify migrations ran: `docker exec todomvc_api rococo-postgres rf`

### Port conflicts
- If port 5000 is in use, modify the port mapping in `docker-compose.yml`
- Similarly for PostgreSQL (5432) and RabbitMQ (5672)

## Development

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
```

### Stop Services

```bash
docker-compose down
```

### Clean Up (removes volumes)

```bash
docker-compose down -v
```

## License

See LICENSE file for details.
