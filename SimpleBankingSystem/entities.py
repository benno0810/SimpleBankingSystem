# entities.py
from typing import Dict, List, Optional, Set, Callable, Tuple
from decimal import Decimal
from datetime import datetime, timezone
import uuid
import threading
import os
import json
import csv
from tempfile import NamedTemporaryFile
from enum import Enum, auto
from SimpleBankingSystem.constants import TransactionType, TransactionStatus, MAX_ACTIVE_TRANSACTIONS, ARCHIVE_KEEP_COUNT, MAX_TRANSACTION_RETRIES
from SimpleBankingSystem.logger import logger
from SimpleBankingSystem.utils import validate_positive_whole_cents

class TransactionEvent(Enum):
    START_PROCESSING = auto()
    COMPLETE = auto()
    FAIL = auto()
    RETRY = auto()
    CANCEL = auto()

class TransactionStateMachine:
    """State machine for managing transaction lifecycle."""
    
    _valid_transitions = {
        TransactionStatus.PENDING: {
            TransactionEvent.START_PROCESSING: TransactionStatus.PROCESSING,
            TransactionEvent.CANCEL: TransactionStatus.FAILED
        },
        TransactionStatus.PROCESSING: {
            TransactionEvent.COMPLETE: TransactionStatus.COMPLETED,
            TransactionEvent.FAIL: TransactionStatus.FAILED,
            TransactionEvent.CANCEL: TransactionStatus.FAILED
        },
        TransactionStatus.FAILED: {
            TransactionEvent.RETRY: TransactionStatus.PENDING
        },
        TransactionStatus.COMPLETED: {}
    }

    def __init__(self, initial_state: TransactionStatus = TransactionStatus.PENDING):
        self._state = initial_state
        self._lock = threading.Lock()
        self._state_handlers: Dict[TransactionStatus, Set[Callable]] = {
            state: set() for state in TransactionStatus
        }

    def add_state_handler(self, state: TransactionStatus, handler: Callable):
        """Add a handler for a specific state."""
        self._state_handlers[state].add(handler)

    def remove_state_handler(self, state: TransactionStatus, handler: Callable):
        """Remove a handler for a specific state."""
        self._state_handlers[state].discard(handler)

    def transition(self, event: TransactionEvent) -> bool:
        """Attempt to transition to a new state based on the event."""
        with self._lock:
            if event not in self._valid_transitions[self._state]:
                logger.warning(f"Invalid transition from {self._state} with event {event}")
                raise ValueError(f"Invalid transition from {self._state} with event {event}")
            
            new_state = self._valid_transitions[self._state][event]
            old_state = self._state
            self._state = new_state
            
            # Notify state handlers
            for handler in self._state_handlers[new_state]:
                try:
                    handler(old_state, new_state)
                except Exception as e:
                    logger.error(f"Error in state handler: {str(e)}")
            
            logger.info(f"Transaction state changed from {old_state} to {new_state}")
            return True

    @property
    def state(self) -> TransactionStatus:
        return self._state

