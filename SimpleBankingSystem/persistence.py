# persistence.py
import csv
import os
from tempfile import NamedTemporaryFile
from datetime import datetime, timezone
from decimal import Decimal

def get_data_dir():
    """Get the data directory from environment variable or use default."""
    return os.getenv('DATA_DIR', '.')

def get_file_path(filename):
    """Get the full path for a file in the data directory."""
    return os.path.join(get_data_dir(), filename)

def save_accounts(accounts, filename='accounts.csv'):
    """
    Save account summaries into a CSV file.
    Each account is represented by its id, name, initial_balance, current_balance,
    created_at and updated_at.
    todo: this is a snapshot table. convert accounts to a slow changing dimension (confirming features)
    """
    filepath = get_file_path(filename)
    temp_file = NamedTemporaryFile('w', delete=False, newline='', encoding='utf-8')
    with temp_file as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['account_id', 'account_name', 'initial_balance', 'account_balance', 'created_at', 'updated_at'])
        for account in accounts.values():
            writer.writerow([
                account.account_id,
                account.account_name,
                str(account.initial_balance),
                str(account.account_balance),
                account.created_at.isoformat(),
                account.updated_at.isoformat()
            ])
    os.replace(temp_file.name, filepath)

def save_transactions(accounts, filename='transactions.csv'):
    """
    Save all transactions from all accounts into a CSV file.
    Each row represents one transaction, along with its account_id.
    """
    filepath = get_file_path(filename)
    temp_file = NamedTemporaryFile('w', delete=False, newline='', encoding='utf-8')
    with temp_file as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['account_id', 'txn_type', 'txn_status', 'amount', 'description', 'timestamp'])
        for account in accounts.values():
            for txn in account.transactions:
                writer.writerow([
                    account.account_id,
                    txn.txn_type,
                    txn.txn_status,
                    str(txn.amount),
                    txn.description,
                    txn.timestamp.isoformat() if isinstance(txn.timestamp, datetime) else txn.timestamp
                ])
    os.replace(temp_file.name, filepath)

def load_accounts(filename='accounts.csv'):
    """
    Load account data from CSV into a dictionary mapping account_id to BankAccount.
    Note: We assume that BankAccount is constructed with the initial_balance.
    """
    accounts = {}
    filepath = get_file_path(filename)
    try:
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            from entities import BankAccount  # delayed import to avoid circular dependency
            for row in reader:
                account = BankAccount(
                    account_id=row['account_id'],
                    account_name=row['account_name'],
                    initial_balance=Decimal(row['initial_balance'])
                )
                # Restore the snapshot balance; note that the balance will be recomputed once transactions are loaded.
                account.account_balance = Decimal(row['account_balance'])
                # In a more advanced system, you would also parse created_at and updated_at
                account.created_at = datetime.fromisoformat(row['created_at'])
                account.updated_at = datetime.fromisoformat(row['updated_at'])
                accounts[account.account_id] = account
    except FileNotFoundError:
        # If file not found, return an empty dict.
        pass
    return accounts

def load_transactions(accounts, filename='transactions.csv'):
    """
    Load transactions from CSV and assign them to the corresponding accounts.
    This assumes that the account dictionary has been loaded (or created) first.
    """
    filepath = get_file_path(filename)
    try:
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            from entities import Transaction  # delayed import to avoid circular dependency
            for row in reader:
                txn = Transaction(
                    txn_type=row['txn_type'],
                    txn_status=row['txn_status'],
                    amount=Decimal(row['amount']),
                    description=row['description'],
                    timestamp=datetime.fromisoformat(row['timestamp'])
                )
                account_id = row['account_id']
                if account_id in accounts:
                    accounts[account_id].apply_transaction(txn)
    except FileNotFoundError:
        pass
