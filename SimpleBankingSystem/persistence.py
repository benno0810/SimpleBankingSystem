# persistence.py
import csv
import os
from tempfile import NamedTemporaryFile

def save_accounts(accounts, filename='accounts.csv'):
    """
    Save account summaries into a CSV file.
    Each account is represented by its id, name, initial_balance, current_balance,
    created_at and updated_at.
    """
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
    os.replace(temp_file.name, filename)

def save_transactions(accounts, filename='transactions.csv'):
    """
    Save all transactions from all accounts into a CSV file.
    Each row represents one transaction, along with its account_id.
    """
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
                    txn.timestamp.isoformat()
                ])
    os.replace(temp_file.name, filename)

def load_accounts(filename='accounts.csv'):
    """
    Read account data from a CSV file and return a dictionary of BankAccount objects.
    (Implementation detail: You must recreate your BankAccount from the CSV data.)
    """
    from entities import BankAccount  # Import here to avoid circular dependency if needed.
    accounts = {}
    try:
        with open(filename, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Create a new BankAccount; note that account_balance is computed via transactions,
                # but we record it here as a snapshot.
                account = BankAccount(
                    account_id=row['account_id'],
                    account_name=row['account_name'],
                    initial_balance=row['initial_balance']
                )
                account.account_balance = row['account_balance']  # stored as string—convert if necessary
                # You can also parse created_at and updated_at if needed.
                accounts[account.account_id] = account
    except FileNotFoundError:
        # If file not found, return empty accounts dictionary.
        pass
    return accounts

def load_transactions(accounts, filename='transactions.csv'):
    """
    Load transactions from CSV and assign them to the corresponding accounts.
    (This assumes that an account already exists in the accounts dictionary.)
    """
    from entities import Transaction
    try:
        with open(filename, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Assuming that Transaction() accepts amount as a number (Decimal or float)
                txn = Transaction(
                    txn_type=row['txn_type'],
                    txn_status=row['txn_status'],
                    amount=row['amount'],  # conversion may be needed
                    description=row['description'],
                    timestamp=row['timestamp']  # conversion to datetime if needed
                )
                account_id = row['account_id']
                if account_id in accounts:
                    accounts[account_id].apply_transaction(txn)
    except FileNotFoundError:
        pass
