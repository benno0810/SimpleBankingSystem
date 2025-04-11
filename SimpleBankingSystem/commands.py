# commands.py
from abc import ABC, abstractmethod
from SimpleBankingSystem.entities import Transaction, BankAccount
from SimpleBankingSystem.persistence import load_accounts, save_accounts, save_transactions
from SimpleBankingSystem.constants import TransactionType, TransactionStatus

'''
Transaction lifecycle:
1. Create transaction
2. Process transaction
3. Complete transaction
4. Fail transaction
cucrrently it's resides in single methods, but we can make it async by using another process monitor and update the status alone
'''
class BaseCommand(ABC):
    @abstractmethod
    def execute(self):
        """Perform the command action."""
        pass
    
    def save_state(self, accounts=None):
        """
        Save the state of the command.
        
        Args:
            accounts: Optional dictionary of accounts to save. If None, will load from persistence.
        """
        from SimpleBankingSystem.persistence import save_accounts, save_transactions
        if accounts is None:
            accounts = load_accounts()
        save_accounts(accounts)
        save_transactions(accounts)
        return accounts


class CreateAccountCommand(BaseCommand):
    def __init__(self, account_name: str, initial_balance: float):
        self.account_name = account_name
        self.initial_balance = initial_balance

    def execute(self):
        if self.initial_balance < 0:
            raise ValueError("Initial balance cannot be negative.")
        
        accounts = load_accounts()
        account = BankAccount(self.account_name, self.initial_balance)
        accounts[str(account.account_id)] = account
        self.save_state(accounts)
        return account

class DepositCommand(BaseCommand):
    def __init__(self, account: BankAccount, amount: float, description: str = "Deposit"):
        self.account = account
        self.amount = amount
        self.description = description

    def execute(self):
        if self.amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        
        accounts = load_accounts()
        account = accounts.get(str(self.account.account_id))
        if not account:
            raise ValueError("Account not found.")
            
        # Create and process transaction
        txn = Transaction(
            txn_type=TransactionType.DEPOSIT,
            txn_status=TransactionStatus.PENDING,
            amount=self.amount,
            description=self.description
        )
        account.apply_transaction(txn)
        
        # Process transaction
        txn.update_status(TransactionStatus.PROCESSING)
        account.apply_transaction(txn)
        
        # Complete transaction
        txn.update_status(TransactionStatus.COMPLETED)
        account.apply_transaction(txn)
        
        self.save_state(accounts)
        return txn

class WithdrawCommand(BaseCommand):
    def __init__(self, account: BankAccount, amount: float, description: str = "Withdrawal"):
        self.account = account
        self.amount = amount
        self.description = description

    def execute(self):
        if self.amount < 0.01:
            raise ValueError("Withdrawal amount must be positive.")
            
        accounts = load_accounts()
        account = accounts.get(str(self.account.account_id))
        if not account:
            raise ValueError("Account not found.")
            
        if account.get_balance() < self.amount:
            raise ValueError("Insufficient funds for withdrawal.")
            
        # Create and process transaction
        txn = Transaction(
            txn_type=TransactionType.WITHDRAW,
            txn_status=TransactionStatus.PENDING,
            amount=-self.amount,
            description=self.description
        )
        account.apply_transaction(txn)
        
        # Process transaction
        txn.update_status(TransactionStatus.PROCESSING)
        account.apply_transaction(txn)
        
        # Complete transaction
        txn.update_status(TransactionStatus.COMPLETED)
        account.apply_transaction(txn)
        
        self.save_state(accounts)
        return txn

class TransferCommand(BaseCommand):
    def __init__(self, source_account: BankAccount, target_account: BankAccount, amount: float):
        self.source_account = source_account
        self.target_account = target_account
        self.amount = amount

    def execute(self):
        if self.amount <= 0:
            raise ValueError("Transfer amount must be positive.")
            
        accounts = load_accounts()
        source = accounts.get(str(self.source_account.account_id))
        target = accounts.get(str(self.target_account.account_id))
        
        if not source:
            raise ValueError("Source account not found.")
        if not target:
            raise ValueError("Target account not found.")
        if source.get_balance() < self.amount:
            raise ValueError("Insufficient funds for transfer.")
            
        # Create and process withdrawal transaction
        withdraw_txn = Transaction(
            txn_type=TransactionType.TRANSFER_OUT,
            txn_status=TransactionStatus.PENDING,
            amount=-self.amount,
            description=f"Transfer to {target.account_id}"
        )
        source.apply_transaction(withdraw_txn)
        
        # Create and process deposit transaction
        deposit_txn = Transaction(
            txn_type=TransactionType.TRANSFER_IN,
            txn_status=TransactionStatus.PENDING,
            amount=self.amount,
            description=f"Transfer from {source.account_id}"
        )
        target.apply_transaction(deposit_txn)
        
        # Process transactions
        withdraw_txn.update_status(TransactionStatus.PROCESSING)
        deposit_txn.update_status(TransactionStatus.PROCESSING)
        source.apply_transaction(withdraw_txn)
        target.apply_transaction(deposit_txn)
        
        # Complete transactions
        withdraw_txn.update_status(TransactionStatus.COMPLETED)
        deposit_txn.update_status(TransactionStatus.COMPLETED)
        source.apply_transaction(withdraw_txn)
        target.apply_transaction(deposit_txn)
        
        self.save_state(accounts)
        return withdraw_txn, deposit_txn

class CommandInvoker:
    def __init__(self):
        self.history = []

    def execute_command(self, command: BaseCommand):
        result = command.execute()
        self.history.append(command)
        return result

if __name__ == "__main__":
    from SimpleBankingSystem.persistence import save_accounts, save_transactions
    accounts = {
        "acc1": BankAccount("acc1", "Alice", initial_balance=100),
        "acc2": BankAccount("acc2", "Bob", initial_balance=50)
    }

    invoker = CommandInvoker()

    # Run operations:
    deposit_cmd = DepositCommand(accounts["acc1"], 50)
    invoker.execute_command(deposit_cmd)

    withdraw_cmd = WithdrawCommand(accounts["acc1"], 30)
    invoker.execute_command(withdraw_cmd)

    transfer_cmd = TransferCommand(accounts["acc1"], accounts["acc2"], 40)
    invoker.execute_command(transfer_cmd)

    # Persist state.
    save_accounts(accounts)
    save_transactions(accounts)

    # Output states for testing.
    print("Account A Balance:", accounts["acc1"].get_balance())
    print("Account B Balance:", accounts["acc2"].get_balance())
