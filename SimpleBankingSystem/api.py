from flask import Blueprint, current_app, request
from flask_restx import Api, Resource, fields, Namespace
from SimpleBankingSystem.entities import BankAccount, Transaction
from SimpleBankingSystem.constants import TransactionType, TransactionStatus
from decimal import Decimal
import uuid
from SimpleBankingSystem.logger import logger
from datetime import datetime

# Create API blueprint
api_bp = Blueprint('api', __name__)
api = Api(api_bp, 
          version='1.0', 
          title='Simple Banking System API',
          description='A simple banking system API',
          doc='/swagger/',
          url_scheme='http')

# Create namespaces
accounts_ns = api.namespace('accounts', description='Account operations')
transactions_ns = api.namespace('transactions', description='Transaction operations')

# Add request logging
@api_bp.before_request
def log_request_info():
    logger.debug('Request URL: %s', request.url)
    logger.debug('Request Method: %s', request.method)
    logger.debug('Request Headers: %s', dict(request.headers))
    if request.is_json:
        logger.debug('Request JSON: %s', request.get_json())

# Add health check endpoint
@api_bp.route('/health/')
def health():
    logger.debug('Health check endpoint called')
    return {'status': 'ok'}, 200

# Define models
account_model = api.model('Account', {
    'account_id': fields.String(description='Account ID'),
    'name': fields.String(description='Account holder name'),
    'balance': fields.Float(description='Current balance'),
    'created_at': fields.DateTime(description='Account creation timestamp')
})

account_input_model = api.model('AccountInput', {
    'name': fields.String(required=True, description='Account holder name'),
    'initial_balance': fields.Float(required=True, description='Initial balance')
})

transaction_model = api.model('Transaction', {
    'transaction_id': fields.String(description='Transaction ID'),
    'account_id': fields.String(description='Account ID'),
    'target_account_id': fields.String(description='Target account ID (for transfers)', required=False),
    'type': fields.String(description='Transaction type', enum=['DEPOSIT', 'WITHDRAW', 'TRANSFER_IN', 'TRANSFER_OUT']),
    'amount': fields.Float(description='Transaction amount'),
    'status': fields.String(description='Transaction status', enum=['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED']),
    'created_at': fields.DateTime(description='Transaction creation timestamp'),
    'updated_at': fields.DateTime(description='Transaction last update timestamp')
})

transaction_input_model = api.model('TransactionInput', {
    'amount': fields.Float(required=True, description='Transaction amount'),
    'description': fields.String(description='Transaction description')
})

transfer_input_model = api.model('TransferInput', {
    'target_account_id': fields.String(required=True, description='Target account ID'),
    'amount': fields.Float(required=True, description='Transfer amount'),
    'description': fields.String(description='Transfer description')
})

# Account namespace endpoints
@accounts_ns.route('/')
class AccountList(Resource):
    @accounts_ns.doc('list_accounts')
    @accounts_ns.marshal_list_with(account_model)
    def get(self):
        """List all accounts"""
        logger.debug('GET /accounts/ called')
        accounts = []
        for account in current_app.invoker.accounts.values():
            accounts.append({
                'account_id': str(account.account_id),
                'name': account.name,
                'balance': float(account.get_balance()),
                'created_at': account.created_at.isoformat()
            })
        logger.debug('Found %d accounts', len(accounts))
        return accounts

    @accounts_ns.doc('create_account')
    @accounts_ns.expect(account_input_model)
    @accounts_ns.marshal_with(account_model, code=201)
    def post(self):
        """Create a new account"""
        logger.debug('POST /accounts/ called with data: %s', api.payload)
        data = api.payload
        try:
            initial_balance = Decimal(str(data['initial_balance']))
            result = current_app.invoker.create_account(data['name'], initial_balance)
            logger.debug('Account created: %s', result)
            return {
                'account_id': result['account_id'],
                'name': result['name'],
                'balance': float(result['balance']),
                'created_at': result['created_at']
            }, 201
        except ValueError as e:
            logger.error('Failed to create account: %s', str(e))
            api.abort(400, str(e))

    @accounts_ns.doc('method_not_allowed')
    def put(self):
        """PUT method not allowed"""
        api.abort(405, 'Method not allowed')

    @accounts_ns.doc('method_not_allowed')
    def delete(self):
        """DELETE method not allowed"""
        api.abort(405, 'Method not allowed')

