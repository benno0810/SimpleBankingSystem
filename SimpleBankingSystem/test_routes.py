import os
import logging
import tempfile
import shutil
from unittest import TestCase
from flask import Flask
from flask_restx import Api
from SimpleBankingSystem.app import create_app
from SimpleBankingSystem.api import api_bp
from SimpleBankingSystem.constants import TransactionType, TransactionStatus
from SimpleBankingSystem.entities import BankAccount
from SimpleBankingSystem.commands import load_accounts, save_accounts
from SimpleBankingSystem.constants import TransactionStatus

BASE_URL = "/api/v1"

######################################################################
#  R O U T E   T E S T   C A S E S
######################################################################
class TestBankingServer(TestCase):
    """REST API Server Tests"""

    @classmethod
    def setUpClass(cls):
        """This runs once before the entire test suite"""
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.app.config["DEBUG"] = True
        cls.app.logger.setLevel(logging.CRITICAL)
        # Create a temporary directory for test data
        cls.temp_dir = tempfile.mkdtemp()
        # Set environment variables for test data files
        os.environ['ACCOUNTS_FILE'] = os.path.join(cls.temp_dir, 'accounts.csv')
        os.environ['TRANSACTIONS_FILE'] = os.path.join(cls.temp_dir, 'transactions.csv')
        # Create empty CSV files with headers
        with open(os.environ['ACCOUNTS_FILE'], 'w') as f:
            f.write('account_id,name,balance,created_at,updated_at\n')
        with open(os.environ['TRANSACTIONS_FILE'], 'w') as f:
            f.write('transaction_id,account_id,type,amount,status,created_at,updated_at\n')

    @classmethod
    def tearDownClass(cls):
        """This runs once after the entire test suite"""
        # Clean up temporary directory
        if os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)
        # Remove environment variables
        if 'ACCOUNTS_FILE' in os.environ:
            del os.environ['ACCOUNTS_FILE']
        if 'TRANSACTIONS_FILE' in os.environ:
            del os.environ['TRANSACTIONS_FILE']

    def setUp(self):
        """This runs before each test"""
        self.client = self.app.test_client()
        # Reset the invoker's accounts dictionary
        self.app.invoker.accounts = {}
        # Create empty files with headers
        with open(os.environ['ACCOUNTS_FILE'], 'w') as f:
            f.write('account_id,name,balance,created_at,updated_at\n')
        with open(os.environ['TRANSACTIONS_FILE'], 'w') as f:
            f.write('transaction_id,account_id,type,amount,status,created_at,updated_at\n')
        
        # Create test accounts via API
        account1_data = {"name": "Test Account 1", "initial_balance": 1000.00}
        account2_data = {"name": "Test Account 2", "initial_balance": 500.00}
        
        # Create accounts through the API
        response1 = self.client.post("/api/v1/accounts/", json=account1_data)
        response2 = self.client.post("/api/v1/accounts/", json=account2_data)
        
        # Store the account IDs for use in tests
        self.account1_id = response1.get_json()["account_id"]
        self.account2_id = response2.get_json()["account_id"]

    def tearDown(self):
        """This runs after each test"""
        # Reset the invoker's accounts dictionary
        self.app.invoker.accounts = {}
        # Clean up test data by removing the files
        if os.path.exists(os.environ['ACCOUNTS_FILE']):
            os.remove(os.environ['ACCOUNTS_FILE'])
        if os.path.exists(os.environ['TRANSACTIONS_FILE']):
            os.remove(os.environ['TRANSACTIONS_FILE'])

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

    ######################################################################
    #  T E S T   H A P P Y   P A T H S
    ######################################################################

    def test_health(self):
        """It should be healthy"""
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")

    def test_get_accounts(self):
        """It should Get a list of Accounts"""
        response = self.client.get("/api/v1/accounts/")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 2)  # Two accounts created in setUp
        # Verify account data
        accounts = {acc["account_id"]: acc for acc in data}
        self.assertIn(str(self.account1_id), accounts)
        self.assertIn(str(self.account2_id), accounts)
        self.assertEqual(accounts[str(self.account1_id)]["balance"], 1000.00)
        self.assertEqual(accounts[str(self.account2_id)]["balance"], 500.00)

    def test_create_account(self):
        """It should Create a new Account"""
        data = {"name": "Test Account", "initial_balance": 1000.00}
        response = self.client.post("/api/v1/accounts/", json=data)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["name"], "Test Account")
        self.assertEqual(data["balance"], 1000.00)
        self.assertIn("account_id", data)

    def test_deposit(self):
        """It should Deposit money into an Account"""
        data = {"amount": 100.00}
        response = self.client.post(f"/api/v1/accounts/{self.account1_id}/deposit/", json=data)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["type"], TransactionType.DEPOSIT.name)
        self.assertEqual(data["amount"], 100.00)
        self.assertEqual(data["status"], TransactionStatus.COMPLETED.name)
        self.assertEqual(data["account_id"], str(self.account1_id))

    def test_withdraw(self):
        """It should Withdraw money from an Account"""
        data = {"amount": 100.00}
        response = self.client.post(f"/api/v1/accounts/{self.account1_id}/withdraw/", json=data)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["type"], TransactionType.WITHDRAW.name)
        self.assertEqual(data["amount"], 100.00)
        self.assertEqual(data["status"], TransactionStatus.COMPLETED.name)
        self.assertEqual(data["account_id"], str(self.account1_id))

    def test_transfer(self):
        """It should Transfer money between Accounts"""
        data = {"target_account_id": str(self.account2_id), "amount": 100.00}
        response = self.client.post(f"/api/v1/accounts/{self.account1_id}/transfer/", json=data)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["type"], TransactionType.TRANSFER_OUT.name)
        self.assertEqual(data["amount"], 100.00)
        self.assertEqual(data["status"], TransactionStatus.COMPLETED.name)
        self.assertEqual(data["account_id"], str(self.account1_id))

    def test_get_statement(self):
        """It should Get an Account Statement"""
        # First make a deposit
        data = {"amount": 100.00}
        deposit_response = self.client.post(f"/api/v1/accounts/{self.account1_id}/deposit/", json=data)
        self.assertEqual(deposit_response.status_code, 200)
        
        # Then get the statement
        response = self.client.get(f"/api/v1/accounts/{self.account1_id}/transactions/")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 1)
        transaction = data[0]
        self.assertEqual(transaction["type"], TransactionType.DEPOSIT.name)
        self.assertEqual(transaction["amount"], 100.00)
        self.assertEqual(transaction["status"], TransactionStatus.COMPLETED.name)
        self.assertEqual(transaction["account_id"], str(self.account1_id))

    ######################################################################
    #  T E S T   E R R O R   C A S E S
    ######################################################################

    def test_create_account_invalid_balance(self):
        """It should not Create an Account with invalid balance"""
        test_account = {"name": "Test Account", "initial_balance": -100.0}
        response = self.client.post("/api/v1/accounts/", json=test_account)
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.get_json())

    def test_create_account_empty_name(self):
        """It should not Create an Account with empty name"""
        test_account = {"name": "", "initial_balance": 100.0}
        response = self.client.post("/api/v1/accounts/", json=test_account)
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.get_json())

    def test_deposit_invalid_amount(self):
        """It should not Deposit invalid amount"""
        # Create an account first
        test_account = {"name": "Test Account", "initial_balance": 1000.0}
        response = self.client.post("/api/v1/accounts/", json=test_account)
        self.assertEqual(response.status_code, 201)
        account_id = response.get_json()["account_id"]

        # Try to deposit invalid amount
        deposit_data = {"amount": -100.0}
        response = self.client.post(f"/api/v1/accounts/{account_id}/deposit/", json=deposit_data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.get_json())

    def test_withdraw_insufficient_funds(self):
        """It should not Withdraw more than available"""
        # Create an account first
        test_account = {"name": "Test Account", "initial_balance": 100.0}
        response = self.client.post("/api/v1/accounts/", json=test_account)
        self.assertEqual(response.status_code, 201)
        account_id = response.get_json()["account_id"]

        # Try to withdraw more than balance
        withdraw_data = {"amount": 200.0}
        response = self.client.post(f"/api/v1/accounts/{account_id}/withdraw/", json=withdraw_data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.get_json())

    def test_transfer_insufficient_funds(self):
        """It should not Transfer more than available"""
        # Create source account
        source_account = {"name": "Source Account", "initial_balance": 100.0}
        response = self.client.post("/api/v1/accounts/", json=source_account)
        self.assertEqual(response.status_code, 201)
        source_id = response.get_json()["account_id"]

        # Create target account
        target_account = {"name": "Target Account", "initial_balance": 0.0}
        response = self.client.post("/api/v1/accounts/", json=target_account)
        self.assertEqual(response.status_code, 201)
        target_id = response.get_json()["account_id"]

        # Try to transfer more than balance
        transfer_data = {"target_account_id": target_id, "amount": 200.0}
        response = self.client.post(f"/api/v1/accounts/{source_id}/transfer/", json=transfer_data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.get_json())

    def test_account_not_found(self):
        """It should handle non-existent Account"""
        response = self.client.get("/api/v1/accounts/non-existent-id/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("message", response.get_json())

    def test_method_not_allowed(self):
        """It should not allow invalid methods"""
        response = self.client.put("/api/v1/accounts/")
        self.assertEqual(response.status_code, 405)
        self.assertIn("message", response.get_json()) 