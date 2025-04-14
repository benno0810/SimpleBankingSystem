import csv
import os
from datetime import datetime, timezone
from threading import Lock
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union

from SimpleBankingSystem.entities import Transaction, TransactionEvent
from SimpleBankingSystem.constants import (
    TransactionType, TransactionStatus, TRANSACTION_LOG_FILE
)
from SimpleBankingSystem.logger import logger
from SimpleBankingSystem.utils import get_file_path

class TransactionLog:
    """A thread-safe transaction log for auditing purposes"""
    
    def __init__(self, filename=TRANSACTION_LOG_FILE):
        self.filename = filename
        self.filepath = get_file_path(filename)
        self._lock = Lock()
        self._ensure_log_file_exists()
        logger.info(f"Initialized TransactionLog with file: {self.filepath}")

    def _ensure_log_file_exists(self):
        """Ensure the log file exists with proper headers"""
        if not os.path.exists(self.filepath):
            with self._lock:
                with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'timestamp', 'transaction_id', 'account_id', 
                        'transaction_type', 'amount', 'old_balance',
                        'new_balance', 'status', 'retry_count',
                        'error_message', 'event'
                    ])
                    writer.writeheader()
                logger.info(f"Created new transaction log file: {self.filepath}")

    def log_transaction(self, transaction_id: str, account_id: str, transaction_type: TransactionType,
                       amount: Decimal, status: TransactionStatus, event: Optional[TransactionEvent] = None,
                       retry_count: int = 0, old_balance: Optional[Decimal] = None, 
                       new_balance: Optional[Decimal] = None):
        """Log a transaction with its details"""
        try:
            with self._lock:
                with open(self.filepath, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'timestamp', 'transaction_id', 'account_id', 
                        'transaction_type', 'amount', 'old_balance',
                        'new_balance', 'status', 'retry_count',
                        'error_message', 'event'
                    ])
                    entry = {
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'transaction_id': transaction_id,
                        'account_id': account_id,
                        'transaction_type': transaction_type.value,
                        'amount': str(amount),
                        'old_balance': str(old_balance) if old_balance is not None else '',
                        'new_balance': str(new_balance) if new_balance is not None else '',
                        'status': status.value,
                        'retry_count': retry_count,
                        'error_message': '',
                        'event': event.value if event else ''
                    }
                    writer.writerow(entry)
        except Exception as e:
            logger.error(f"Failed to log transaction {transaction_id}: {str(e)}")
            raise

    def log_state_change(self, transaction: Transaction, old_status: TransactionStatus, 
                        new_status: TransactionStatus, event: TransactionEvent):
        """Log a transaction state change"""
        if not transaction.account_id:
            logger.warning(f"Cannot log state change for transaction {transaction.transaction_id}: no account ID")
            return
            
        self.log_transaction(
            transaction_id=transaction.transaction_id,
            account_id=transaction.account_id,
            transaction_type=transaction.txn_type,
            amount=transaction.amount,
            status=new_status,
            event=event,
            retry_count=transaction.retry_count
        )

    def get_log_entries(self, account_id: Optional[str] = None, 
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None,
                       status: Optional[TransactionStatus] = None) -> List[Dict[str, Any]]:
        """Get log entries with optional filtering"""
        entries = []
        try:
            with self._lock:
                with open(self.filepath, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Convert timestamp
                        timestamp = datetime.fromisoformat(row['timestamp'])
                        
                        # Apply filters
                        if account_id and row['account_id'] != account_id:
                            continue
                        if start_date and timestamp < start_date:
                            continue
                        if end_date and timestamp > end_date:
                            continue
                        if status and int(row['status']) != status.value:
                            continue
                        
                        # Convert numeric fields and enums
                        try:
                            row['amount'] = Decimal(row['amount'])
                            row['old_balance'] = Decimal(row['old_balance']) if row['old_balance'] else None
                            row['new_balance'] = Decimal(row['new_balance']) if row['new_balance'] else None
                            row['retry_count'] = int(row['retry_count'])
                            row['transaction_type'] = TransactionType(int(row['transaction_type']))
                            row['status'] = TransactionStatus(int(row['status']))
                            if row['event']:
                                row['event'] = TransactionEvent(int(row['event']))
                            else:
                                row['event'] = None
                        except (decimal.InvalidOperation, ValueError) as e:
                            logger.warning(f"Error converting values in log entry: {row}, error: {e}")
                            continue
                        
                        entries.append(row)
        except FileNotFoundError:
            logger.warning(f"Transaction log file not found: {self.filepath}")
        except Exception as e:
            logger.error(f"Error reading transaction log: {str(e)}")
            raise
        
        return entries 