class Transaction:
    """Represents a financial transaction in the banking system."""
    
    def __init__(self, txn_type: TransactionType, amount: Decimal, account_id: str):
        self.transaction_id = str(uuid.uuid4())
        self.txn_type = txn_type
        self.amount = amount
        self.account_id = account_id
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = self.created_at
        self.retry_count = 0
        self.max_retries = MAX_TRANSACTION_RETRIES
        self.state_machine = TransactionStateMachine()
        
    @property
    def txn_status(self) -> TransactionStatus:
        """Get the current transaction status."""
        return self.state_machine.state
        
    def get_account(self) -> Optional['BankAccount']:
        """Get the associated bank account for this transaction."""
        from SimpleBankingSystem.commands import load_accounts
        accounts = load_accounts()
        return accounts.get(self.account_id)
        
    def start_processing(self) -> bool:
        """Start processing the transaction.
        
        Returns:
            bool: True if processing started successfully
            
        Raises:
            ValueError: If the transaction is not in a valid state for processing
        """
        self.state_machine.transition(TransactionEvent.START_PROCESSING)
        self.updated_at = datetime.now(timezone.utc)
        return True
            
    def complete(self) -> bool:
        """Complete the transaction.
        
        Returns:
            bool: True if transaction was completed successfully
            
        Raises:
            ValueError: If the transaction is not in a valid state for completion
        """
        self.state_machine.transition(TransactionEvent.COMPLETE)
        self.updated_at = datetime.now(timezone.utc)
        return True
            
    def fail(self) -> bool:
        """Fail the transaction.
        
        Returns:
            bool: True if transaction was failed successfully
            
        Raises:
            ValueError: If the transaction is not in a valid state for failing
        """
        self.state_machine.transition(TransactionEvent.FAIL)
        self.updated_at = datetime.now(timezone.utc)
        return True
            
    def retry(self) -> bool:
        """Retry a failed transaction.
        
        Returns:
            bool: True if retry was successful
            
        Raises:
            ValueError: If the transaction has reached maximum retry count
                      or is not in a valid state for retry
        """
        if self.retry_count >= self.max_retries:
            raise ValueError(f"Transaction {self.transaction_id} has reached maximum retry count")
            
        self.state_machine.transition(TransactionEvent.RETRY)
        self.retry_count += 1
        self.updated_at = datetime.now(timezone.utc)
        return True
            
    def cancel(self) -> bool:
        """Cancel the transaction.
        
        Returns:
            bool: True if transaction was cancelled successfully
            
        Raises:
            ValueError: If the transaction is not in a valid state for cancellation
        """
        self.state_machine.transition(TransactionEvent.CANCEL)
        self.updated_at = datetime.now(timezone.utc)
        return True

    def to_dict(self) -> dict:
        """Convert transaction to dictionary for persistence."""
        return {
            'transaction_id': self.transaction_id,
            'txn_type': self.txn_type.name,
            'amount': str(self.amount),
            'txn_status': self.txn_status.name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'account_id': self.account_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Transaction':
        """Create transaction from dictionary."""
        txn = cls(
            txn_type=TransactionType[data['txn_type']],
            amount=Decimal(data['amount']),
            account_id=data['account_id']
        )
        txn.transaction_id = data['transaction_id']
        txn.created_at = datetime.fromisoformat(data['created_at'])
        txn.updated_at = datetime.fromisoformat(data['updated_at'])
        txn.retry_count = data.get('retry_count', 0)
        txn.max_retries = data.get('max_retries', MAX_TRANSACTION_RETRIES)
        # Set initial state from txn_status
        txn.state_machine = TransactionStateMachine(initial_state=TransactionStatus[data['txn_status']])
        return txn

class TransactionManager:
    """Manages transactions for a bank account"""
    
    def __init__(self):
        """Initialize the transaction manager"""
        self._transactions: List[Transaction] = []
        self._lock = threading.Lock()
        
    def add_transaction(self, transaction: Transaction) -> bool:
        """Add a transaction to the manager"""
        with self._lock:
            self._transactions.append(transaction)
            return True
            
    def get_transactions(self) -> Tuple[Transaction, ...]:
        """Get all transactions"""
        with self._lock:
            return tuple(self._transactions)  # Return a tuple to ensure immutability
            
    def get_transactions_by_status(self, status: TransactionStatus) -> List[Transaction]:
        """Get all transactions with a specific status"""
        with self._lock:
            return [txn for txn in self._transactions if txn.txn_status == status]
            
    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get a specific transaction by ID."""
        with self._lock:
            return next((t for t in self._transactions if t.transaction_id == transaction_id), None)
            
    def update_transaction_status(self, transaction_id: str, event: TransactionEvent) -> bool:
        """Update a transaction's status."""
        with self._lock:
            # Find the transaction
            transaction = next((t for t in self._transactions if t.transaction_id == transaction_id), None)
            if not transaction:
                return False
                
            # Update transaction status
            if event == TransactionEvent.COMPLETE:
                return transaction.complete()
            elif event == TransactionEvent.FAIL:
                return transaction.fail()
            elif event == TransactionEvent.START_PROCESSING:
                return transaction.start_processing()
            elif event == TransactionEvent.RETRY:
                return transaction.retry()
            elif event == TransactionEvent.CANCEL:
                return transaction.cancel()
                    
            return True
            
    def clear(self):
        """Clear all transactions"""
        with self._lock:
            self._transactions.clear()

class BankAccount:
    def __init__(self, name: str, initial_balance: Decimal, base_dir: str = None, account_id: str = None, created_at: datetime = None):
        self._account_id = account_id if account_id is not None else str(uuid.uuid4())
        self.name = name
        self.account_balance = initial_balance
        self._created_at = created_at if created_at is not None else datetime.now(timezone.utc)
        self._updated_at = self._created_at  # Initialize updated_at to created_at
        self.base_dir = base_dir or os.getcwd()
        self._lock = threading.Lock()
        self._transaction_manager = TransactionManager()
        
        # Validate initial balance
        if initial_balance < 0:
            raise ValueError("Initial balance cannot be negative")
        if initial_balance % Decimal('0.01') != 0:
            raise ValueError("Initial balance must be in whole cents")

        self._ensure_directory_exists()
        logger.info(f"Created new account: id={self._account_id}, name={name}, initial_balance={initial_balance}")

    @property
    def account_id(self) -> str:
        """Read-only property for account_id"""
        return self._account_id

    @account_id.setter
    def account_id(self, value):
        """Prevent modification of account_id after creation"""
        raise AttributeError("account_id cannot be modified after creation")

    @property
    def created_at(self) -> datetime:
        """Read-only property for created_at"""
        return self._created_at

    @created_at.setter
    def created_at(self, value: datetime):
        """Prevent modification of created_at after creation"""
        raise AttributeError("created_at cannot be modified after creation")

    @property
    def updated_at(self) -> datetime:
        """Get the last update timestamp"""
        return self._updated_at

    @updated_at.setter
    def updated_at(self, value: datetime):
        """Set the last update timestamp"""
        self._updated_at = value

    def _ensure_directory_exists(self):
        """Ensure the base directory exists"""
        try:
            if not os.path.exists(self.base_dir):
                os.makedirs(self.base_dir)
                logger.info(f"Created base directory: {self.base_dir}")
        except Exception as e:
            logger.error(f"Failed to create base directory {self.base_dir}: {str(e)}")
            raise

    def get_balance(self) -> Decimal:
        with self._lock:
            balance = self.account_balance
            logger.debug(f"Retrieved balance for account {self.account_id}: {balance}")
            return balance

    def get_balance_at(self, timestamp: datetime) -> Decimal:
        with self._lock:
            balance = Decimal('0.00')
            for txn in self._transaction_manager.get_transactions():
                if txn.created_at <= timestamp and txn.txn_status == TransactionStatus.COMPLETED:
                    if txn.txn_type == TransactionType.DEPOSIT or txn.txn_type == TransactionType.TRANSFER_IN:
                        balance += txn.amount
                    elif txn.txn_type == TransactionType.WITHDRAW or txn.txn_type == TransactionType.TRANSFER_OUT:
                        balance -= txn.amount
            logger.debug(f"Retrieved historical balance for account {self.account_id} at {timestamp}: {balance}")
            return balance

    def calculate_effective_amount(self, transaction: Transaction) -> Decimal:
        """Calculate the effective amount to apply to the balance based on transaction type."""
        if transaction.txn_type == TransactionType.DEPOSIT or transaction.txn_type == TransactionType.TRANSFER_IN:
            return transaction.amount
        elif transaction.txn_type == TransactionType.WITHDRAW or transaction.txn_type == TransactionType.TRANSFER_OUT:
            return -transaction.amount
        else:
            raise ValueError("Invalid transaction type")

    def add_transaction(self, transaction: Transaction) -> bool:
        """Add a transaction to the account's transaction manager."""
        with self._lock:
            transaction.account_id = self.account_id
            success = self._transaction_manager.add_transaction(transaction)
            if success:
                self._update_timestamp()  # Update timestamp when adding a transaction
            return success

    def _update_timestamp(self):
        """Update the updated_at timestamp to current time"""
        self.updated_at = datetime.now(timezone.utc)

    def update_transaction_status(self, transaction_id: str, event: TransactionEvent) -> bool:
        """Update a transaction's status and handle balance updates if needed."""
        with self._lock:
            # Update transaction status
            if not self._transaction_manager.update_transaction_status(transaction_id, event):
                return False
                
            # If transaction was completed, update balance
            if event == TransactionEvent.COMPLETE:
                transaction = self._transaction_manager.get_transaction(transaction_id)
                if transaction:
                    effective_amount = self.calculate_effective_amount(transaction)
                    self.account_balance += effective_amount
                    self._update_timestamp()  # Update timestamp when balance changes
                    
            return True

    def get_transactions(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[Transaction]:
        """Get all transactions for the account."""
        with self._lock:
            transactions = (
                self._transaction_manager.get_transactions_by_status(TransactionStatus.PENDING) +
                self._transaction_manager.get_transactions_by_status(TransactionStatus.COMPLETED) +
                self._transaction_manager.get_transactions_by_status(TransactionStatus.FAILED)
            )
            
            if start_time:
                transactions = [t for t in transactions if t.created_at >= start_time]
            if end_time:
                transactions = [t for t in transactions if t.created_at <= end_time]
            
            return sorted(transactions, key=lambda t: t.created_at)

    def to_dict(self) -> dict:
        """Convert account to dictionary for persistence"""
        return {
            'account_id': self.account_id,
            'name': self.name,
            'balance': str(self.account_balance),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'transactions': [t.to_dict() for t in self.get_transactions()]
        }

    @classmethod
    def from_dict(cls, data: dict, base_dir: str = "data") -> 'BankAccount':
        """Create account from dictionary"""
        account = cls(
            name=data['name'],
            initial_balance=Decimal(data['balance']),
            base_dir=base_dir,
            account_id=data['account_id'],
            created_at=datetime.fromisoformat(data['created_at'])
        )
        # Set updated_at if it exists in the data, otherwise use created_at
        account._updated_at = datetime.fromisoformat(data.get('updated_at', data['created_at']))
        return account

    @property
    def transactions(self) -> List[Transaction]:
        """Get a copy of the transactions list"""
        return self.get_transactions()

    def generate_statement(self, start_date: datetime = None, end_date: datetime = None) -> str:
        """
        Generate an account statement for the specified date range.
        
        Args:
            start_date: Start date for the statement (inclusive)
            end_date: End date for the statement (inclusive)
            
        Returns:
            str: Formatted account statement
        """
        if start_date is None:
            start_date = self.created_at
        if end_date is None:
            end_date = datetime.now(timezone.utc)
            
        # Get all transactions (including archived)
        all_transactions = self.get_transactions(start_date, end_date)
        
        # Sort transactions by created_at
        all_transactions.sort(key=lambda x: x.created_at)
        
        # Generate statement
        statement = [
            f"Account Statement for {self.name}",
            f"Account ID: {self.account_id}",
            f"Period: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Current Balance: ${self.account_balance:.2f}",
            "\nTransactions:",
            "Date\t\tType\t\tAmount\t\tStatus"
        ]
        
        for txn in all_transactions:
            statement.append(
                f"{txn.created_at.strftime('%Y-%m-%d %H:%M:%S')}\t"
                f"{txn.txn_type.name}\t"
                f"${txn.amount:.2f}\t\t"
                f"{txn.txn_status.name}"
            )
        
        return "\n".join(statement)

    def save_statement(self, start_date: datetime = None, end_date: datetime = None, filename: str = None) -> str:
        """
        Save account statement to a file.
        
        Args:
            start_date: Start date for the statement (inclusive)
            end_date: End date for the statement (inclusive)
            filename: Optional filename to save the statement
            
        Returns:
            str: Path to the saved statement file
        """
        if filename is None:
            filename = f"statement_{self.account_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
        
        # Ensure statements directory exists
        statements_dir = os.path.join(self.base_dir, 'statements')
        os.makedirs(statements_dir, exist_ok=True)
        
        # Generate and save statement
        statement = self.generate_statement(start_date, end_date)
        filepath = os.path.join(statements_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write(statement)
            
        return filepath

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get a specific transaction by ID."""
        with self._lock:
            return self._transaction_manager.get_transaction(transaction_id)