@accounts_ns.route('/<string:account_id>/')
@accounts_ns.param('account_id', 'The account identifier')
class AccountDetail(Resource):
    @accounts_ns.doc('get_account')
    @accounts_ns.marshal_with(account_model)
    def get(self, account_id):
        """Get account details"""
        logger.debug('GET /accounts/%s/ called', account_id)
        account = current_app.invoker.accounts.get(account_id)
        if not account:
            logger.error('Account not found: %s', account_id)
            api.abort(404, 'Account not found')
        logger.debug('Found account: %s', account)
        return {
            'account_id': str(account.account_id),
            'name': account.name,
            'balance': float(account.get_balance()),
            'created_at': account.created_at.isoformat()
        }

@accounts_ns.route('/<string:account_id>/deposit/')
@accounts_ns.param('account_id', 'The account identifier')
class AccountDeposit(Resource):
    @accounts_ns.doc('deposit')
    @accounts_ns.expect(transaction_input_model)
    @accounts_ns.marshal_with(transaction_model)
    def post(self, account_id):
        """Deposit money into account"""
        logger.debug('POST /accounts/%s/deposit/ called with data: %s', account_id, api.payload)
        data = api.payload
        try:
            amount = Decimal(str(data['amount']))
            result = current_app.invoker.deposit(account_id, amount)
            logger.debug('Deposit result: %s', result)
            # Get the transaction to get its timestamps
            account = current_app.invoker.accounts.get(account_id)
            transaction = account.get_transaction(result['transaction_id'])
            return {
                'transaction_id': result['transaction_id'],
                'account_id': account_id,
                'type': TransactionType.DEPOSIT.name,
                'amount': float(amount),
                'status': result['status'],
                'created_at': transaction.created_at.isoformat(),
                'updated_at': transaction.updated_at.isoformat()
            }
        except ValueError as e:
            logger.error('Failed to deposit: %s', str(e))
            if "not found" in str(e).lower():
                api.abort(404, str(e))
            api.abort(400, str(e))

@accounts_ns.route('/<string:account_id>/withdraw/')
@accounts_ns.param('account_id', 'The account identifier')
class AccountWithdraw(Resource):
    @accounts_ns.doc('withdraw')
    @accounts_ns.expect(transaction_input_model)
    @accounts_ns.marshal_with(transaction_model)
    def post(self, account_id):
        """Withdraw money from account"""
        # First check if account exists
        account = current_app.invoker.accounts.get(account_id)
        if not account:
            api.abort(404, 'Account not found')
            
        data = api.payload
        try:
            amount = Decimal(str(data['amount']))
            if amount <= 0:
                api.abort(400, 'Amount must be positive')
                
            result = current_app.invoker.withdraw(account_id, amount)
            # Get the transaction to get its timestamps
            transaction = account.get_transaction(result['transaction_id'])
            return {
                'transaction_id': result['transaction_id'],
                'account_id': account_id,
                'type': TransactionType.WITHDRAW.name,
                'amount': float(amount),
                'status': result['status'],
                'created_at': transaction.created_at.isoformat(),
                'updated_at': transaction.updated_at.isoformat()
            }
        except ValueError as e:
            if "insufficient funds" in str(e).lower():
                api.abort(400, str(e))
            api.abort(400, 'Invalid amount')

