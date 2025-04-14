# commands.py
from abc import ABC, abstractmethod
from SimpleBankingSystem.entities import Transaction, BankAccount, TransactionEvent, TransactionManager, TransactionStateMachine
from SimpleBankingSystem.constants import TransactionType, TransactionStatus, ACCOUNTS_FILE, TRANSACTIONS_FILE, ARCHIVED_TRANSACTIONS_FILE
from SimpleBankingSystem.logger import logger
import uuid
from decimal import Decimal
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
import json
import os
import csv
from tempfile import NamedTemporaryFile
from SimpleBankingSystem.utils import validate_positive_whole_cents
import threading

def load_accounts() -> Dict[str, BankAccount]:
    """
    Load accounts and their active transactions from CSV files.
    
    Returns:
        Dictionary of accounts with their active transactions loaded.
    """
    accounts = {}
    try:
        # Load accounts
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Create account with the existing account_id and created_at
                    account = BankAccount(
                        name=row['name'],
                        initial_balance=Decimal(row['balance']),
                        account_id=row['account_id'],
                        created_at=datetime.fromisoformat(row['created_at']) if 'created_at' in row else None
                    )
                    # Set updated_at if it exists in the data, otherwise use created_at
                    if 'updated_at' in row:
                        account.updated_at = datetime.fromisoformat(row['updated_at'])
                    accounts[row['account_id']] = account
            logger.info(f"Loaded {len(accounts)} accounts from {ACCOUNTS_FILE}")
        
        # Load active transactions
        if os.path.exists(TRANSACTIONS_FILE):
            with open(TRANSACTIONS_FILE, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    account = accounts.get(row['account_id'])
                    if account:
                        txn = Transaction(
                            txn_type=TransactionType[row['txn_type']],
                            amount=Decimal(row['amount']),
                            account_id=row['account_id']
                        )
                        txn.transaction_id = row['transaction_id']
                        txn.created_at = datetime.fromisoformat(row['created_at'])
                        txn.updated_at = datetime.fromisoformat(row['updated_at'])
                        # Set the status using the state machine
                        status = TransactionStatus[row['txn_status']]
                        if status == TransactionStatus.COMPLETED:
                            # For completed transactions, we need to go through the proper state transitions
                            txn.state_machine.transition(TransactionEvent.START_PROCESSING)
                            txn.state_machine.transition(TransactionEvent.COMPLETE)
                        elif status == TransactionStatus.FAILED:
                            txn.state_machine.transition(TransactionEvent.START_PROCESSING)
                            txn.state_machine.transition(TransactionEvent.FAIL)
                        elif status == TransactionStatus.PROCESSING:
                            txn.state_machine.transition(TransactionEvent.START_PROCESSING)
                        elif status == TransactionStatus.PENDING:
                            # PENDING is the initial state, no transition needed
                            pass
                        account.add_transaction(txn)
            logger.info(f"Loaded active transactions from {TRANSACTIONS_FILE}")
            
    except Exception as e:
        logger.error(f"Error loading system state: {str(e)}")
        raise
    
    return accounts

def save_accounts(accounts: Dict[str, BankAccount]) -> None:
    """Save accounts to disk."""
    try:
        # Save accounts to CSV
        with open(ACCOUNTS_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['account_id', 'name', 'balance', 'created_at', 'updated_at'])
            writer.writeheader()
            for account in accounts.values():
                writer.writerow({
                    'account_id': account.account_id,
                    'name': account.name,
                    'balance': str(account.account_balance),
                    'created_at': account.created_at.isoformat(),
                    'updated_at': account.updated_at.isoformat()
                })
            
        # Save transactions to CSV
        with open(TRANSACTIONS_FILE, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'transaction_id', 'account_id', 'txn_type', 'amount', 
                'txn_status', 'created_at', 'updated_at', 'retry_count', 
                'max_retries'
            ])
            writer.writeheader()
            for account in accounts.values():
                for txn in account.transactions:
                    writer.writerow({
                        'transaction_id': txn.transaction_id,
                        'account_id': txn.account_id,
                        'txn_type': txn.txn_type.name,
                        'amount': str(txn.amount),
                        'txn_status': txn.txn_status.name,
                        'created_at': txn.created_at.isoformat(),
                        'updated_at': txn.updated_at.isoformat(),
                        'retry_count': txn.retry_count,
                        'max_retries': txn.max_retries
                    })
            
    except Exception as e:
        logger.error(f"Error saving system state: {str(e)}")
        raise

