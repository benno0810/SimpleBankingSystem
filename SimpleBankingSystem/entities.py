# entities.py
from datetime import datetime, timezone
from decimal import Decimal, getcontext
import uuid
getcontext().prec = 2  # Precision up to cents

class Transaction:
    def __init__(self, txn_type, txn_status, amount, description="", timestamp=None):
        self.txn_type = txn_type
        self.txn_status = txn_status
        self.amount = Decimal(amount)
        self.description = description
        self.timestamp = timestamp if timestamp else datetime.now(timezone.utc)

    def __repr__(self):
        return f"Transaction: {self.txn_type}, Status: {self.txn_status}, Amount: {self.amount}, Timestamp: {self.timestamp}"

class BankAccount:
    def __init__(self, account_name, initial_balance):
        self.account_id = uuid.uuid4()
        self.account_name = account_name
        self.initial_balance = Decimal(initial_balance)
        self.account_balance = self.initial_balance
        self.transactions = []
        from datetime import datetime, timezone
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at

    def apply_transaction(self, transaction: Transaction):
        from constants import TransactionStatus
        self.updated_at = transaction.timestamp 
        self.transactions.append(transaction)
        if transaction.txn_status == TransactionStatus.COMPLETED:
            self.account_balance += transaction.amount

    def get_balance(self):
        # Optionally compute on the fly:
        finalized_amount = sum(txn.amount for txn in self.transactions if txn.txn_status == "COMPLETED")
        return self.initial_balance + finalized_amount

    def get_statement(self):
        running_balance = self.initial_balance
        statement = []
        for txn in sorted(self.transactions, key=lambda t: t.timestamp):
            if txn.txn_status == "COMPLETED":
                running_balance += txn.amount
            statement.append({
                'timestamp': txn.timestamp,
                'type': txn.txn_type,
                'amount': txn.amount,
                'balance_after': running_balance,
                'description': txn.description,
                'status': txn.txn_status,
            })
        return statement

    def __repr__(self):
        return f"Account: {self.account_name}, Balance: {self.get_balance()}, Updated At: {self.updated_at}"
