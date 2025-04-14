import unittest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import threading
import time
import os
import uuid
import csv
import tempfile

from SimpleBankingSystem.entities import BankAccount, Transaction, TransactionEvent
from SimpleBankingSystem.constants import TransactionType, TransactionStatus, ACCOUNTS_FILE, TRANSACTIONS_FILE

class TestBankAccount(unittest.TestCase):
    """Test cases for the BankAccount class"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.original_accounts_file = ACCOUNTS_FILE
        self.original_transactions_file = TRANSACTIONS_FILE
        
        # Override file paths for testing
        os.environ['ACCOUNTS_FILE'] = os.path.join(self.temp_dir, 'accounts.csv')
        os.environ['TRANSACTIONS_FILE'] = os.path.join(self.temp_dir, 'transactions.csv')
        
        # Create test account with temp_dir as base_dir
        self.account = BankAccount(
            name="Test Account",
            initial_balance=Decimal("1000.00"),
            base_dir=self.temp_dir
        )
        self.initial_id = self.account.account_id

    def tearDown(self):
        """Clean up test files"""
        for file in [ACCOUNTS_FILE, TRANSACTIONS_FILE]:
            if os.path.exists(file):
                os.remove(file)
        
        # Clean up archive file
        archive_file = os.path.join(self.temp_dir, 'transactions_archive.csv')
        if os.path.exists(archive_file):
            os.remove(archive_file)
        
        # Remove temporary directory
        os.rmdir(self.temp_dir)
        
        # Restore original file paths
        os.environ['ACCOUNTS_FILE'] = self.original_accounts_file
        os.environ['TRANSACTIONS_FILE'] = self.original_transactions_file

    def test_account_initialization(self):
        """Test account initialization"""
        self.assertEqual(self.account.name, "Test Account")
        self.assertEqual(self.account.account_balance, Decimal("1000.00"))
        self.assertIsInstance(self.account.created_at, datetime)
        self.assertTrue(len(self.account.account_id) > 0)
        
        # Verify account_id is a valid UUID
        try:
            uuid_obj = uuid.UUID(self.account.account_id)
            self.assertEqual(str(uuid_obj), self.account.account_id)
        except ValueError:
            self.fail("account_id is not a valid UUID")

    def test_account_id_immutability(self):
        """Test that account_id cannot be modified after creation"""
        with self.assertRaises(AttributeError):
            self.account.account_id = str(uuid.uuid4())

    def test_initial_balance(self):
        """Test initial balance validation"""
        with self.assertRaises(ValueError):
            BankAccount("Invalid Account", Decimal("-100.00"))

    def test_transaction_state_management(self):
        """Test transaction state management and balance updates."""
        # Create account
        account = BankAccount("Test Account", Decimal("1000.00"))
        
        # Create and add a deposit transaction
        deposit = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal("100.00"),
            account_id=account.account_id
        )
        account.add_transaction(deposit)
        
        # Verify initial state
        self.assertEqual(deposit.txn_status, TransactionStatus.PENDING)
        self.assertEqual(account.account_balance, Decimal("1000.00"))
        
        # Start processing
        time.sleep(0.001)  # Small delay to ensure timestamps are different
        deposit.start_processing()
        self.assertEqual(deposit.txn_status, TransactionStatus.PROCESSING)
        self.assertEqual(account.account_balance, Decimal("1000.00"))
        
        # Complete transaction
        time.sleep(0.001)  # Small delay to ensure timestamps are different
        account.update_transaction_status(deposit.transaction_id, TransactionEvent.COMPLETE)
        self.assertEqual(deposit.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(account.account_balance, Decimal("1100.00"))
        
        # Verify invalid state transition
        with self.assertRaises(ValueError):
            deposit.start_processing()  # Cannot start processing a completed transaction
        
        # Create and add a withdraw transaction
        withdraw = Transaction(
            txn_type=TransactionType.WITHDRAW,
            amount=Decimal("50.00"),
            account_id=account.account_id
        )
        account.add_transaction(withdraw)
        
        # Verify initial state
        self.assertEqual(withdraw.txn_status, TransactionStatus.PENDING)
        self.assertEqual(account.account_balance, Decimal("1100.00"))
        
        # Start processing
        time.sleep(0.001)  # Small delay to ensure timestamps are different
        withdraw.start_processing()
        self.assertEqual(withdraw.txn_status, TransactionStatus.PROCESSING)
        self.assertEqual(account.account_balance, Decimal("1100.00"))
        
        # Complete transaction
        time.sleep(0.001)  # Small delay to ensure timestamps are different
        account.update_transaction_status(withdraw.transaction_id, TransactionEvent.COMPLETE)
        self.assertEqual(withdraw.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(account.account_balance, Decimal("1050.00"))
        
        # Verify invalid state transition
        with self.assertRaises(ValueError):
            withdraw.start_processing()  # Cannot start processing a completed transaction
        
        # Verify timestamps
        self.assertIsNotNone(deposit.created_at)
        self.assertIsNotNone(deposit.updated_at)
        self.assertIsNotNone(withdraw.created_at)
        self.assertIsNotNone(withdraw.updated_at)
        
        # Verify updated_at is after created_at for completed transactions
        self.assertGreater(deposit.updated_at, deposit.created_at)
        self.assertGreater(withdraw.updated_at, withdraw.created_at)

    def test_transaction_ordering(self):
        """Test transaction ordering by created_at"""
        # Create account
        account = BankAccount("Test Account", Decimal("1000.00"))
        
        # Create transactions with different timestamps
        txn1 = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal("100.00"),
            account_id=account.account_id
        )
        txn1.created_at = datetime(2023, 1, 1, tzinfo=timezone.utc)
        txn1.updated_at = datetime(2023, 1, 1, tzinfo=timezone.utc)
        
        txn2 = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal("200.00"),
            account_id=account.account_id
        )
        txn2.created_at = datetime(2023, 1, 2, tzinfo=timezone.utc)
        txn2.updated_at = datetime(2023, 1, 2, tzinfo=timezone.utc)
        
        txn3 = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal("300.00"),
            account_id=account.account_id
        )
        txn3.created_at = datetime(2023, 1, 3, tzinfo=timezone.utc)
        txn3.updated_at = datetime(2023, 1, 3, tzinfo=timezone.utc)
        
        # Add transactions in reverse order
        account.add_transaction(txn3)
        account.add_transaction(txn1)
        account.add_transaction(txn2)
        
        # Get transactions and verify order
        transactions = account.get_transactions()
        self.assertEqual(len(transactions), 3)
        self.assertEqual(transactions[0].created_at, datetime(2023, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(transactions[1].created_at, datetime(2023, 1, 2, tzinfo=timezone.utc))
        self.assertEqual(transactions[2].created_at, datetime(2023, 1, 3, tzinfo=timezone.utc))

    def test_balance_calculation_edge_cases(self):
        """Test balance calculation with edge cases"""
        # Test zero amount transaction
        zero_txn = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal("0.00"),
            account_id=self.account.account_id
        )
        self.account.add_transaction(zero_txn)
        zero_txn.start_processing()
        self.account.update_transaction_status(zero_txn.transaction_id, TransactionEvent.COMPLETE)
        self.assertEqual(self.account.account_balance, Decimal("1000.00"))
        
        # Test transfer between same account
        transfer_out = Transaction(
            txn_type=TransactionType.TRANSFER_OUT,
            amount=Decimal("100.00"),
            account_id=self.account.account_id
        )
        transfer_in = Transaction(
            txn_type=TransactionType.TRANSFER_IN,
            amount=Decimal("100.00"),
            account_id=self.account.account_id
        )
        self.account.add_transaction(transfer_out)
        self.account.add_transaction(transfer_in)
        transfer_out.start_processing()
        transfer_in.start_processing()
        self.account.update_transaction_status(transfer_out.transaction_id, TransactionEvent.COMPLETE)
        self.account.update_transaction_status(transfer_in.transaction_id, TransactionEvent.COMPLETE)
        self.assertEqual(self.account.account_balance, Decimal("1000.00"))

    def test_concurrent_balance_access(self):
        """Test concurrent access to account balance"""
        def check_balance():
            for _ in range(1000):
                balance = self.account.get_balance()
                self.assertIsInstance(balance, Decimal)
                self.assertTrue(balance >= Decimal("0.00"))
        
        # Create multiple threads accessing balance
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=check_balance)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()

    def test_transaction_archiving(self):
        """Test transaction archiving"""
        # Create more transactions than the keep limit
        for i in range(10):
            txn = Transaction(
                txn_type=TransactionType.DEPOSIT,
                amount=Decimal("100.00"),
                account_id=self.account.account_id
            )
            self.account.add_transaction(txn)
            txn.start_processing()
            self.account.update_transaction_status(txn.transaction_id, TransactionEvent.COMPLETE)
        
        # Archive transactions, keeping only 5
        from SimpleBankingSystem.commands import ArchiveTransactionsCommand
        cmd = ArchiveTransactionsCommand(self.account, keep_last=5)
        result = cmd.execute({str(self.account.account_id): self.account})
        
        self.assertEqual(len(self.account.get_transactions()), 5)
        self.assertEqual(result['archived_count'], 5)
        self.assertEqual(result['kept_count'], 5)
        
        # Verify archive file exists and has correct content
        archive_file = os.path.join(self.temp_dir, 'transactions_archive.csv')
        self.assertTrue(os.path.exists(archive_file))
        
        with open(archive_file, 'r') as f:
            reader = csv.DictReader(f)
            archived_transactions = list(reader)
            self.assertEqual(len(archived_transactions), 5)

    def test_archived_transactions_loading(self):
        """Test loading archived transactions"""
        # Create and archive some transactions
        for i in range(10):
            txn = Transaction(
                txn_type=TransactionType.DEPOSIT,
                amount=Decimal("100.00"),
                account_id=self.account.account_id
            )
            self.account.add_transaction(txn)
            txn.start_processing()
            self.account.update_transaction_status(txn.transaction_id, TransactionEvent.COMPLETE)
        
        # Archive transactions
        from SimpleBankingSystem.commands import ArchiveTransactionsCommand
        cmd = ArchiveTransactionsCommand(self.account, keep_last=5)
        cmd.execute({str(self.account.account_id): self.account})
        
        # Load archived transactions
        transactions = self.account.get_transactions()
        self.assertEqual(len(transactions), 5)  # Only active transactions should be loaded

    def test_transaction_list_immutability(self):
        """Test that transaction list is not a direct reference to internal list."""
        # Add a transaction
        txn = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal("100.00"),
            account_id=self.account.account_id
        )
        self.account.add_transaction(txn)
        
        # Get the transactions list
        transactions = self.account.get_transactions()
        
        # Create a new transaction
        new_txn = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal("200.00"),
            account_id=self.account.account_id
        )
        
        # Try to modify the list
        try:
            transactions.append(new_txn)
        except AttributeError:
            # This is expected if we return a tuple
            pass
        else:
            # If we get here, we returned a list and the append succeeded
            # Now check if the internal list was modified
            internal_transactions = self.account.get_transactions()
            self.assertNotIn(new_txn, internal_transactions,
                           "External modification of returned list affected internal state")
            
        # Try to modify the list in other ways
        try:
            transactions[0] = new_txn
        except TypeError:
            # This is expected if we return a tuple
            pass
        else:
            # If we get here, we returned a list and the modification succeeded
            # Now check if the internal list was modified
            internal_transactions = self.account.get_transactions()
            self.assertNotEqual(internal_transactions[0], new_txn,
                              "External modification of returned list affected internal state")
        
        # Original list should remain unchanged
        self.assertEqual(len(self.account.get_transactions()), 1)

    def test_transaction_retry(self):
        """Test transaction retry functionality."""
        # Create a withdraw transaction
        withdraw = Transaction(
            txn_type=TransactionType.WITHDRAW,
            amount=Decimal("200.00"),  # More than balance
            account_id=self.account.account_id
        )
        
        # Add transaction to account
        self.assertTrue(self.account.add_transaction(withdraw))
        
        # Start processing
        self.assertTrue(withdraw.start_processing())
        self.assertEqual(withdraw.txn_status, TransactionStatus.PROCESSING)
        
        # Fail transaction (insufficient funds)
        self.assertTrue(withdraw.fail())
        self.assertEqual(withdraw.txn_status, TransactionStatus.FAILED)
        
        # First retry
        self.assertTrue(withdraw.retry())
        self.assertEqual(withdraw.txn_status, TransactionStatus.PENDING)
        self.assertEqual(withdraw.retry_count, 1)
        
        # Second retry cycle
        self.assertTrue(withdraw.start_processing())
        self.assertTrue(withdraw.fail())
        self.assertTrue(withdraw.retry())
        self.assertEqual(withdraw.retry_count, 2)
        
        # Third retry cycle
        self.assertTrue(withdraw.start_processing())
        self.assertTrue(withdraw.fail())
        self.assertTrue(withdraw.retry())
        self.assertEqual(withdraw.retry_count, 3)
        
        # Fourth retry cycle should fail due to max retries
        self.assertTrue(withdraw.start_processing())
        self.assertTrue(withdraw.fail())
        with self.assertRaises(ValueError) as context:
            withdraw.retry()
        self.assertIn("has reached maximum retry count", str(context.exception))

class TestTransaction(unittest.TestCase):
    """Test cases for the Transaction class"""

    def test_transaction_creation(self):
        """Test transaction creation"""
        # Create a transaction
        txn = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal("100.00"),
            account_id="test-account"
        )
        
        # Verify transaction properties
        self.assertIsNotNone(txn.transaction_id)
        self.assertEqual(txn.txn_type, TransactionType.DEPOSIT)
        self.assertEqual(txn.amount, Decimal("100.00"))
        self.assertEqual(txn.account_id, "test-account")
        self.assertEqual(txn.txn_status, TransactionStatus.PENDING)
        self.assertIsNotNone(txn.created_at)
        self.assertIsNotNone(txn.updated_at)
        self.assertEqual(txn.retry_count, 0)
        self.assertEqual(txn.max_retries, 3)
        
        # Verify timestamps are UTC
        self.assertEqual(txn.created_at.tzinfo, timezone.utc)
        self.assertEqual(txn.updated_at.tzinfo, timezone.utc)
        
        # Verify created_at and updated_at are initially the same
        self.assertEqual(txn.created_at, txn.updated_at)
        
        # Verify transaction state machine
        self.assertIsNotNone(txn.state_machine)
        self.assertEqual(txn.state_machine.state, TransactionStatus.PENDING)

    def test_transaction_status_update(self):
        """Test transaction status updates"""
        txn = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal("100.00"),
            account_id="test_account"
        )
        
        # Test valid transitions
        self.assertTrue(txn.start_processing())
        self.assertEqual(txn.txn_status, TransactionStatus.PROCESSING)
        
        self.assertTrue(txn.complete())
        self.assertEqual(txn.txn_status, TransactionStatus.COMPLETED)
        
        # Test invalid transitions from COMPLETED state
        with self.assertRaises(ValueError):
            txn.start_processing()  # Cannot start processing a completed transaction
            
        with self.assertRaises(ValueError):
            txn.fail()  # Cannot fail a completed transaction
            
        with self.assertRaises(ValueError):
            txn.retry()  # Cannot retry a completed transaction
            
        # Test invalid transitions from PENDING state
        txn = Transaction(
            txn_type=TransactionType.DEPOSIT,
            amount=Decimal("100.00"),
            account_id="test_account"
        )
        
        with self.assertRaises(ValueError):
            txn.complete()  # Cannot complete a pending transaction
            
        with self.assertRaises(ValueError):
            txn.fail()  # Cannot fail a pending transaction
            
        with self.assertRaises(ValueError):
            txn.retry()  # Cannot retry a pending transaction

if __name__ == '__main__':
    unittest.main() 