'''
Transaction lifecycle:
1. Create transaction
2. Process transaction
3. Complete transaction
4. Fail transaction
cucrrently it's resides in single methods, but we can make it async by using another process monitor and update the status alone
'''
class BaseCommand(ABC):
    @abstractmethod
    def execute(self, accounts: Dict[str, BankAccount]) -> Dict[str, Any]:
        """Perform the command action."""
        pass
    
    def save_state(self, accounts: Dict[str, BankAccount]):
        """Save the current state of all accounts to CSV files."""
        save_accounts(accounts)


class CreateAccountCommand(BaseCommand):
    def __init__(self, name: str, initial_balance: Decimal):
        self.name = name
        self.initial_balance = initial_balance
        logger.info(f"Initialized CreateAccountCommand: name={name}, initial_balance={initial_balance}")

    def execute(self, accounts: Optional[Dict[str, BankAccount]] = None) -> Dict[str, Any]:
        if self.initial_balance < 0:
            logger.error(f"Attempted to create account with negative balance: {self.initial_balance}")
            raise ValueError("Initial balance cannot be negative.")
        
        if accounts is None:
            accounts = load_accounts()
            
        # Create account with auto-generated UUID
        account = BankAccount(
            name=self.name,
            initial_balance=self.initial_balance
        )
        accounts[str(account.account_id)] = account
        logger.info(f"Created new account: {account.account_id}")
        self.save_state(accounts)
        
        # Return account information as a dictionary
        return {
            'account_id': str(account.account_id),
            'name': account.name,
            'balance': account.account_balance,
            'created_at': account.created_at.isoformat(),
            'updated_at': account.updated_at.isoformat()
        }

class DepositCommand(BaseCommand):
    def __init__(self, account: BankAccount, amount: Decimal):
        super().__init__()
        self.account = account
        self.amount = amount
        self.transaction = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=amount,
            account_id=account.account_id
        )

    def execute(self, accounts: Optional[Dict[str, BankAccount]] = None) -> dict:
        try:
            # Add transaction to account first
            if not self.account.add_transaction(self.transaction):
                raise Exception("Failed to add transaction to account")
            
            # Start processing the transaction
            if not self.transaction.start_processing():
                raise Exception("Failed to start processing transaction")
            
            # Complete the transaction and update balance
            if not self.account.update_transaction_status(
                self.transaction.transaction_id,
                TransactionEvent.COMPLETE
            ):
                raise Exception("Failed to complete transaction")
            
            return {
                'success': True,
                'transaction_id': self.transaction.transaction_id,
                'status': self.transaction.txn_status.name,
                'created_at': self.transaction.created_at.isoformat(),
                'updated_at': self.transaction.updated_at.isoformat(),
                'new_balance': self.account.get_balance()
            }
        except Exception as e:
            # If anything fails, mark the transaction as failed
            self.account.update_transaction_status(
                self.transaction.transaction_id,
                TransactionEvent.FAIL
            )
            raise

class WithdrawCommand(BaseCommand):
    def __init__(self, account: BankAccount, amount: Decimal):
        super().__init__()
        self.account = account
        self.amount = amount
        self.transaction = Transaction(
            txn_type=TransactionType.WITHDRAW,
            amount=amount,
            account_id=account.account_id
        )

    def execute(self, accounts: Optional[Dict[str, BankAccount]] = None) -> dict:
        try:
            # Add transaction to account first
            if not self.account.add_transaction(self.transaction):
                raise Exception("Failed to add transaction to account")
            
            # Start processing the transaction
            if not self.transaction.start_processing():
                raise Exception("Failed to start processing transaction")
            
            # Check for sufficient funds
            if self.amount > self.account.account_balance:
                # Mark as failed
                self.account.update_transaction_status(
                    self.transaction.transaction_id,
                    TransactionEvent.FAIL
                )
                raise ValueError("Insufficient funds")
            
            # Complete the transaction and update balance
            if not self.account.update_transaction_status(
                self.transaction.transaction_id,
                TransactionEvent.COMPLETE
            ):
                raise Exception("Failed to complete transaction")
            
            return {
                'success': True,
                'transaction_id': self.transaction.transaction_id,
                'status': self.transaction.txn_status.name,
                'created_at': self.transaction.created_at.isoformat(),
                'updated_at': self.transaction.updated_at.isoformat(),
                'new_balance': self.account.get_balance()
            }
        except Exception as e:
            # If anything fails, mark the transaction as failed
            self.account.update_transaction_status(
                self.transaction.transaction_id,
                TransactionEvent.FAIL
            )
            raise

