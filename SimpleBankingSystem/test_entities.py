import unittest
from decimal import Decimal
from entities import BankAccount, Transaction
from constants import TransactionType, TransactionStatus

class TestBankAccount(unittest.TestCase):
    def setUp(self):
        self.account = BankAccount("Test Account", 100.00)

    def test_account_creation(self):
        self.assertEqual(self.account.account_name, "Test Account")
        self.assertEqual(self.account.initial_balance, Decimal('100.00'))
        self.assertEqual(self.account.get_balance(), Decimal('100.00'))
        self.assertEqual(len(self.account.transactions), 0)

    def test_deposit(self):
        txn = Transaction(TransactionType.DEPOSIT, TransactionStatus.COMPLETED, 50.00)
        self.account.apply_transaction(txn)
        self.assertEqual(self.account.get_balance(), Decimal('150.00'))
        self.assertEqual(len(self.account.transactions), 1)

    def test_withdraw(self):
        txn = Transaction(TransactionType.WITHDRAW, TransactionStatus.COMPLETED, 30.00)
        self.account.apply_transaction(txn)
        self.assertEqual(self.account.get_balance(), Decimal('70.00'))
        self.assertEqual(len(self.account.transactions), 1)

    def test_get_statement(self):
        # Add multiple transactions
        transactions = [
            Transaction(TransactionType.DEPOSIT, TransactionStatus.COMPLETED, 50.00),
            Transaction(TransactionType.WITHDRAW, TransactionStatus.COMPLETED, 30.00),
            Transaction(TransactionType.DEPOSIT, TransactionStatus.COMPLETED, 20.00)
        ]
        
        for txn in transactions:
            self.account.apply_transaction(txn)

        statement = self.account.get_statement()
        self.assertEqual(len(statement), 3)
        self.assertEqual(statement[0]['balance_after'], Decimal('150.00'))
        self.assertEqual(statement[1]['balance_after'], Decimal('120.00'))
        self.assertEqual(statement[2]['balance_after'], Decimal('140.00'))

class TestTransaction(unittest.TestCase):
    def test_transaction_creation(self):
        txn = Transaction(TransactionType.DEPOSIT, TransactionStatus.COMPLETED, 100.00, "Test deposit")
        self.assertEqual(txn.txn_type, TransactionType.DEPOSIT)
        self.assertEqual(txn.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(txn.amount, Decimal('100.00'))
        self.assertEqual(txn.description, "Test deposit")
        self.assertIsNotNone(txn.timestamp)

if __name__ == '__main__':
    unittest.main() 