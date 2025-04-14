import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Flask configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    DATA_DIR = os.getenv('DATA_DIR', 'data')
    ACCOUNTS_FILE = os.path.join(DATA_DIR, 'accounts.csv')
    TRANSACTIONS_FILE = os.path.join(DATA_DIR, 'transactions.csv')
    os.makedirs(DATA_DIR, exist_ok=True) 