class TransferCommand(BaseCommand):
    def __init__(self, source_account: BankAccount, target_account: BankAccount, amount: Decimal):
        super().__init__()
        self.source_account = source_account
        self.target_account = target_account
        self.amount = amount
        self.source_txn = Transaction(
            txn_type=TransactionType.TRANSFER_OUT,
            amount=amount,
            account_id=source_account.account_id
        )
        self.target_txn = Transaction(
            txn_type=TransactionType.TRANSFER_IN,
            amount=amount,
            account_id=target_account.account_id
        )

    def execute(self, accounts: Optional[Dict[str, BankAccount]] = None) -> dict:
        try:
            # Add transactions to accounts
            if not self.source_account.add_transaction(self.source_txn):
                raise Exception("Failed to add source transaction")
            if not self.target_account.add_transaction(self.target_txn):
                raise Exception("Failed to add target transaction")
            
            # Start processing both transactions
            if not self.source_txn.start_processing():
                raise Exception("Failed to start processing source transaction")
            if not self.target_txn.start_processing():
                raise Exception("Failed to start processing target transaction")
            
            # Complete both transactions
            if not self.source_account.update_transaction_status(
                self.source_txn.transaction_id,
                TransactionEvent.COMPLETE
            ):
                raise Exception("Failed to complete source transaction")
            if not self.target_account.update_transaction_status(
                self.target_txn.transaction_id,
                TransactionEvent.COMPLETE
            ):
                raise Exception("Failed to complete target transaction")
            
            return {
                'success': True,
                'source_transaction': {
                    'transaction_id': self.source_txn.transaction_id,
                    'status': self.source_txn.txn_status.name,
                    'created_at': self.source_txn.created_at.isoformat(),
                    'updated_at': self.source_txn.updated_at.isoformat()
                },
                'target_transaction': {
                    'transaction_id': self.target_txn.transaction_id,
                    'status': self.target_txn.txn_status.name,
                    'created_at': self.target_txn.created_at.isoformat(),
                    'updated_at': self.target_txn.updated_at.isoformat()
                },
                'source_new_balance': self.source_account.get_balance(),
                'target_new_balance': self.target_account.get_balance()
            }
        except Exception as e:
            # If anything fails, mark both transactions as failed
            self.source_account.update_transaction_status(
                self.source_txn.transaction_id,
                TransactionEvent.FAIL
            )
            self.target_account.update_transaction_status(
                self.target_txn.transaction_id,
                TransactionEvent.FAIL
            )
            raise

class ArchiveTransactionsCommand(BaseCommand):
    """Command to archive transactions for a bank account when the transaction list becomes too long.
    
    TODO: A scheduled Airflow job will handle:
    - Sorting and deduplication of archived transactions
    - Generating and exporting statements
    - Cleaning up old archive files
    """
    
    def __init__(self, account: BankAccount, keep_last: int = 100):
        super().__init__()
        self.account = account
        self.keep_last = keep_last
        
    def execute(self, accounts: Dict[str, BankAccount]) -> Dict:
        """Execute the archive command"""
        try:
            # Get all transactions from the transaction manager
            transactions = self.account.get_transactions()
            
            if len(transactions) <= self.keep_last:
                return {
                    'success': True,
                    'archived_count': 0,
                    'kept_count': len(transactions)
                }
            
            # Sort transactions by created_at
            transactions.sort(key=lambda x: x.created_at)
            
            # Split into transactions to archive and keep
            to_archive = transactions[:-self.keep_last]
            to_keep = transactions[-self.keep_last:]
            
            # Write archived transactions to CSV
            archive_file = os.path.join(self.account.base_dir, 'transactions_archive.csv')
            try:
                # Ensure base directory exists
                os.makedirs(os.path.dirname(archive_file), exist_ok=True)
                
                file_exists = os.path.exists(archive_file)
                with open(archive_file, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=['transaction_id', 'account_id', 'txn_type', 'amount', 'txn_status', 'created_at', 'updated_at'])
                    if not file_exists:
                        writer.writeheader()
                    
                    for txn in to_archive:
                        writer.writerow({
                            'transaction_id': txn.transaction_id,
                            'account_id': self.account.account_id,
                            'txn_type': txn.txn_type.name,
                            'amount': str(txn.amount),
                            'txn_status': txn.txn_status.name,
                            'created_at': txn.created_at.isoformat(),
                            'updated_at': txn.updated_at.isoformat()
                        })
                
                # Clear the transaction manager's state
                self.account._transaction_manager = TransactionManager()
                
                # Add back the transactions we want to keep
                for txn in to_keep:
                    self.account.add_transaction(txn)
                
                # Save updated state
                self.save_state(accounts)
                
                return {
                    'success': True,
                    'archived_count': len(to_archive),
                    'kept_count': len(to_keep)
                }
                
            except Exception as e:
                logger.error(f"Error archiving transactions: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Error executing archive command: {str(e)}")
            raise

