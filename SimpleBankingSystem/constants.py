from enum import Enum, auto
import os

# Transaction Types
class TransactionType(Enum):
    DEPOSIT = 1
    WITHDRAW = 2
    TRANSFER_IN = 3
    TRANSFER_OUT = 4

# Transaction Statuses
class TransactionStatus(Enum):
    PENDING = 1 
    PROCESSING = 2
    COMPLETED = 3
    FAILED = 4

# Environment Variables
DATA_DIR_ENV_VAR = 'SIMPLE_BANKING_DATA_DIR'
ACCOUNTS_FILE_ENV_VAR = 'SIMPLE_BANKING_ACCOUNTS_FILE'
TRANSACTIONS_FILE_ENV_VAR = 'SIMPLE_BANKING_TRANSACTIONS_FILE'

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

# File Names
DATA_DIR = os.getenv(DATA_DIR_ENV_VAR, DEFAULT_DATA_DIR)
ACCOUNTS_FILE = os.getenv(ACCOUNTS_FILE_ENV_VAR, os.path.join(DATA_DIR, 'accounts.csv'))
TRANSACTIONS_FILE = os.getenv(TRANSACTIONS_FILE_ENV_VAR, os.path.join(DATA_DIR, 'transactions.csv'))
ARCHIVED_TRANSACTIONS_FILE = os.path.join(DATA_DIR, 'archived_transactions.csv')
TRANSACTION_LOG_FILE = os.path.join(DATA_DIR, 'transaction_log.csv')

# Limits
MAX_ACTIVE_TRANSACTIONS = 1000  # Number of transactions to keep in memory before archiving
ARCHIVE_KEEP_COUNT = 100  # Number of transactions to keep in memory after archiving

# Default Values

DEFAULT_INITIAL_BALANCE = 0.00

# Transaction retry settings
MAX_TRANSACTION_RETRIES = 3