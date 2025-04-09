import unittest
import os
import tempfile
from decimal import Decimal
from datetime import datetime, timezone
from entities import BankAccount, Transaction
from persistence import save_accounts, save_transactions, load_accounts, load_transactions
from constants import TransactionType, TransactionStatus

class TestPersistence(unittest.TestCase):
    def setUp(self):
        # Create temporary files for testing
        self.accounts_file = tempfile.NamedTemporaryFile(delete=False)
        self.transactions_file = tempfile.NamedTemporaryFile(delete=False)
        
        # Create test accounts
        self.accounts = {
            "acc1": BankAccount("Account 1", 100.00),
            "acc2": BankAccount("Account 2", 50.00)
        }
        
        # Add some transactions
        self.accounts["acc1"].apply_transaction(
            Transaction(TransactionType.DEPOSIT, TransactionStatus.COMPLETED, 50.00)
        )
        self.accounts["acc2"].apply_transaction(
            Transaction(TransactionType.WITHDRAW, TransactionStatus.COMPLETED, 20.00)
        )

    def tearDown(self):
        # Clean up temporary files
        os.unlink(self.accounts_file.name)
        os.unlink(self.transactions_file.name)

    def test_save_and_load_accounts(self):
        # Save accounts
        save_accounts(self.accounts, self.accounts_file.name)
        
        # Load accounts
        loaded_accounts = load_accounts(self.accounts_file.name)
        
        # Verify loaded accounts
        self.assertEqual(len(loaded_accounts), 2)
        self.assertEqual(loaded_accounts["acc1"].account_name, "Account 1")
        self.assertEqual(loaded_accounts["acc1"].initial_balance, Decimal('100.00'))
        self.assertEqual(loaded_accounts["acc2"].account_name, "Account 2")
        self.assertEqual(loaded_accounts["acc2"].initial_balance, Decimal('50.00'))

    def test_save_and_load_transactions(self):
        # Save accounts and transactions
        save_accounts(self.accounts, self.accounts_file.name)
        save_transactions(self.accounts, self.transactions_file.name)
        
        # Load accounts and transactions
        loaded_accounts = load_accounts(self.accounts_file.name)
        load_transactions(loaded_accounts, self.transactions_file.name)
        
        # Verify loaded transactions
        self.assertEqual(len(loaded_accounts["acc1"].transactions), 1)
        self.assertEqual(len(loaded_accounts["acc2"].transactions), 1)
        
        acc1_txn = loaded_accounts["acc1"].transactions[0]
        self.assertEqual(acc1_txn.txn_type, TransactionType.DEPOSIT)
        self.assertEqual(acc1_txn.amount, Decimal('50.00'))
        
        acc2_txn = loaded_accounts["acc2"].transactions[0]
        self.assertEqual(acc2_txn.txn_type, TransactionType.WITHDRAW)
        self.assertEqual(acc2_txn.amount, Decimal('-20.00'))

    def test_load_nonexistent_files(self):
        # Test loading from nonexistent files
        nonexistent_accounts = load_accounts("nonexistent.csv")
        self.assertEqual(nonexistent_accounts, {})
        
        # Test loading transactions for nonexistent accounts
        load_transactions({}, "nonexistent.csv")  # Should not raise an exception

if __name__ == '__main__':
    unittest.main() 