class RetryTransactionCommand(BaseCommand):
    """Command to retry a failed transaction"""
    
    def __init__(self, transaction: Transaction):
        """
        Initialize the retry command.
        
        Args:
            transaction: Transaction to retry
        """
        super().__init__()
        self.transaction = transaction
        
    def execute(self, accounts: Dict[str, BankAccount]) -> dict:
        """Execute the retry command"""
        if self.transaction.retry_count >= self.transaction.max_retries:
            raise ValueError("Transaction has reached maximum retry attempts")
            
        if self.transaction.txn_status != TransactionStatus.FAILED:
            raise ValueError("Can only retry failed transactions")
            
        # Get the account
        account = accounts.get(self.transaction.account_id)
        if not account:
            raise ValueError(f"Account {self.transaction.account_id} not found")
            
        # Reset the transaction state
        self.transaction.state_machine = TransactionStateMachine()
        self.transaction.retry_count += 1
        
        # Start processing again
        if not self.transaction.start_processing():
            raise Exception("Failed to start processing transaction")
            
        # Try to complete the transaction
        try:
            # Check for sufficient funds if it's a withdrawal or transfer out
            if self.transaction.txn_type in [TransactionType.WITHDRAW, TransactionType.TRANSFER_OUT]:
                if self.transaction.amount > account.account_balance:
                    # Mark as failed
                    account.update_transaction_status(
                        self.transaction.transaction_id,
                        TransactionEvent.FAIL
                    )
                    return {
                        'success': False,
                        'transaction_id': self.transaction.transaction_id,
                        'new_status': self.transaction.txn_status.name,
                        'retry_count': self.transaction.retry_count,
                        'error': "Insufficient funds"
                    }
            
            # Complete the transaction
            if not account.update_transaction_status(
                self.transaction.transaction_id,
                TransactionEvent.COMPLETE
            ):
                raise Exception("Failed to complete transaction")
                
            return {
                'success': True,
                'transaction_id': self.transaction.transaction_id,
                'new_status': self.transaction.txn_status.name,
                'retry_count': self.transaction.retry_count
            }
        except Exception as e:
            # If anything fails, mark the transaction as failed again
            account.update_transaction_status(
                self.transaction.transaction_id,
                TransactionEvent.FAIL
            )
            return {
                'success': False,
                'transaction_id': self.transaction.transaction_id,
                'new_status': self.transaction.txn_status.name,
                'retry_count': self.transaction.retry_count,
                'error': str(e)
            }

class RetryFailedTransactionsCommand(BaseCommand):
    """Command to retry all failed transactions for an account"""
    
    def __init__(self, account: BankAccount):
        """
        Initialize the retry command.
        
        Args:
            account: BankAccount to retry failed transactions for
        """
        super().__init__()
        self.account = account
        
    def execute(self, accounts: Dict[str, BankAccount]) -> Dict:
        """Execute the retry command"""
        if self.account.account_id not in accounts:
            raise ValueError(f"Account {self.account.account_id} not found")
            
        results = {
            'success': True,
            'retried_count': 0,
            'success_count': 0,
            'failed_count': 0,
            'transaction_results': {}
        }
        
        # Get all failed transactions
        failed_transactions = [
            txn for txn in self.account.get_transactions()
            if txn.txn_status == TransactionStatus.FAILED and txn.retry_count < txn.max_retries
        ]
        
        # Retry each failed transaction
        for txn in failed_transactions:
            try:
                retry_cmd = RetryTransactionCommand(txn)
                result = retry_cmd.execute(accounts)
                results['retried_count'] += 1
                if result['success']:
                    results['success_count'] += 1
                else:
                    results['failed_count'] += 1
                results['transaction_results'][txn.transaction_id] = result
            except Exception as e:
                results['failed_count'] += 1
                results['transaction_results'][txn.transaction_id] = {
                    'success': False,
                    'error': str(e)
                }
        
        return results

