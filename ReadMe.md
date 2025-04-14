# Simple Banking System

A RESTful API for a simple banking system built with Flask and Flask-RESTX.

## Table of Contents

- [Project Overview](#project-overview)
- [Setup](#setup)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Design Principles](#design-principles)
- [System Architecture](#system-architecture)

## Project Overview

This project implements a simple banking system with the following features:

- Account management (create, view, list)
- Transaction operations (deposit, withdraw, transfer)
- Transaction history and statements
- Command pattern implementation for operations
- RESTful API with Swagger documentation

## Setup

### Prerequisites

- Python 3.8 or higher
- Docker (optional, for containerized deployment)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/SimpleBankingSystem.git
cd SimpleBankingSystem
```

2. Create and activate a virtual environment:

#### Windows

```powershell
# First, ensure pip is installed
python -m pip install --upgrade pip
# Create virtual environment
python -m venv venv --without-pip

# Activate the virtual environment
.\venv\Scripts\activate

# Install pip in the virtual environment
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py
```

#### Linux/Mac

```bash
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

### Running the Application

#### Local Development

```bash
python -m SimpleBankingSystem.app
```

#### Docker Deployment

```bash
docker build -t simple-banking-system .
docker run -p 5000:5000 simple-banking-system
```

The API will be available at `http://localhost:5000/api/v1/`

## API Documentation

### Base URL

All API endpoints are prefixed with `/api/v1/`

### Swagger Documentation

Access the interactive API documentation at:

```
http://localhost:5000/api/v1/swagger/
```

### Available Endpoints

#### Health Check

- `GET /health/` - Check API health status

#### Accounts

- `GET /accounts/` - List all accounts
- `POST /accounts/` - Create a new account
- `GET /accounts/<account_id>/` - Get account details
- `GET /accounts/<account_id>/transactions/` - Get account transactions

#### Transactions

- `POST /accounts/<account_id>/deposit/` - Make a deposit
- `POST /accounts/<account_id>/withdraw/` - Make a withdrawal
- `POST /accounts/<account_id>/transfer/` - Transfer money to another account
- `GET /accounts/<account_id>/statement/` - Get account statement

### Example API Calls

#### Create Account

```bash
curl -X POST http://localhost:5000/api/v1/accounts \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "initial_balance": 1000.00}'
```

#### Make a Deposit

```bash
curl -X POST http://localhost:5000/api/v1/accounts/<account_id>/deposit \
  -H "Content-Type: application/json" \
  -d '{"amount": 100.00}'
```

#### Get Account Statement

```bash
curl http://localhost:5000/api/v1/accounts/<account_id>/statement
```

## Testing

### Running Tests

```bash
python -m pytest
```

### Test Coverage

```bash
python -m pytest --cov=SimpleBankingSystem
```

## Project Structure

```
SimpleBankingSystem/
├── __init__.py
├── app.py              # Flask application factory
├── api.py              # API routes and documentation
├── commands.py         # Command pattern implementation
├── config.py           # Application configuration
├── models.py           # Data models
├── test_routes.py      # API test cases
└── test_commands.py    # Command pattern test cases
```

## Design Principles

1. **Immutability**: Completed transactions are immutable to prevent data corruption
2. **Thread Safety**: All operations are thread-safe using locks
3. **Decimal Precision**: Financial calculations use Decimal for precise arithmetic
4. **Clean Architecture**: Separation of concerns between layers
5. **State Management**: Clear transaction lifecycle with immutable completed state

### Transaction States

- PENDING: Initial state when a transaction is created
- PROCESSING: Transaction is being processed
- COMPLETED: Transaction is finalized and cannot be modified
- FAILED: Transaction has failed and can be retried

### State Transition Flow

```mermaid
    [*] --> PENDING: Transaction Created
    PENDING --> PROCESSING: Start Processing
    PENDING --> COMPLETED: Direct Completion
    PENDING --> FAILED: Validation Failed
    PROCESSING --> COMPLETED: Success
    PROCESSING --> FAILED: Processing Error
    FAILED --> PENDING: Retry
    COMPLETED --> [*]: Final State
```

## System Architecture

### Command Pattern Implementation

The system uses the Command pattern to encapsulate banking operations:

```python
class BaseCommand(ABC):
    @abstractmethod
    def execute(self, accounts: Dict[str, BankAccount]) -> Dict[str, Any]:
        """Perform the command action."""
        pass

    def save_state(self, accounts: Dict[str, BankAccount]):
        """Save the current state of all accounts to CSV files."""
        pass
```