@accounts_ns.route('/<string:account_id>/transfer/')
@accounts_ns.param('account_id', 'The source account identifier')
class AccountTransfer(Resource):
    @accounts_ns.doc('transfer')
    @accounts_ns.expect(transfer_input_model)
    @accounts_ns.marshal_with(transaction_model)
    def post(self, account_id):
        """Transfer money to another account"""
        # First check if source account exists
        source_account = current_app.invoker.accounts.get(account_id)
        if not source_account:
            api.abort(404, 'Source account not found')
            
        data = api.payload
        # Check if target account exists
        target_account = current_app.invoker.accounts.get(data['target_account_id'])
        if not target_account:
            api.abort(404, 'Target account not found')
            
        try:
            amount = Decimal(str(data['amount']))
            if amount <= 0:
                api.abort(400, 'Amount must be positive')
                
            result = current_app.invoker.transfer(account_id, data['target_account_id'], amount)
            # Get the transaction to get its timestamps
            transaction = source_account.get_transaction(result['source_transaction']['transaction_id'])
            return {
                'transaction_id': result['source_transaction']['transaction_id'],
                'account_id': account_id,
                'type': TransactionType.TRANSFER_OUT.name,
                'amount': float(amount),
                'status': result['source_transaction']['status'],
                'created_at': transaction.created_at.isoformat(),
                'updated_at': transaction.updated_at.isoformat()
            }
        except ValueError as e:
            if "insufficient funds" in str(e).lower():
                api.abort(400, str(e))
            api.abort(400, 'Invalid amount')

@accounts_ns.route('/<string:account_id>/transactions/')
@accounts_ns.param('account_id', 'The account identifier')
class AccountTransactions(Resource):
    @accounts_ns.doc('list_account_transactions')
    @accounts_ns.marshal_list_with(transaction_model)
    def get(self, account_id):
        """List all transactions for an account"""
        account = current_app.invoker.accounts.get(account_id)
        if not account:
            api.abort(404, 'Account not found')

        # Get active transactions
        transactions = []
        for txn in account.get_transactions():
            transactions.append({
                'transaction_id': txn.transaction_id,
                'account_id': txn.account_id,
                'type': txn.txn_type.name,
                'amount': float(txn.amount),
                'status': txn.txn_status.name,
                'created_at': txn.created_at,
                'updated_at': txn.updated_at
            })

        # Get archived transactions
        try:
            archived_transactions = current_app.invoker.get_archived_transactions(account_id)
            for txn in archived_transactions:
                transactions.append({
                    'transaction_id': txn.transaction_id,
                    'account_id': txn.account_id,
                    'type': txn.txn_type.name,
                    'amount': float(txn.amount),
                    'status': txn.txn_status.name,
                    'created_at': txn.created_at,
                    'updated_at': txn.updated_at
                })
        except FileNotFoundError:
            # If no archived transactions exist, that's fine
            pass

        # Sort transactions by creation date (newest first)
        transactions.sort(key=lambda x: x['created_at'], reverse=True)
        return transactions

# Transaction namespace endpoints
@transactions_ns.route('/')
class TransactionList(Resource):
    @transactions_ns.doc('list_transactions')
    @transactions_ns.marshal_list_with(transaction_model)
    def get(self):
        """List all transactions"""
        transactions = []
        for account in current_app.invoker.accounts.values():
            for txn in account.get_transactions():
                transactions.append({
                    'transaction_id': txn.transaction_id,
                    'account_id': txn.account_id,
                    'type': txn.txn_type.name,
                    'amount': float(txn.amount),
                    'status': txn.txn_status.name,
                    'created_at': txn.created_at,
                    'updated_at': txn.updated_at
                })
        return transactions

@transactions_ns.route('/<string:transaction_id>/')
@transactions_ns.param('transaction_id', 'The transaction identifier')
class TransactionDetail(Resource):
    @transactions_ns.doc('get_transaction')
    @transactions_ns.marshal_with(transaction_model)
    def get(self, transaction_id):
        """Get transaction details"""
        # Search for transaction in all accounts
        for account in current_app.invoker.accounts.values():
            for txn in account.get_transactions():
                if txn.transaction_id == transaction_id:
                    return {
                        'transaction_id': txn.transaction_id,
                        'account_id': txn.account_id,
                        'type': txn.txn_type.name,
                        'amount': float(txn.amount),
                        'status': txn.txn_status.name,
                        'created_at': txn.created_at,
                        'updated_at': txn.updated_at
                    }
        api.abort(404, 'Transaction not found')