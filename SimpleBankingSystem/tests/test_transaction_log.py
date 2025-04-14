import os
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import threading
import time
from SimpleBankingSystem.transaction_log import TransactionLog
from SimpleBankingSystem.entities import BankAccount, Transaction, TransactionEvent
from SimpleBankingSystem.constants import TransactionType, TransactionStatus

class TestTransactionLog(unittest.TestCase):
    """Test cases for the TransactionLog class"""

    def setUp(self):
        """Set up test environment"""
        self.test_log_file = 'test_transaction_log.csv'
        self.transaction_log = TransactionLog(self.test_log_file)
        self.account = BankAccount("Test Account", Decimal('1000.00'))
        self.transaction = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal('100.00'),
            account_id=self.account.account_id
        )

    def tearDown(self):
        """Clean up test files"""
        if os.path.exists(self.transaction_log.filepath):
            os.remove(self.transaction_log.filepath)

    def test_log_creation(self):
        """Test that log file is created with correct headers"""
        self.assertTrue(os.path.exists(self.transaction_log.filepath))
        with open(self.transaction_log.filepath, 'r') as f:
            headers = f.readline().strip().split(',')
            expected_headers = [
                'timestamp', 'transaction_id', 'account_id',
                'transaction_type', 'amount', 'old_balance',
                'new_balance', 'status', 'retry_count',
                'error_message', 'event'
            ]
            self.assertEqual(headers, expected_headers)

    def test_log_transaction(self):
        """Test logging a single transaction"""
        self.transaction_log.log_transaction(
            transaction_id=self.transaction.transaction_id,
            account_id=self.account.account_id,
            transaction_type=self.transaction.txn_type,
            amount=self.transaction.amount,
            old_balance=Decimal('1000.00'),
            new_balance=Decimal('1100.00'),
            status=self.transaction.txn_status
        )

        entries = self.transaction_log.get_log_entries()
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry['transaction_id'], self.transaction.transaction_id)
        self.assertEqual(entry['account_id'], self.account.account_id)
        self.assertEqual(entry['amount'], self.transaction.amount)
        self.assertEqual(entry['old_balance'], Decimal('1000.00'))
        self.assertEqual(entry['new_balance'], Decimal('1100.00'))
        self.assertEqual(entry['status'], TransactionStatus.PENDING)

    def test_log_state_change(self):
        """Test logging transaction state changes"""
        # Add transaction to account
        self.account.add_transaction(self.transaction)
        
        # Log state change from PENDING to PROCESSING
        self.transaction_log.log_state_change(
            self.transaction,
            TransactionStatus.PENDING,
            TransactionStatus.PROCESSING,
            TransactionEvent.START_PROCESSING
        )
        
        # Log state change from PROCESSING to COMPLETED
        self.transaction_log.log_state_change(
            self.transaction,
            TransactionStatus.PROCESSING,
            TransactionStatus.COMPLETED,
            TransactionEvent.COMPLETE
        )
        
        entries = self.transaction_log.get_log_entries()
        self.assertEqual(len(entries), 2)
        
        # Check first entry (PENDING -> PROCESSING)
        self.assertEqual(entries[0]['status'], TransactionStatus.PROCESSING)
        self.assertEqual(entries[0]['event'], TransactionEvent.START_PROCESSING)
        
        # Check second entry (PROCESSING -> COMPLETED)
        self.assertEqual(entries[1]['status'], TransactionStatus.COMPLETED)
        self.assertEqual(entries[1]['event'], TransactionEvent.COMPLETE)

    def test_log_filtering(self):
        """Test log entry filtering"""
        # Log multiple transactions
        for i in range(3):
            self.transaction_log.log_transaction(
                transaction_id=f"txn-{i}",
                account_id=self.account.account_id,
                transaction_type=TransactionType.DEPOSIT,
                amount=Decimal('100.00'),
                old_balance=Decimal('1000.00') + (i * Decimal('100.00')),
                new_balance=Decimal('1100.00') + (i * Decimal('100.00')),
                status=TransactionStatus.COMPLETED
            )

        # Test account filtering
        entries = self.transaction_log.get_log_entries(account_id=self.account.account_id)
        self.assertEqual(len(entries), 3)

        # Test date filtering
        start_date = datetime.now(timezone.utc) - timedelta(minutes=5)
        end_date = datetime.now(timezone.utc) + timedelta(minutes=5)
        entries = self.transaction_log.get_log_entries(
            account_id=self.account.account_id,
            start_date=start_date,
            end_date=end_date
        )
        self.assertEqual(len(entries), 3)
        
        # Test status filtering
        entries = self.transaction_log.get_log_entries(status=TransactionStatus.COMPLETED)
        self.assertEqual(len(entries), 3)

    def test_error_handling(self):
        """Test error handling in transaction logging"""
        # Test invalid transaction type (wrong type)
        with self.assertRaises(AttributeError):
            self.transaction_log.log_transaction(
                transaction_id="test",
                account_id=self.account.account_id,
                transaction_type="DEPOSIT",  # Should be TransactionType.DEPOSIT
                amount=Decimal('100.00'),
                old_balance=Decimal('1000.00'),
                new_balance=Decimal('1100.00'),
                status=TransactionStatus.COMPLETED
            )
            
        # Test invalid status (wrong type)
        with self.assertRaises(AttributeError):
            self.transaction_log.log_transaction(
                transaction_id="test",
                account_id=self.account.account_id,
                transaction_type=TransactionType.DEPOSIT,
                amount=Decimal('100.00'),
                old_balance=Decimal('1000.00'),
                new_balance=Decimal('1100.00'),
                status="COMPLETED"  # Should be TransactionStatus.COMPLETED
            )

class TestTransactionLogConcurrency(unittest.TestCase):
    """Test cases for concurrent transaction logging"""

    def setUp(self):
        self.test_log_file = 'test_concurrent_log.csv'
        self.transaction_log = TransactionLog(self.test_log_file)
        self.account = BankAccount("Test Account", Decimal('1000.00'))
        self.num_threads = 10
        self.transactions_per_thread = 10

    def tearDown(self):
        if os.path.exists(self.transaction_log.filepath):
            os.remove(self.transaction_log.filepath)

    def test_concurrent_logging(self):
        """Test concurrent transaction logging"""
        def log_transactions():
            for i in range(self.transactions_per_thread):
                txn = Transaction(
                    txn_type=TransactionType.DEPOSIT,
                    amount=Decimal('10.00'),
                    account_id=self.account.account_id
                )
                self.transaction_log.log_transaction(
                    transaction_id=txn.transaction_id,
                    account_id=txn.account_id,
                    transaction_type=txn.txn_type,
                    amount=txn.amount,
                    old_balance=Decimal('1000.00'),
                    new_balance=Decimal('1010.00'),
                    status=txn.txn_status
                )

        # Create and start threads
        threads = []
        for _ in range(self.num_threads):
            thread = threading.Thread(target=log_transactions)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify number of log entries
        entries = self.transaction_log.get_log_entries()
        expected_entries = self.num_threads * self.transactions_per_thread
        self.assertEqual(len(entries), expected_entries)

if __name__ == '__main__':
    unittest.main() 