def load_archived_transactions(account_id: str) -> List[Transaction]:
    """Load archived transactions for an account from the archive file.
    
    Args:
        account_id: ID of the account to load archived transactions for
        
    Returns:
        List of archived transactions for the account
    """
    transactions = []
    try:
        # Get the account's base directory from the accounts file
        accounts = load_accounts()
        account = accounts.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
            
        archive_file = os.path.join(account.base_dir, 'transactions_archive.csv')
        if os.path.exists(archive_file):
            with open(archive_file, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['account_id'] == account_id:
                        txn = Transaction(
                            txn_type=TransactionType[row['txn_type']],
                            amount=Decimal(row['amount']),
                            account_id=row['account_id']
                        )
                        txn.transaction_id = row['transaction_id']
                        txn.created_at = datetime.fromisoformat(row['created_at'])
                        txn.updated_at = datetime.fromisoformat(row['updated_at'])
                        # Set the status using the state machine
                        status = TransactionStatus[row['txn_status']]
                        if status == TransactionStatus.COMPLETED:
                            txn.state_machine.transition(TransactionEvent.START_PROCESSING)
                            txn.state_machine.transition(TransactionEvent.COMPLETE)
                        elif status == TransactionStatus.FAILED:
                            txn.state_machine.transition(TransactionEvent.START_PROCESSING)
                            txn.state_machine.transition(TransactionEvent.FAIL)
                        elif status == TransactionStatus.PROCESSING:
                            txn.state_machine.transition(TransactionEvent.START_PROCESSING)
                        transactions.append(txn)
    except Exception as e:
        logger.error(f"Error loading archived transactions: {str(e)}")
        raise
    return transactions

class CommandInvoker:
    """Singleton class that manages command execution and system state."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.accounts = load_accounts()
                    cls._instance._lock = threading.Lock()
                    cls._instance.factory = CommandFactory()
        return cls._instance
        
    def __init__(self):
        """Initialize the command invoker with accounts loaded from storage."""
        # Initialization is handled in __new__
        pass
        
    def execute_command(self, command: BaseCommand) -> Dict[str, Any]:
        """Execute a command and return the result."""
        with self._lock:
            result = command.execute(self.accounts)
            self.save_state(self.accounts)
            return result
    
    def save_state(self, accounts: Dict[str, BankAccount]):
        """Save the current state of all accounts."""
        save_accounts(accounts)
    
    def create_account(self, name: str, initial_balance: Decimal) -> Dict[str, Any]:
        """Create a new account."""
        command = self.factory._create_account(name, initial_balance)
        return self.execute_command(command)
    
    def deposit(self, account_id: str, amount: Decimal) -> Dict[str, Any]:
        """Deposit money into an account."""
        account = self.accounts.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        command = self.factory._deposit(account, amount)
        return self.execute_command(command)
    
    def withdraw(self, account_id: str, amount: Decimal) -> Dict[str, Any]:
        """Withdraw money from an account."""
        account = self.accounts.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        command = self.factory._withdraw(account, amount)
        return self.execute_command(command)
    
    def transfer(self, source_id: str, target_id: str, amount: Decimal) -> Dict[str, Any]:
        """Transfer money between accounts."""
        source_account = self.accounts.get(source_id)
        if not source_account:
            raise ValueError(f"Source account {source_id} not found")
        target_account = self.accounts.get(target_id)
        if not target_account:
            raise ValueError(f"Target account {target_id} not found")
        command = self.factory._transfer(source_account, target_account, amount)
        return self.execute_command(command)
        
    def archive_transactions(self, account_id: str, keep_last: int = 100) -> Dict[str, Any]:
        """Archive transactions for an account.
        
        Args:
            account_id: ID of the account to archive transactions for
            keep_last: Number of recent transactions to keep
            
        Returns:
            Dictionary containing the result of the operation
            
        Raises:
            ValueError: If the account is not found
        """
        account = self.accounts.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        command = ArchiveTransactionsCommand(account, keep_last)
        return self.execute_command(command)
        
    def retry_transaction(self, account_id: str, transaction_id: str) -> Dict[str, Any]:
        """Retry a failed transaction.
        
        Args:
            account_id: ID of the account containing the transaction
            transaction_id: ID of the transaction to retry
            
        Returns:
            Dictionary containing the result of the operation
            
        Raises:
            ValueError: If the account or transaction is not found
        """
        account = self.accounts.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        transaction = next((t for t in account.get_transactions() if t.transaction_id == transaction_id), None)
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")
        command = RetryTransactionCommand(transaction)
        return self.execute_command(command)
        
    def retry_failed_transactions(self, account_id: str) -> Dict[str, Any]:
        """Retry all failed transactions for an account.
        
        Args:
            account_id: ID of the account to retry failed transactions for
            
        Returns:
            Dictionary containing the result of the operation
            
        Raises:
            ValueError: If the account is not found
        """
        account = self.accounts.get(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        command = RetryFailedTransactionsCommand(account)
        return self.execute_command(command)

    def get_archived_transactions(self, account_id: str) -> List[Transaction]:
        """Get archived transactions for an account"""
        return load_archived_transactions(account_id)

class CommandFactory:
    """Factory for creating command instances with centralized command creation logic.
    This class should only be used by CommandInvoker. Clients should use CommandInvoker methods directly.
    """
    
    @staticmethod
    def _create_account(name: str, initial_balance: Decimal) -> CreateAccountCommand:
        """Create a new account creation command.
        
        Args:
            name: Name of the account holder
            initial_balance: Initial balance for the account
            
        Returns:
            CreateAccountCommand instance
        """
        if not name.strip():
            raise ValueError("Account name cannot be empty")
        if initial_balance < 0:
            raise ValueError("Initial balance cannot be negative")
        initial_balance = validate_positive_whole_cents(initial_balance, "initial balance", allow_zero=True)
        return CreateAccountCommand(name, initial_balance)
        
    @staticmethod
    def _deposit(account: BankAccount, amount: Decimal) -> DepositCommand:
        """Create a new deposit command.
        
        Args:
            account: Target account for deposit
            amount: Amount to deposit
            
        Returns:
            DepositCommand instance
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        amount = validate_positive_whole_cents(amount, "deposit amount")
        return DepositCommand(account, amount)
        
    @staticmethod
    def _withdraw(account: BankAccount, amount: Decimal) -> WithdrawCommand:
        """Create a new withdraw command.
        
        Args:
            account: Source account for withdraw
            amount: Amount to withdraw
            
        Returns:
            WithdrawCommand instance
        """
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        amount = validate_positive_whole_cents(amount, "withdraw amount")
        if amount > account.account_balance:
            raise ValueError("Insufficient funds")
        return WithdrawCommand(account, amount)
        
    @staticmethod
    def _transfer(source: BankAccount, target: BankAccount, amount: Decimal) -> TransferCommand:
        """Create a new transfer command.
        
        Args:
            source: Source account for transfer
            target: Target account for transfer
            amount: Amount to transfer
            
        Returns:
            TransferCommand instance
        """
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")
        amount = validate_positive_whole_cents(amount, "transfer amount")
        if source == target:
            raise ValueError("Source and target accounts must be different")
        if amount > source.account_balance:
            raise ValueError("Insufficient funds")
        return TransferCommand(source, target, amount)
        
    @staticmethod
    def _archive_transactions(account: BankAccount, keep_last: int = 100) -> ArchiveTransactionsCommand:
        """Create a new transaction archiving command.
        
        Args:
            account: Account whose transactions to archive
            keep_last: Number of recent transactions to keep
            
        Returns:
            ArchiveTransactionsCommand instance
        """
        if keep_last < 0:
            raise ValueError("keep_last must be non-negative")
        return ArchiveTransactionsCommand(account, keep_last)
        
    @staticmethod
    def _retry_transaction(transaction: Transaction) -> RetryTransactionCommand:
        """Create a new transaction retry command.
        
        Args:
            transaction: Transaction to retry
            
        Returns:
            RetryTransactionCommand instance
        """
        if transaction.txn_status != TransactionStatus.FAILED:
            raise ValueError("Can only retry failed transactions")
        return RetryTransactionCommand(transaction)
        
    @staticmethod
    def _retry_failed_transactions(account: BankAccount) -> RetryFailedTransactionsCommand:
        """Create a new command to retry all failed transactions.
        
        Args:
            account: Account whose failed transactions to retry
            
        Returns:
            RetryFailedTransactionsCommand instance
        """
        return RetryFailedTransactionsCommand(account)

if __name__ == "__main__":
    pass
