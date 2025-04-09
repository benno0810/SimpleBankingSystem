import unittest
from decimal import Decimal
from entities import BankAccount
from commands import DepositCommand, WithdrawCommand, TransferCommand, CommandInvoker, CreateAccountCommand
from persistence import load_accounts, save_accounts
from constants import TransactionStatus
import os
import shutil

class TestCommands(unittest.TestCase):
    def setUp(self):
        """Set up test environment for each test."""
        self.test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
        os.makedirs(self.test_data_dir, exist_ok=True)
        
        # Create test accounts
        self.account1 = BankAccount("Test Account 1", 1000.00)
        self.account2 = BankAccount("Test Account 2", 500.00)
        self.invoker = CommandInvoker()
        
        # Save initial accounts
        accounts = {
            str(self.account1.account_id): self.account1,
            str(self.account2.account_id): self.account2
        }
        save_accounts(accounts)

    def tearDown(self):
        """Clean up test environment after each test."""
        for file in os.listdir(self.test_data_dir):
            os.remove(os.path.join(self.test_data_dir, file))
        os.rmdir(self.test_data_dir)

    def test_deposit_command_success(self):
        """Test successful deposit command."""
        # Arrange
        amount = 100.00
        description = "Test deposit"
        
        # Act
        command = DepositCommand(self.account1, amount, description)
        transaction = command.execute()
        
        # Assert
        self.assertEqual(self.account1.get_balance(), Decimal('1100.00'))
        self.assertEqual(transaction.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(transaction.amount, amount)
        self.assertEqual(transaction.description, description)

    def test_deposit_command_zero_amount(self):
        """Test deposit command with zero amount."""
        # Arrange
        amount = 0.00
        
        # Act & Assert
        with self.assertRaises(ValueError, msg="Deposit amount must be positive"):
            command = DepositCommand(self.account1, amount)
            command.execute()

    def test_deposit_command_negative_amount(self):
        """Test deposit command with negative amount."""
        # Arrange
        amount = -100.00
        
        # Act & Assert
        with self.assertRaises(ValueError, msg="Deposit amount must be positive"):
            command = DepositCommand(self.account1, amount)
            command.execute()

    def test_deposit_command_large_amount(self):
        """Test deposit command with very large amount."""
        # Arrange
        amount = 1_000_000_000.00  # 1 billion
        
        # Act
        command = DepositCommand(self.account1, amount)
        transaction = command.execute()
        
        # Assert
        self.assertEqual(self.account1.get_balance(), Decimal('1000001000.00'))
        self.assertEqual(transaction.txn_status, TransactionStatus.COMPLETED)

    def test_deposit_command_precision_amount(self):
        """Test deposit command with precise decimal amount."""
        # Arrange
        amount = 123.4567
        
        # Act
        command = DepositCommand(self.account1, amount)
        transaction = command.execute()
        
        # Assert
        self.assertEqual(self.account1.get_balance(), Decimal('1123.4567'))
        self.assertEqual(transaction.txn_status, TransactionStatus.COMPLETED)

    def test_withdraw_command_success(self):
        """Test successful withdraw command."""
        # Arrange
        amount = 100.00
        description = "Test withdrawal"
        
        # Act
        command = WithdrawCommand(self.account1, amount, description)
        transaction = command.execute()
        
        # Assert
        self.assertEqual(self.account1.get_balance(), Decimal('900.00'))
        self.assertEqual(transaction.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(transaction.amount, -amount)  # Negative for withdrawal
        self.assertEqual(transaction.description, description)

    def test_withdraw_command_zero_amount(self):
        """Test withdraw command with zero amount."""
        # Arrange
        amount = 0.00
        
        # Act & Assert
        with self.assertRaises(ValueError, msg="Withdrawal amount must be positive"):
            command = WithdrawCommand(self.account1, amount)
            command.execute()

    def test_withdraw_command_negative_amount(self):
        """Test withdraw command with negative amount."""
        # Arrange
        amount = -100.00
        
        # Act & Assert
        with self.assertRaises(ValueError, msg="Withdrawal amount must be positive"):
            command = WithdrawCommand(self.account1, amount)
            command.execute()

    def test_withdraw_command_insufficient_funds(self):
        """Test withdraw command with insufficient funds."""
        # Arrange
        amount = 2000.00
        
        # Act & Assert
        with self.assertRaises(ValueError, msg="Insufficient funds"):
            command = WithdrawCommand(self.account1, amount)
            command.execute()

    def test_withdraw_command_exact_balance(self):
        """Test withdraw command with exact balance amount."""
        # Arrange
        amount = 1000.00
        
        # Act
        command = WithdrawCommand(self.account1, amount)
        transaction = command.execute()
        
        # Assert
        self.assertEqual(self.account1.get_balance(), Decimal('0.00'))
        self.assertEqual(transaction.txn_status, TransactionStatus.COMPLETED)

    def test_transfer_command_success(self):
        """Test successful transfer command."""
        # Arrange
        amount = 100.00
        
        # Act
        command = TransferCommand(self.account1, self.account2, amount)
        withdraw_txn, deposit_txn = command.execute()
        
        # Assert
        self.assertEqual(self.account1.get_balance(), Decimal('900.00'))
        self.assertEqual(self.account2.get_balance(), Decimal('600.00'))
        self.assertEqual(withdraw_txn.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(deposit_txn.txn_status, TransactionStatus.COMPLETED)

    def test_transfer_command_zero_amount(self):
        """Test transfer command with zero amount."""
        # Arrange
        amount = 0.00
        
        # Act & Assert
        with self.assertRaises(ValueError, msg="Transfer amount must be positive"):
            command = TransferCommand(self.account1, self.account2, amount)
            command.execute()

    def test_transfer_command_negative_amount(self):
        """Test transfer command with negative amount."""
        # Arrange
        amount = -100.00
        
        # Act & Assert
        with self.assertRaises(ValueError, msg="Transfer amount must be positive"):
            command = TransferCommand(self.account1, self.account2, amount)
            command.execute()

    def test_transfer_command_insufficient_funds(self):
        """Test transfer command with insufficient funds."""
        # Arrange
        amount = 2000.00
        
        # Act & Assert
        with self.assertRaises(ValueError, msg="Insufficient funds"):
            command = TransferCommand(self.account1, self.account2, amount)
            command.execute()

    def test_transfer_command_large_amount(self):
        """Test transfer command with very large amount."""
        # Arrange
        amount = 500.00  # Exact balance of account1
        
        # Act
        command = TransferCommand(self.account1, self.account2, amount)
        withdraw_txn, deposit_txn = command.execute()
        
        # Assert
        self.assertEqual(self.account1.get_balance(), Decimal('500.00'))
        self.assertEqual(self.account2.get_balance(), Decimal('1000.00'))
        self.assertEqual(withdraw_txn.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(deposit_txn.txn_status, TransactionStatus.COMPLETED)

    def test_transfer_command_precision_amount(self):
        """Test transfer command with precise decimal amount."""
        # Arrange
        amount = 123.4567
        
        # Act
        command = TransferCommand(self.account1, self.account2, amount)
        withdraw_txn, deposit_txn = command.execute()
        
        # Assert
        self.assertEqual(self.account1.get_balance(), Decimal('876.5433'))
        self.assertEqual(self.account2.get_balance(), Decimal('623.4567'))
        self.assertEqual(withdraw_txn.txn_status, TransactionStatus.COMPLETED)
        self.assertEqual(deposit_txn.txn_status, TransactionStatus.COMPLETED)

    def test_transfer_command_same_account(self):
        """Test transfer command between same account."""
        # Arrange
        amount = 100.00
        
        # Act & Assert
        with self.assertRaises(ValueError, msg="Cannot transfer to the same account"):
            command = TransferCommand(self.account1, self.account1, amount)
            command.execute()

@pytest.fixture
def test_data_dir():
    """Create a temporary data directory for testing."""
    test_dir = os.path.join(os.path.dirname(__file__), 'test_data')
    os.makedirs(test_dir, exist_ok=True)
    yield test_dir
    shutil.rmtree(test_dir)

@pytest.fixture
def accounts_file(test_data_dir):
    """Create a temporary accounts file."""
    return os.path.join(test_data_dir, 'accounts.csv')

@pytest.fixture
def transactions_file(test_data_dir):
    """Create a temporary transactions file."""
    return os.path.join(test_data_dir, 'transactions.csv')

class TestCreateAccountCommand:
    def test_create_account_success(self, accounts_file, transactions_file):
        """Test successful account creation."""
        # Arrange
        account_name = "Test Account"
        initial_balance = 1000.0
        
        # Act
        command = CreateAccountCommand(account_name, initial_balance)
        account = command.execute()
        
        # Assert
        assert account.account_name == account_name
        assert account.get_balance() == initial_balance
        assert account.transactions == []
        
        # Verify persistence
        saved_accounts = load_accounts()
        assert str(account.account_id) in saved_accounts
        saved_account = saved_accounts[str(account.account_id)]
        assert saved_account.account_name == account_name
        assert saved_account.get_balance() == initial_balance

    def test_create_account_zero_balance(self, accounts_file, transactions_file):
        """Test creating account with zero balance."""
        # Arrange
        account_name = "Zero Balance Account"
        initial_balance = 0.0
        
        # Act
        command = CreateAccountCommand(account_name, initial_balance)
        account = command.execute()
        
        # Assert
        assert account.account_name == account_name
        assert account.get_balance() == initial_balance
        assert account.transactions == []

    def test_create_account_invalid_balance(self, accounts_file, transactions_file):
        """Test creating account with negative balance."""
        # Arrange
        account_name = "Invalid Balance Account"
        initial_balance = -100.0
        
        # Act & Assert
        with pytest.raises(ValueError, match="Initial balance cannot be negative"):
            command = CreateAccountCommand(account_name, initial_balance)
            command.execute()

    def test_create_account_empty_name(self, accounts_file, transactions_file):
        """Test creating account with empty name."""
        # Arrange
        account_name = ""
        initial_balance = 1000.0
        
        # Act & Assert
        with pytest.raises(ValueError, match="Account name cannot be empty"):
            command = CreateAccountCommand(account_name, initial_balance)
            command.execute()

    def test_create_account_whitespace_name(self, accounts_file, transactions_file):
        """Test creating account with whitespace-only name."""
        # Arrange
        account_name = "   "
        initial_balance = 1000.0
        
        # Act & Assert
        with pytest.raises(ValueError, match="Account name cannot be empty"):
            command = CreateAccountCommand(account_name, initial_balance)
            command.execute()

    def test_create_account_duplicate_name(self, accounts_file, transactions_file):
        """Test creating account with duplicate name."""
        # Arrange
        account_name = "Duplicate Account"
        initial_balance = 1000.0
        
        # Create first account
        command1 = CreateAccountCommand(account_name, initial_balance)
        command1.execute()
        
        # Act & Assert
        with pytest.raises(ValueError, match="Account name already exists"):
            command2 = CreateAccountCommand(account_name, initial_balance)
            command2.execute()

    def test_create_account_large_balance(self, accounts_file, transactions_file):
        """Test creating account with very large balance."""
        # Arrange
        account_name = "Large Balance Account"
        initial_balance = 1_000_000_000.0  # 1 billion
        
        # Act
        command = CreateAccountCommand(account_name, initial_balance)
        account = command.execute()
        
        # Assert
        assert account.account_name == account_name
        assert account.get_balance() == initial_balance

    def test_create_account_precision_balance(self, accounts_file, transactions_file):
        """Test creating account with precise decimal balance."""
        # Arrange
        account_name = "Precise Balance Account"
        initial_balance = 1234.5678
        
        # Act
        command = CreateAccountCommand(account_name, initial_balance)
        account = command.execute()
        
        # Assert
        assert account.account_name == account_name
        assert account.get_balance() == initial_balance

    def test_create_account_special_characters_name(self, accounts_file, transactions_file):
        """Test creating account with special characters in name."""
        # Arrange
        account_name = "Test Account #123!@#$%^&*()"
        initial_balance = 1000.0
        
        # Act
        command = CreateAccountCommand(account_name, initial_balance)
        account = command.execute()
        
        # Assert
        assert account.account_name == account_name
        assert account.get_balance() == initial_balance

    def test_create_account_long_name(self, accounts_file, transactions_file):
        """Test creating account with very long name."""
        # Arrange
        account_name = "A" * 1000  # 1000 character name
        initial_balance = 1000.0
        
        # Act
        command = CreateAccountCommand(account_name, initial_balance)
        account = command.execute()
        
        # Assert
        assert account.account_name == account_name
        assert account.get_balance() == initial_balance

if __name__ == '__main__':
    unittest.main() 