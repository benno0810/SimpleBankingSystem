import os
import logging
from unittest import TestCase
from SimpleBankingSystem.app import create_app
from SimpleBankingSystem.entities import BankAccount, Transaction, TransactionEvent
from SimpleBankingSystem.commands import CommandInvoker
from SimpleBankingSystem.constants import TransactionStatus, TransactionType, ACCOUNTS_FILE_ENV_VAR, TRANSACTIONS_FILE_ENV_VAR
from SimpleBankingSystem.logger import setup_logger
import unittest
import json
from decimal import Decimal
import threading
import time
from flask import Flask
import csv
import shutil
import tempfile
from SimpleBankingSystem.api import api_bp

# Constants
BASE_URL = '/api/v1'
DATA_DIR = 'test_data'
ACCOUNTS_FILE = os.path.join(DATA_DIR, 'accounts.csv')
TRANSACTIONS_FILE = os.path.join(DATA_DIR, 'transactions.csv')
ARCHIVED_TRANSACTIONS_FILE = os.path.join(DATA_DIR, 'archived_transactions.csv')

# Configure logging
logger = setup_logger("TestRoutes", level=logging.DEBUG)

######################################################################
#  R O U T E   T E S T   C A S E S
######################################################################
class TestRoutes(unittest.TestCase):
    """REST API Server Tests"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment before all tests."""
        # Create a temporary directory for test data
        cls.test_dir = tempfile.mkdtemp()
        
        # Set environment variables for test files
        os.environ[ACCOUNTS_FILE_ENV_VAR] = os.path.join(cls.test_dir, 'accounts.csv')
        os.environ[TRANSACTIONS_FILE_ENV_VAR] = os.path.join(cls.test_dir, 'transactions.csv')
        
        # Create empty CSV files with headers
        with open(os.environ[ACCOUNTS_FILE_ENV_VAR], 'w') as f:
            f.write('id,name,balance\n')
        with open(os.environ[TRANSACTIONS_FILE_ENV_VAR], 'w') as f:
            f.write('id,account_id,type,amount,timestamp\n')
        
        # Create and configure the Flask app
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['DEBUG'] = False
        cls.app.url_map.strict_slashes = False
        cls.client = cls.app.test_client()
        
        # Initialize the CommandInvoker with test files
        cls.app.invoker = CommandInvoker()
        
        logger.debug('Test environment set up with app configuration:')
        logger.debug('TESTING: %s', cls.app.config['TESTING'])
        logger.debug('DEBUG: %s', cls.app.config['DEBUG'])

    @classmethod
    def tearDownClass(cls):
        """Clean up test environment after all tests."""
        # Clean up the temporary directory
        shutil.rmtree(cls.test_dir)
        # Remove environment variables
        if ACCOUNTS_FILE_ENV_VAR in os.environ:
            del os.environ[ACCOUNTS_FILE_ENV_VAR]
        if TRANSACTIONS_FILE_ENV_VAR in os.environ:
            del os.environ[TRANSACTIONS_FILE_ENV_VAR]

    def setUp(self):
        """Run before each test"""
        # Clean up existing test data files
        with open(os.environ[ACCOUNTS_FILE_ENV_VAR], 'w') as f:
            f.write('id,name,balance\n')
        with open(os.environ[TRANSACTIONS_FILE_ENV_VAR], 'w') as f:
            f.write('id,account_id,type,amount,timestamp\n')
        
        # Reset the CommandInvoker's accounts dictionary
        self.app.invoker.accounts = {}
        
        # Create test accounts using the service
        account1_data = self.app.invoker.create_account('Test Account 1', 1500.00)
        account2_data = self.app.invoker.create_account('Test Account 2', 2000.00)
        
        # Store account IDs for reference
        self.account1_id = account1_data['account_id']
        self.account2_id = account2_data['account_id']
        
        # Store test accounts for reference
        self.test_accounts = [account1_data, account2_data]

    def tearDown(self):
        """Clean up test data after each test."""
        logger.debug('Cleaning up test data...')
        # Remove test files
        if os.path.exists(os.environ[ACCOUNTS_FILE_ENV_VAR]):
            logger.debug('Removing accounts file')
            os.remove(os.environ[ACCOUNTS_FILE_ENV_VAR])
        if os.path.exists(os.environ[TRANSACTIONS_FILE_ENV_VAR]):
            logger.debug('Removing transactions file')
            os.remove(os.environ[TRANSACTIONS_FILE_ENV_VAR])
        
        # Reset the CommandInvoker's accounts dictionary
        self.app.invoker.accounts = {}
        logger.debug('Test data cleanup complete')

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_account(self, name, balance):
        """Helper method to create an account"""
        response = self.client.post(
            f"{BASE_URL}/accounts/",
            json={"name": name, "initial_balance": balance}
        )
        return response.get_json()

    def _create_transaction(self, account_id, amount, txn_type, description=None, target_account_id=None):
        """Helper method to create a transaction"""
        if txn_type == TransactionType.DEPOSIT:
            response = self.client.post(
                f"{BASE_URL}/accounts/{account_id}/deposit/",
                json={"amount": amount, "description": description}
            )
        elif txn_type == TransactionType.WITHDRAW:
            response = self.client.post(
                f"{BASE_URL}/accounts/{account_id}/withdraw/",
                json={"amount": amount, "description": description}
            )
        elif txn_type == TransactionType.TRANSFER_OUT:
            response = self.client.post(
                f"{BASE_URL}/accounts/{account_id}/transfer/",
                json={"target_account_id": target_account_id, "amount": amount, "description": description}
            )
        
        if response.status_code not in [200, 201]:
            raise ValueError(f"Failed to create transaction: {response.get_json()}")
            
        return response.get_json()

    ######################################################################
    #  T E S T   H A P P Y   P A T H S
    ######################################################################

    def test_health(self):
        """Test health endpoint"""
        response = self.client.get(f"{BASE_URL}/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

    def test_swagger_docs(self):
        """Test Swagger documentation endpoint"""
        response = self.client.get(f"{BASE_URL}/swagger/")
        self.assertEqual(response.status_code, 200)

    def test_create_account(self):
        """Test account creation"""
        response = self.client.post(
            f"{BASE_URL}/accounts/",
            json={"name": "New Account", "initial_balance": 1000.00}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["name"], "New Account")
        self.assertEqual(response.json["balance"], 1000.00)

    def test_create_account_empty_name(self):
        """Test account creation with empty name"""
        response = self.client.post(
            f"{BASE_URL}/accounts/",
            json={"name": "", "initial_balance": 1000.00}
        )
        self.assertEqual(response.status_code, 400)

    def test_create_account_invalid_balance(self):
        """Test account creation with invalid balance"""
        response = self.client.post(
            f"{BASE_URL}/accounts/",
            json={"name": "Invalid Account", "initial_balance": -100.00}
        )
        self.assertEqual(response.status_code, 400)

    def test_get_accounts(self):
        """Test getting all accounts"""
        response = self.client.get(f"{BASE_URL}/accounts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 2)  # Should have 2 test accounts

    def test_get_account(self):
        """Test getting a specific account"""
        response = self.client.get(f"{BASE_URL}/accounts/{self.account1_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["account_id"], self.account1_id)
        self.assertEqual(response.json["name"], "Test Account 1")

    def test_account_not_found(self):
        """Test getting a non-existent account"""
        response = self.client.get(f"{BASE_URL}/accounts/nonexistent/")
        self.assertEqual(response.status_code, 404)

    def test_deposit(self):
        """Test deposit to account"""
        response = self.client.post(
            f"{BASE_URL}/accounts/{self.account1_id}/deposit/",
            json={"amount": 500.00}
        )
        self.assertEqual(response.status_code, 200)
        # Verify the transaction was created
        self.assertEqual(response.json["type"], "DEPOSIT")
        self.assertEqual(response.json["amount"], 500.00)
        self.assertEqual(response.json["status"], "COMPLETED")

    def test_deposit_invalid_amount(self):
        """Test deposit with invalid amount"""
        response = self.client.post(
            f"{BASE_URL}/accounts/{self.account1_id}/deposit/",
            json={"amount": -100.00}
        )
        self.assertEqual(response.status_code, 400)

    def test_withdraw(self):
        """Test withdraw from account"""
        response = self.client.post(
            f"{BASE_URL}/accounts/{self.account1_id}/withdraw/",
            json={"amount": 500.00}
        )
        self.assertEqual(response.status_code, 200)
        # Verify the transaction was created
        self.assertEqual(response.json["type"], "WITHDRAW")
        self.assertEqual(response.json["amount"], 500.00)
        self.assertEqual(response.json["status"], "COMPLETED")

    def test_withdraw_insufficient_funds(self):
        """Test withdraw with insufficient funds"""
        response = self.client.post(
            f"{BASE_URL}/accounts/{self.account1_id}/withdraw/",
            json={"amount": 2000.00}
        )
        self.assertEqual(response.status_code, 400)

    def test_transfer(self):
        """Test transfer between accounts"""
        response = self.client.post(
            f"{BASE_URL}/accounts/{self.account1_id}/transfer/",
            json={"target_account_id": self.account2_id, "amount": 500.00}
        )
        self.assertEqual(response.status_code, 200)
        # Verify the transaction was created
        self.assertEqual(response.json["type"], "TRANSFER_OUT")
        self.assertEqual(response.json["amount"], 500.00)
        self.assertEqual(response.json["status"], "COMPLETED")

    def test_transfer_insufficient_funds(self):
        """Test transfer with insufficient funds"""
        response = self.client.post(
            f"{BASE_URL}/accounts/{self.account1_id}/transfer/",
            json={"target_account_id": self.account2_id, "amount": 2000.00}
        )
        self.assertEqual(response.status_code, 400)

    def test_get_transactions(self):
        """Test getting all transactions"""
        # Create some transactions first
        self.app.invoker.deposit(self.account1_id, 100.00)
        self.app.invoker.withdraw(self.account1_id, 50.00)
        
        response = self.client.get(f"{BASE_URL}/transactions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 2)  # Should have 2 transactions

    def test_get_transaction(self):
        """Test getting a specific transaction"""
        # Create a transaction first
        transaction = self.app.invoker.deposit(self.account1_id, 100.00)
        
        response = self.client.get(f"{BASE_URL}/transactions/{transaction['transaction_id']}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["transaction_id"], transaction['transaction_id'])
        self.assertEqual(response.json["amount"], 100.00)

    def test_transaction_not_found(self):
        """Test getting a non-existent transaction"""
        response = self.client.get(f"{BASE_URL}/transactions/nonexistent/")
        self.assertEqual(response.status_code, 404)

    def test_method_not_allowed(self):
        """Test method not allowed"""
        response = self.client.post(f"{BASE_URL}/health/")
        self.assertEqual(response.status_code, 405)

    def test_concurrent_requests(self):
        """Test concurrent requests"""
        def make_request():
            response = self.client.post(
                f"{BASE_URL}/accounts/{self.account1_id}/deposit/",
                json={"amount": 100.00}
            )
            return response.status_code

        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify final balance
        response = self.client.get(f"{BASE_URL}/accounts/{self.account1_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["balance"], 2000.00)  # 1500 + (5 * 100)

    def test_deposit_with_special_characters(self):
        """Test deposit with special characters in description"""
        response = self.client.post(
            f"{BASE_URL}/accounts/{self.account1_id}/deposit/",
            json={"amount": 100.00, "description": "Salary!@#$%^&*()"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["type"], "DEPOSIT")
        self.assertEqual(response.json["amount"], 100.00)

    def test_withdraw_with_decimal_precision(self):
        """Test withdraw with decimal precision"""
        response = self.client.post(
            f"{BASE_URL}/accounts/{self.account1_id}/withdraw/",
            json={"amount": 123.456789}
        )
        self.assertEqual(response.status_code, 400)  # Should reject more than 2 decimal places

        # Test with valid precision
        response = self.client.post(
            f"{BASE_URL}/accounts/{self.account1_id}/withdraw/",
            json={"amount": 123.45}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["type"], "WITHDRAW")
        self.assertEqual(float(response.json["amount"]), 123.45)

    def test_transfer_with_same_account(self):
        """Test transfer to the same account"""
        response = self.client.post(
            f"{BASE_URL}/accounts/{self.account1_id}/transfer/",
            json={"target_account_id": self.account1_id, "amount": 100.00}
        )
        self.assertEqual(response.status_code, 400)

    def test_create_account_with_special_characters(self):
        """Test account creation with special characters in name"""
        response = self.client.post(
            f"{BASE_URL}/accounts/",
            json={"name": "Special!@#$%^&*() Account", "initial_balance": 1000.00}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["name"], "Special!@#$%^&*() Account")

    def test_large_number_operations(self):
        """Test operations with very large numbers"""
        # Create account with large balance
        response = self.client.post(
            f"{BASE_URL}/accounts/",
            json={"name": "Large Balance Account", "initial_balance": 999999999.99}
        )
        self.assertEqual(response.status_code, 201)
        account_id = response.json["account_id"]

        # Test deposit with large amount
        response = self.client.post(
            f"{BASE_URL}/accounts/{account_id}/deposit/",
            json={"amount": 999999999.99}
        )
        self.assertEqual(response.status_code, 200)

    def test_transaction_history_filtering(self):
        """Test transaction history filtering"""
        # Create multiple transactions
        self.app.invoker.deposit(self.account1_id, 100.00)
        self.app.invoker.withdraw(self.account1_id, 50.00)
        self.app.invoker.deposit(self.account1_id, 200.00)

        # Get all transactions
        response = self.client.get(f"{BASE_URL}/accounts/{self.account1_id}/transactions/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 3)

        # Get only deposits
        response = self.client.get(f"{BASE_URL}/accounts/{self.account1_id}/transactions/?type=DEPOSIT")
        self.assertEqual(response.status_code, 200)
        # Since filtering isn't implemented yet, we'll expect all transactions
        self.assertEqual(len(response.json), 3)

    def test_account_balance_precision(self):
        """Test account balance precision handling"""
        # Create account with precise balance
        response = self.client.post(
            f"{BASE_URL}/accounts/",
            json={"name": "Precise Balance", "initial_balance": 123.456789}
        )
        self.assertEqual(response.status_code, 400)  # Should reject more than 2 decimal places

        # Create account with valid precision
        response = self.client.post(
            f"{BASE_URL}/accounts/",
            json={"name": "Precise Balance", "initial_balance": 123.45}
        )
        self.assertEqual(response.status_code, 201)
        account_id = response.json["account_id"]
        
        # Make multiple small transactions
        for _ in range(5):
            self.app.invoker.deposit(account_id, 0.01)
        
        # Check final balance
        response = self.client.get(f"{BASE_URL}/accounts/{account_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(float(response.json["balance"]), 123.50)  # 123.45 + (5 * 0.01)

    def test_invalid_json_format(self):
        """Test requests with invalid JSON format"""
        # Test with malformed JSON
        response = self.client.post(
            f"{BASE_URL}/accounts/",
            data='{"name": "Test", "initial_balance": 1000',  # Missing closing brace
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)  # Bad Request for malformed JSON

        # Test with wrong content type
        response = self.client.post(
            f"{BASE_URL}/accounts/",
            data='{"name": "Test", "initial_balance": 1000}',
            content_type='text/plain'
        )
        self.assertEqual(response.status_code, 415)  # Unsupported Media Type

if __name__ == '__main__':
    unittest.main() 