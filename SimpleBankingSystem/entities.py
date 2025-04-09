# entities.py
from datetime import datetime, timezone
from decimal import Decimal, getcontext
import uuid
getcontext().prec = 2  # Precision up to cents

class Transaction:
    def __init__(self, txn_type, txn_status, amount, description="", timestamp=None):
        self.transaction_id = str(uuid.uuid4())
        self.txn_type = txn_type
        self.txn_status = txn_status
        self.amount = Decimal(amount)
        self.description = description
        self.timestamp = timestamp if timestamp else datetime.now(timezone.utc)
        self.error_message = None

    def update_status(self, new_status, error_message=None):
        """Update the transaction status and optionally set an error message."""
        self.txn_status = new_status
        if error_message:
            self.error_message = error_message

    def __repr__(self):
        return f"Transaction(id={self.transaction_id}, type={self.txn_type}, status={self.txn_status}, amount={self.amount}, timestamp={self.timestamp})"

class BankAccount:
    def __init__(self, account_name, initial_balance):
        self.account_id = str(uuid.uuid4())
        self.account_name = account_name
        self.initial_balance = Decimal(initial_balance)
        self.account_balance = self.initial_balance
        self.transactions = []
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at

    def apply_transaction(self, transaction: Transaction):
        """Apply a transaction to the account, handling different transaction states."""
        from constants import TransactionStatus
        
        self.updated_at = transaction.timestamp
        
        if transaction.txn_status == TransactionStatus.PENDING:
            # Queue the transaction for processing
            self.transactions.append(transaction)
            
        elif transaction.txn_status == TransactionStatus.PROCESSING:
            # Transaction is being processed
            self.transactions.append(transaction)
            
        elif transaction.txn_status == TransactionStatus.COMPLETED:
            # Transaction is completed, update balance
            self.transactions.append(transaction)
            self.account_balance += transaction.amount
            
        elif transaction.txn_status == TransactionStatus.FAILED:
            # Transaction failed, log it but don't update balance
            self.transactions.append(transaction)

    def get_balance(self):
        """Get the current account balance, considering only completed transactions."""
        from constants import TransactionStatus
        completed_amount = sum(
            txn.amount for txn in self.transactions 
            if txn.txn_status == TransactionStatus.COMPLETED
        )
        return self.initial_balance + completed_amount

    def get_statement(self):
        """Get account statement with transaction history and running balance."""
        from constants import TransactionStatus
        running_balance = self.initial_balance
        statement = []
        
        for txn in sorted(self.transactions, key=lambda t: t.timestamp):
            if txn.txn_status == TransactionStatus.COMPLETED:
                running_balance += txn.amount
                
            statement.append({
                'transaction_id': txn.transaction_id,
                'timestamp': txn.timestamp,
                'type': txn.txn_type,
                'amount': txn.amount,
                'balance_after': running_balance,
                'description': txn.description,
                'status': txn.txn_status,
                'error_message': txn.error_message
            })
            
        return statement

    def __repr__(self):
        return f"Account(id={self.account_id}, name={self.account_name}, balance={self.get_balance()}, updated_at={self.updated_at})"
