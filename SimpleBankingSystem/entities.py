# entities.py
from datetime import datetime, timezone
from decimal import Decimal, getcontext
import uuid
from threading import Lock
from SimpleBankingSystem.constants import TransactionType, TransactionStatus
from SimpleBankingSystem.transaction_log import TransactionLog
from typing import List, Optional
from SimpleBankingSystem.models import Transaction

getcontext().prec = 2  # Precision up to cents

# Create a single transaction log instance
transaction_log = TransactionLog()

class Transaction:
    def __init__(self, txn_type: TransactionType, txn_status: TransactionStatus, amount: Decimal, description: str = ""):
        self.transaction_id = str(uuid.uuid4())
        self.txn_type = txn_type
        self.txn_status = txn_status
        self.amount = amount
        self.description = description
        self.timestamp = datetime.now(timezone.utc)
        self.error_message = None
        self.balance_updated = False  # Track if this transaction has affected the balance

    def get_effective_amount(self):
        """Return the amount with the correct sign based on transaction type"""
        if self.txn_type == TransactionType.WITHDRAW:
            return -self.amount
        return self.amount

    def update_status(self, new_status: TransactionStatus, error_message: Optional[str] = None):
        """Update the transaction status and optionally set an error message."""
        self.txn_status = new_status
        if error_message:
            self.error_message = error_message

    def __repr__(self):
        return f"Transaction(id={self.transaction_id}, type={self.txn_type}, status={self.txn_status}, amount={self.amount}, timestamp={self.timestamp})"

class BankAccount:
    def __init__(self, account_id: str, name: str, initial_balance: Decimal = Decimal('0.00')):
        self.account_id = account_id
        self.name = name
        self.initial_balance = initial_balance
        self.account_balance = initial_balance
        self.transactions: List[Transaction] = []
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        self._lock = Lock()
        self._transaction_limit = 1000

    def apply_transaction(self, transaction: Transaction) -> None:
        """Apply a transaction to the account"""
        with self._lock:
            if transaction.txn_status == TransactionStatus.COMPLETED:
                self.account_balance += transaction.amount
            # Simply append to transactions queue
            self.transactions.append(transaction)
            self.updated_at = datetime.now(timezone.utc)
            
            # Archive old transactions if we exceed the limit
            if len(self.transactions) > self._transaction_limit:
                self._archive_transactions()

    def _archive_transactions(self) -> None:
        """Archive old transactions to keep memory usage under control"""
        with self._lock:
            # Separate completed and uncompleted transactions
            completed_txns = [txn for txn in self.transactions if txn.txn_status == TransactionStatus.COMPLETED]
            uncompleted_txns = [txn for txn in self.transactions if txn.txn_status != TransactionStatus.COMPLETED]
            
            # Calculate how many completed transactions we can keep
            remaining_slots = self._transaction_limit - len(uncompleted_txns)
            
            if remaining_slots > 0:
                # Sort completed transactions by timestamp before archiving
                completed_txns.sort(key=lambda txn: txn.timestamp)
                # Keep the most recent completed transactions
                recent_completed = completed_txns[-remaining_slots:]
                # Get transactions to be archived
                to_archive = completed_txns[:-remaining_slots]
                
                # Persist archived transactions
                if to_archive:
                    from SimpleBankingSystem.persistence import save_archived_transactions
                    save_archived_transactions(self.account_id, to_archive)
                
                self.transactions = uncompleted_txns + recent_completed
            else:
                # If we have more uncompleted transactions than the limit, keep them all
                self.transactions = uncompleted_txns

    def get_balance(self) -> Decimal:
        """Get the current account balance"""
        with self._lock:
            return self.account_balance

    def get_statement(self, limit: Optional[int] = None, offset: int = 0) -> List[dict]:
        """Get account statement with pagination, including archived transactions"""
        with self._lock:
            # Sort in-memory transactions by timestamp
            sorted_in_memory = sorted(self.transactions, key=lambda txn: txn.timestamp)
            in_memory_txns = sorted_in_memory[offset:offset + limit] if limit else sorted_in_memory
            
            # If we need more transactions, load from archive
            if limit and len(in_memory_txns) < limit:
                from SimpleBankingSystem.persistence import load_archived_transactions
                archived_txns = load_archived_transactions(self.account_id, limit - len(in_memory_txns), offset)
                # Merge and sort transactions
                all_txns = in_memory_txns + archived_txns
                all_txns.sort(key=lambda txn: txn.timestamp)
                in_memory_txns = all_txns[:limit]
            
            return [{
                'timestamp': txn.timestamp.isoformat(),
                'type': txn.txn_type.name,
                'amount': float(txn.amount),
                'balance_after': float(self.get_balance_at(txn.timestamp)),
                'description': txn.description,
                'status': txn.txn_status.name
            } for txn in in_memory_txns]

    def get_balance_at(self, timestamp: datetime) -> Decimal:
        """Get the account balance at a specific timestamp"""
        with self._lock:
            balance = self.initial_balance
            # Get all transactions up to the timestamp
            all_txns = self.transactions + self._get_archived_transactions_before(timestamp)
            # Sort all transactions by timestamp
            all_txns.sort(key=lambda txn: txn.timestamp)
            
            for txn in all_txns:
                if txn.timestamp <= timestamp and txn.txn_status == TransactionStatus.COMPLETED:
                    balance += txn.amount
            return balance

    def _get_archived_transactions_before(self, timestamp: datetime) -> List[Transaction]:
        """Get archived transactions before a specific timestamp"""
        from SimpleBankingSystem.persistence import load_archived_transactions
        # Load all archived transactions and filter by timestamp
        archived_txns = load_archived_transactions(self.account_id, float('inf'), 0)
        return [txn for txn in archived_txns if txn.timestamp <= timestamp]

    def get_transaction_count(self) -> int:
        """Get the total number of transactions including archived ones"""
        with self._lock:
            from SimpleBankingSystem.persistence import get_archived_transaction_count
            return len(self.transactions) + get_archived_transaction_count(self.account_id)

    def __repr__(self):
        return f"Account(id={self.account_id}, name={self.name}, balance={self.get_balance()}, updated_at={self.updated_at})"
