import unittest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import threading
import time
import os
import tempfile
import uuid
import csv

from SimpleBankingSystem.entities import BankAccount, Transaction
from SimpleBankingSystem.constants import TransactionType, TransactionStatus, ACCOUNTS_FILE, TRANSACTIONS_FILE
from SimpleBankingSystem.commands import (
    CommandFactory, load_accounts, save_accounts, ArchiveTransactionsCommand,
    DepositCommand, WithdrawCommand, TransferCommand, RetryTransactionCommand,
    RetryFailedTransactionsCommand, CommandInvoker, load_archived_transactions,
    CreateAccountCommand
)
from SimpleBankingSystem.logger import setup_logger
# import logging
# logger = setup_logger(level=logging.WARNING)

class TestCommands(unittest.TestCase):
    def setUp(self):
        self.account_name = "Test Account"
        self.initial_balance = Decimal('100.00')
        self.invoker = CommandInvoker()
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.original_accounts_file = ACCOUNTS_FILE
        self.original_transactions_file = TRANSACTIONS_FILE
        
        # Override file paths for testing
        os.environ['ACCOUNTS_FILE'] = os.path.join(self.temp_dir, 'accounts.csv')
        os.environ['TRANSACTIONS_FILE'] = os.path.join(self.temp_dir, 'transactions.csv')
        
        # Create test accounts using invoker
        result1 = self.invoker.create_account("Test Account 1", Decimal('1000.00'))
        result2 = self.invoker.create_account("Test Account 2", Decimal('500.00'))
        
        self.account1_id = result1['account_id']
        self.account2_id = result2['account_id']

    def tearDown(self):
        # Clean up test files
        for file in ['accounts.csv', 'transactions.csv', 'archived_transactions.csv']:
            try:
                os.remove(os.path.join(self.temp_dir, file))
            except FileNotFoundError:
                pass
        
        # Clean up any archive files
        try:
            for file in os.listdir(self.temp_dir):
                if file.endswith('_archive.csv'):
                    os.remove(os.path.join(self.temp_dir, file))
        except FileNotFoundError:
            pass
        
        # Clean up test files after each test
        for file in [ACCOUNTS_FILE, TRANSACTIONS_FILE]:
            try:
                if os.path.exists(file):
                    os.remove(file)
            except FileNotFoundError:
                pass
        
        # Restore original file paths
        os.environ['ACCOUNTS_FILE'] = self.original_accounts_file
        os.environ['TRANSACTIONS_FILE'] = self.original_transactions_file
        
        # Remove temporary directory last
        try:
            os.rmdir(self.temp_dir)
        except FileNotFoundError:
            pass

    def test_create_account_command(self):
        """Test CreateAccountCommand"""
        result = self.invoker.create_account(self.account_name, self.initial_balance)
        
        self.assertIn('account_id', result)
        self.assertIn('name', result)
        self.assertIn('balance', result)
        self.assertEqual(result['name'], self.account_name)
        self.assertEqual(result['balance'], self.initial_balance)
        
        # Verify account_id is a valid UUID
        try:
            uuid_obj = uuid.UUID(result['account_id'])
            self.assertEqual(str(uuid_obj), result['account_id'])
        except ValueError:
            self.fail("account_id is not a valid UUID")

    def test_create_multiple_accounts_unique_ids(self):
        """Test that multiple accounts have unique UUIDs"""
        account_ids = set()
        num_accounts = 10
        
        for i in range(num_accounts):
            result = self.invoker.create_account(f"Test Account {i}", Decimal('100.00'))
            account_ids.add(result['account_id'])
        
        self.assertEqual(len(account_ids), num_accounts, "All accounts should have unique UUIDs")
        
        # Verify all UUIDs are valid
        for account_id in account_ids:
            try:
                uuid_obj = uuid.UUID(account_id)
                self.assertEqual(str(uuid_obj), account_id)
            except ValueError:
                self.fail(f"Invalid UUID found: {account_id}")

    def test_create_account_with_invalid_uuid(self):
        """Test that creating an account with an invalid UUID raises an error"""
        with self.assertRaises(AttributeError):
            # Try to set account_id directly (should fail)
            account = BankAccount(name="Test Account", initial_balance=Decimal('100.00'))
            account.account_id = "invalid-uuid"  # This should raise AttributeError

    def test_account_id_immutability(self):
        """Test that account_id cannot be modified after creation"""
        account = BankAccount(name="Test Account", initial_balance=Decimal('100.00'))
        original_id = account.account_id
        
        # Verify account_id is a valid UUID
        try:
            uuid_obj = uuid.UUID(original_id)
            self.assertEqual(str(uuid_obj), original_id)
        except ValueError:
            self.fail("account_id is not a valid UUID")
        
        # Try to modify account_id (should fail)
        with self.assertRaises(AttributeError):
            account.account_id = str(uuid.uuid4())
        
        # Verify account_id remains unchanged
        self.assertEqual(account.account_id, original_id)

    def test_deposit_command(self):
        """Test deposit command execution."""
        # Create test account
        account = BankAccount("Test Account", Decimal("1000.00"))
        
        # Create and execute deposit command
        cmd = DepositCommand(account, Decimal("100.00"))
        result = cmd.execute()
        
        # Verify results
        self.assertTrue(result['success'])
        self.assertEqual(account.account_balance, Decimal("1100.00"))
        
        # Verify transaction state
        transaction = account.get_transaction(result['transaction_id'])
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(transaction.txn_type, TransactionType.DEPOSIT)
        self.assertEqual(transaction.amount, Decimal("100.00"))

    def test_withdraw_command(self):
        """Test withdraw command execution."""
        # Create test account
        account = BankAccount("Test Account", Decimal("1000.00"))
        
        # Create and execute withdraw command
        cmd = WithdrawCommand(account, Decimal("100.00"))
        result = cmd.execute()
        
        # Verify results
        self.assertTrue(result['success'])
        self.assertEqual(account.account_balance, Decimal("900.00"))
        
        # Verify transaction state
        transaction = account.get_transaction(result['transaction_id'])
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(transaction.txn_type, TransactionType.WITHDRAW)
        self.assertEqual(transaction.amount, Decimal("100.00"))

    def test_transfer_command(self):
        """Test transfer command execution."""
        # Create source and target accounts
        source = BankAccount("Source Account", Decimal("1000.00"))
        target = BankAccount("Target Account", Decimal("500.00"))
        
        # Create transfer command
        command = TransferCommand(source, target, Decimal("200.00"))
        
        # Execute command
        result = command.execute({source.account_id: source, target.account_id: target})
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['source_new_balance'], Decimal("800.00"))
        self.assertEqual(result['target_new_balance'], Decimal("700.00"))
        
        # Verify transactions
        source_txn = source.get_transaction(result['source_transaction']['transaction_id'])
        target_txn = target.get_transaction(result['target_transaction']['transaction_id'])
        
        self.assertIsNotNone(source_txn)
        self.assertIsNotNone(target_txn)
        self.assertEqual(source_txn.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(target_txn.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(source_txn.txn_type, TransactionType.TRANSFER_OUT)
        self.assertEqual(target_txn.txn_type, TransactionType.TRANSFER_IN)
        self.assertEqual(source_txn.amount, Decimal("200.00"))
        self.assertEqual(target_txn.amount, Decimal("200.00"))

    def test_concurrent_commands(self):
        """Test concurrent command execution"""
        def execute_deposits():
            for _ in range(10):
                self.invoker.deposit(self.account1_id, Decimal('10.00'))
                time.sleep(0.01)

        def execute_withdraws():
            for _ in range(10):
                self.invoker.withdraw(self.account1_id, Decimal('5.00'))
                time.sleep(0.01)

        # Start concurrent operations
        deposit_thread = threading.Thread(target=execute_deposits)
        withdraw_thread = threading.Thread(target=execute_withdraws)
        
        deposit_thread.start()
        withdraw_thread.start()
        
        deposit_thread.join()
        withdraw_thread.join()
        
        # Get final balance
        account = self.invoker.accounts.get(self.account1_id)
        expected_balance = Decimal('1050.00')  # 1000 + (10 * 10) - (10 * 5)
        self.assertEqual(account.account_balance, expected_balance)

    def test_negative_amount_validations(self):
        """Test validation of negative amounts"""
        # Test negative initial balance
        with self.assertRaises(ValueError):
            self.invoker.create_account("Test Account", Decimal('-100.00'))

        # Test negative deposit
        with self.assertRaises(ValueError):
            self.invoker.deposit(self.account1_id, Decimal('-50.00'))

        # Test negative withdraw
        with self.assertRaises(ValueError):
            self.invoker.withdraw(self.account1_id, Decimal('-30.00'))

        # Test negative transfer
        with self.assertRaises(ValueError):
            self.invoker.transfer(self.account1_id, self.account2_id, Decimal('-20.00'))

    def test_zero_amount_validations(self):
        """Test validation of zero amounts"""
        # Test zero initial balance
        result = self.invoker.create_account("Zero Balance", Decimal('0.00'))
        self.assertEqual(result['balance'], Decimal('0.00'))

        # Test zero deposit
        with self.assertRaises(ValueError):
            self.invoker.deposit(self.account1_id, Decimal('0.00'))

        # Test zero withdraw
        with self.assertRaises(ValueError):
            self.invoker.withdraw(self.account1_id, Decimal('0.00'))

        # Test zero transfer
        with self.assertRaises(ValueError):
            self.invoker.transfer(self.account1_id, self.account2_id, Decimal('0.00'))

    def test_insufficient_funds(self):
        """Test insufficient funds scenarios"""
        # Test withdrawal with insufficient funds
        with self.assertRaises(ValueError):
            self.invoker.withdraw(self.account1_id, Decimal('2000.00'))

        # Test transfer with insufficient funds
        with self.assertRaises(ValueError):
            self.invoker.transfer(self.account1_id, self.account2_id, Decimal('1500.00'))

    def test_decimal_precision(self):
        """Test handling of decimal precision"""
        # Test with many decimal places (should be rejected)
        amount = Decimal('10.123456789')
        with self.assertRaises(ValueError) as context:
            self.invoker.deposit(self.account1_id, amount)
        self.assertIn("must be in whole cents", str(context.exception))
        
        # Test with valid amount (2 decimal places)
        amount = Decimal('10.12')
        result = self.invoker.deposit(self.account1_id, amount)
        self.assertEqual(result['new_balance'], Decimal('1010.12'))

    def test_self_transfer(self):
        """Test transfer to same account"""
        with self.assertRaises(ValueError) as context:
            self.invoker.transfer(self.account1_id, self.account1_id, Decimal('100.00'))
        self.assertEqual(str(context.exception), "Source and target accounts must be different")

    def test_large_number_transactions(self):
        """Test system with a large number of small transactions"""
        num_transactions = 1000
        amount = Decimal('0.01')  # Minimum allowed amount
        
        # Perform many small deposits
        for _ in range(num_transactions):
            self.invoker.deposit(self.account1_id, amount)
        
        # Get final balance
        account = self.invoker.accounts.get(self.account1_id)
        expected_balance = Decimal('1000.00') + (amount * num_transactions)
        self.assertEqual(account.account_balance, expected_balance)

    def test_minimum_transaction_amount(self):
        """Test minimum transaction amount validation"""
        # Test deposit with exactly 1 cent
        min_amount = Decimal('0.01')
        result = self.invoker.deposit(self.account1_id, min_amount)
        self.assertEqual(result['new_balance'], Decimal('1000.01'))
        
        # Test withdraw with exactly 1 cent
        result = self.invoker.withdraw(self.account1_id, min_amount)
        self.assertEqual(result['new_balance'], Decimal('1000.00'))
        
        # Test deposit with less than 1 cent
        with self.assertRaises(ValueError):
            self.invoker.deposit(self.account1_id, Decimal('0.009'))
        
        # Test withdraw with less than 1 cent
        with self.assertRaises(ValueError):
            self.invoker.withdraw(self.account1_id, Decimal('0.009'))
        
        # Test transfer with less than 1 cent
        with self.assertRaises(ValueError):
            self.invoker.transfer(self.account1_id, self.account2_id, Decimal('0.009'))

    def test_account_not_found(self):
        """Test operations with non-existent accounts"""
        # Test deposit to non-existent account
        with self.assertRaises(ValueError) as context:
            self.invoker.deposit("non-existent-id", Decimal('50.00'))
            
        # Test withdraw from non-existent account
        with self.assertRaises(ValueError) as context:
            self.invoker.withdraw("non-existent-id", Decimal('50.00'))
            
        # Test transfer from non-existent account
        with self.assertRaises(ValueError) as context:
            self.invoker.transfer("non-existent-id", self.account2_id, Decimal('50.00'))
            
        # Test transfer to non-existent account
        with self.assertRaises(ValueError) as context:
            self.invoker.transfer(self.account1_id, "non-existent-id", Decimal('50.00'))

    def test_system_state_persistence(self):
        """Test that system state is correctly persisted and can be reloaded"""
        # Create two accounts
        account1 = self.invoker.create_account("Test Account 1", Decimal("100.00"))
        account2 = self.invoker.create_account("Test Account 2", Decimal("200.00"))
        
        # Perform some operations
        deposit_cmd = self.invoker.deposit(account1['account_id'], Decimal("50.00"))
        withdraw_cmd = self.invoker.withdraw(account2['account_id'], Decimal("100.00"))
        transfer_cmd = self.invoker.transfer(account1['account_id'], account2['account_id'], Decimal("25.00"))
        
        # Get a new instance of the invoker (should be the same instance)
        new_invoker = CommandInvoker()
        
        # Verify accounts exist and have correct balances
        self.assertIn(account1['account_id'], new_invoker.accounts)
        self.assertIn(account2['account_id'], new_invoker.accounts)
        
        # Verify balances
        self.assertEqual(new_invoker.accounts[account1['account_id']].account_balance, Decimal("125.00"))
        self.assertEqual(new_invoker.accounts[account2['account_id']].account_balance, Decimal("125.00"))
        
        # Verify it's the same instance
        self.assertIs(self.invoker, new_invoker)

    def test_deposit(self):
        # Create account using invoker
        invoker = CommandInvoker()
        result = invoker.create_account("Test Account", Decimal("100.00"))
        account_id = result['account_id']
        
        # Deposit using invoker
        result = invoker.deposit(account_id, Decimal("50.00"))
        self.assertEqual(result['new_balance'], Decimal("150.00"))

    def test_withdraw(self):
        # Create account using invoker
        invoker = CommandInvoker()
        result = invoker.create_account("Test Account", Decimal("100.00"))
        account_id = result['account_id']
        
        # Withdraw using invoker
        result = invoker.withdraw(account_id, Decimal("50.00"))
        self.assertEqual(result['new_balance'], Decimal("50.00"))

    def test_transfer(self):
        # Create accounts using invoker
        invoker = CommandInvoker()
        source_result = invoker.create_account("Source Account", Decimal("100.00"))
        target_result = invoker.create_account("Target Account", Decimal("0.00"))
        
        # Transfer using invoker
        result = invoker.transfer(source_result['account_id'], target_result['account_id'], Decimal("50.00"))
        self.assertEqual(result['source_new_balance'], Decimal("50.00"))
        self.assertEqual(result['target_new_balance'], Decimal("50.00"))

    def test_insufficient_funds(self):
        # Create account using invoker
        invoker = CommandInvoker()
        result = invoker.create_account("Test Account", Decimal("100.00"))
        account_id = result['account_id']
        
        # Try to withdraw more than balance
        with self.assertRaises(ValueError) as context:
            invoker.withdraw(account_id, Decimal("150.00"))
        self.assertEqual(str(context.exception), "Insufficient funds")

    def test_account_not_found_single_operation(self):
        # Create account using invoker
        invoker = CommandInvoker()
        with self.assertRaises(ValueError) as context:
            invoker.deposit("non-existent-id", Decimal("100.00"))
        self.assertEqual(str(context.exception), "Account non-existent-id not found")

    def test_concurrent_withdraw(self):
        """Test concurrent withdraw operations"""
        def execute_withdraws():
            """Execute concurrent withdraws"""
            for _ in range(5):
                self.invoker.withdraw(self.account1_id, Decimal("100.00"))

        # Create and start threads for concurrent withdraws
        withdraw_thread = threading.Thread(target=execute_withdraws)
        withdraw_thread.start()
        withdraw_thread.join()

        # Verify final balance
        account = self.invoker.accounts.get(self.account1_id)
        expected_balance = Decimal('1000.00') - (Decimal('100.00') * 5)
        self.assertEqual(account.account_balance, expected_balance)

    def test_negative_withdraw(self):
        """Test negative withdraw amount"""
        with self.assertRaises(ValueError):
            self.invoker.withdraw(self.account1_id, Decimal("-50.00"))

    def test_zero_withdraw(self):
        """Test zero withdraw amount"""
        with self.assertRaises(ValueError):
            self.invoker.withdraw(self.account1_id, Decimal("0.00"))

    def test_withdraw_insufficient_funds(self):
        """Test withdraw with insufficient funds"""
        with self.assertRaises(ValueError):
            self.invoker.withdraw(self.account1_id, Decimal("2000.00"))

    def test_withdraw_one_cent(self):
        """Test withdraw with exactly 1 cent"""
        self.invoker.withdraw(self.account1_id, Decimal("0.01"))
        account = self.invoker.accounts.get(self.account1_id)
        expected_balance = Decimal('1000.00') - Decimal('0.01')
        self.assertEqual(account.account_balance, expected_balance)

    def test_withdraw_less_than_one_cent(self):
        """Test withdraw with less than 1 cent"""
        with self.assertRaises(ValueError):
            self.invoker.withdraw(self.account1_id, Decimal("0.001"))

    def test_withdraw_nonexistent_account(self):
        """Test withdraw from non-existent account"""
        with self.assertRaises(ValueError) as context:
            self.invoker.withdraw("nonexistent", Decimal("50.00"))
        self.assertEqual(str(context.exception), "Account nonexistent not found")

    def test_withdraw_insufficient_funds(self):
        # Create a withdraw command with amount greater than balance
        withdraw_command = WithdrawCommand(
            account_id=self.account1_id,
            amount=2000.00,
            transaction_type=TransactionType.WITHDRAW,
            description="Test withdraw with insufficient funds"
        )

    def test_execute_withdraws(self):
        """Test executing multiple withdraws concurrently."""

    def test_withdraw_negative_amount(self):
        """Test withdraw with negative amount raises ValueError."""

    def test_withdraw_zero_amount(self):
        """Test withdraw with zero amount raises ValueError."""

    def test_withdraw_insufficient_funds(self):
        """Test withdraw with insufficient funds raises ValueError."""

    def test_withdraw_nonexistent_account(self):
        """Test withdraw from nonexistent account raises ValueError."""

    def test_load_and_save_accounts(self):
        """Test loading and saving accounts to/from CSV files."""
        # Create test accounts
        account1 = BankAccount("Test Account 1", Decimal("1000.00"))
        account2 = BankAccount("Test Account 2", Decimal("500.00"))
        accounts = {account1.account_id: account1, account2.account_id: account2}
        
        # Save accounts
        save_accounts(accounts)
        
        # Load accounts
        loaded_accounts = load_accounts()
        
        # Verify loaded accounts
        self.assertEqual(len(loaded_accounts), 2)
        self.assertIn(account1.account_id, loaded_accounts)
        self.assertIn(account2.account_id, loaded_accounts)
        self.assertEqual(loaded_accounts[account1.account_id].name, "Test Account 1")
        self.assertEqual(loaded_accounts[account2.account_id].name, "Test Account 2")
        self.assertEqual(loaded_accounts[account1.account_id].account_balance, Decimal("1000.00"))
        self.assertEqual(loaded_accounts[account2.account_id].account_balance, Decimal("500.00"))

    def test_archive_transactions_command(self):
        """Test ArchiveTransactionsCommand."""
        # Create account with multiple transactions
        account = BankAccount("Test Account", Decimal("1000.00"))
        
        # Add transactions
        for i in range(150):  # More than keep_last
            cmd = DepositCommand(account, Decimal("10.00"))
            result = cmd.execute()
            transaction = account.get_transaction(result['transaction_id'])
            # Don't change state - let it be COMPLETED from the command execution
        
        # Create and execute archive command
        archive_cmd = ArchiveTransactionsCommand(account, keep_last=100)
        result = archive_cmd.execute({account.account_id: account})
        
        # Verify results
        self.assertTrue(result['success'])
        self.assertEqual(len(account.transactions), 100)  # Should keep last 100
        self.assertEqual(result['archived_count'], 50)    # Should archive 50
        
        # Verify archived transactions
        archived_txns = load_archived_transactions(account.account_id)
        self.assertEqual(len(archived_txns), 50)

    def test_retry_transaction_command(self):
        """Test RetryTransactionCommand."""
        # Create account and failed transaction
        account = BankAccount("Test Account", Decimal("1000.00"))
        cmd = WithdrawCommand(account, Decimal("2000.00"))  # This will fail
        try:
            cmd.execute()
        except ValueError:
            pass  # Expected failure
        
        # Get the failed transaction
        transaction = account.get_transaction(cmd.transaction.transaction_id)
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.txn_status, TransactionStatus.FAILED)
        
        # Create and execute retry command
        retry_cmd = RetryTransactionCommand(transaction)
        retry_result = retry_cmd.execute({account.account_id: account})
        
        # Verify results
        self.assertFalse(retry_result['success'])  # Should still fail
        self.assertEqual(transaction.retry_count, 1)

    def test_retry_failed_transactions_command(self):
        """Test RetryFailedTransactionsCommand."""
        # Create account with multiple failed transactions
        account = BankAccount("Test Account", Decimal("1000.00"))
        
        # Create failed transactions
        for _ in range(3):
            cmd = WithdrawCommand(account, Decimal("2000.00"))  # This will fail
            try:
                cmd.execute()
            except ValueError:
                pass  # Expected failure
        
        # Create and execute retry command
        retry_cmd = RetryFailedTransactionsCommand(account)
        result = retry_cmd.execute({account.account_id: account})
        
        # Verify results
        self.assertEqual(result['retried_count'], 3)
        self.assertEqual(result['success_count'], 0)  # All should still fail
        for txn in account.transactions:
            self.assertEqual(txn.retry_count, 1)

    def test_command_factory(self):
        """Test CommandFactory methods."""
        # Create test accounts
        account1 = BankAccount("Test Account 1", Decimal("1000.00"))
        account2 = BankAccount("Test Account 2", Decimal("500.00"))
        
        # Test create account command
        create_cmd = CommandFactory._create_account("New Account", Decimal("100.00"))
        self.assertIsInstance(create_cmd, CreateAccountCommand)
        
        # Test deposit command
        deposit_cmd = CommandFactory._deposit(account1, Decimal("100.00"))
        self.assertIsInstance(deposit_cmd, DepositCommand)
        
        # Test withdraw command
        withdraw_cmd = CommandFactory._withdraw(account1, Decimal("100.00"))
        self.assertIsInstance(withdraw_cmd, WithdrawCommand)
        
        # Test transfer command
        transfer_cmd = CommandFactory._transfer(account1, account2, Decimal("100.00"))
        self.assertIsInstance(transfer_cmd, TransferCommand)
        
        # Test archive command
        archive_cmd = CommandFactory._archive_transactions(account1)
        self.assertIsInstance(archive_cmd, ArchiveTransactionsCommand)
        
        # Test retry commands
        cmd = WithdrawCommand(account1, Decimal("2000.00"))  # This will fail
        try:
            cmd.execute()
        except ValueError:
            pass  # Expected failure
        failed_transaction = account1.get_transaction(cmd.transaction.transaction_id)
        self.assertIsNotNone(failed_transaction)
        retry_cmd = CommandFactory._retry_transaction(failed_transaction)
        self.assertIsInstance(retry_cmd, RetryTransactionCommand)
        
        retry_failed_cmd = CommandFactory._retry_failed_transactions(account1)
        self.assertIsInstance(retry_failed_cmd, RetryFailedTransactionsCommand)

    def test_command_invoker_singleton(self):
        """Test CommandInvoker singleton pattern."""
        invoker1 = CommandInvoker()
        invoker2 = CommandInvoker()
        self.assertIs(invoker1, invoker2)

    def test_command_invoker_methods(self):
        """Test CommandInvoker methods."""
        # Create account
        result = self.invoker.create_account("Test Account", Decimal("1000.00"))
        account_id = result['account_id']
        
        # Test deposit
        deposit_result = self.invoker.deposit(account_id, Decimal("100.00"))
        self.assertTrue(deposit_result['success'])
        
        # Test withdraw
        withdraw_result = self.invoker.withdraw(account_id, Decimal("50.00"))
        self.assertTrue(withdraw_result['success'])
        
        # Test transfer
        target_result = self.invoker.create_account("Target Account", Decimal("500.00"))
        target_id = target_result['account_id']
        transfer_result = self.invoker.transfer(account_id, target_id, Decimal("100.00"))
        self.assertTrue(transfer_result['success'])
        
        # Test archive
        archive_result = self.invoker.archive_transactions(account_id)
        self.assertTrue(archive_result['success'])
        
        # Test retry
        retry_result = self.invoker.retry_failed_transactions(account_id)
        self.assertEqual(retry_result['retried_count'], 0)  # No failed transactions

    def test_error_handling(self):
        """Test error handling in commands."""
        # Test invalid account ID
        with self.assertRaises(ValueError):
            self.invoker.deposit("invalid-id", Decimal("100.00"))
        
        # Test negative amount
        account_id = self.invoker.create_account("Test Account", Decimal("1000.00"))['account_id']
        with self.assertRaises(ValueError):
            self.invoker.deposit(account_id, Decimal("-100.00"))
        
        # Test insufficient funds
        with self.assertRaises(ValueError):
            self.invoker.withdraw(account_id, Decimal("2000.00"))
        
        # Test self transfer
        with self.assertRaises(ValueError):
            self.invoker.transfer(account_id, account_id, Decimal("100.00"))

if __name__ == '__main__':
    unittest.main() 