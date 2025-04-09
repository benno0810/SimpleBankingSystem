# commands.py
from entities import Transaction, BankAccount
from constants import TransactionType, TransactionStatus
from abc import ABC, abstractmethod

class Command(ABC):
    @abstractmethod
    def execute(self):
        """Perform the command action."""
        pass

class DepositCommand(Command):
    def __init__(self, account: BankAccount, amount: float):
        self.account = account
        self.amount = amount

    def execute(self):
        if self.amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        txn = Transaction(
            txn_type=TransactionType.DEPOSIT,
            txn_status=TransactionStatus.COMPLETED,
            amount=self.amount,
            description="Deposit"
        )
        self.account.apply_transaction(txn)
        return txn

class WithdrawCommand(Command):
    def __init__(self, account: BankAccount, amount: float):
        self.account = account
        self.amount = amount

    def execute(self):
        if self.amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        if self.account.get_balance() < self.amount:
            raise ValueError("Insufficient funds for withdrawal.")
        txn = Transaction(
            txn_type=TransactionType.WITHDRAW,
            txn_status=TransactionStatus.COMPLETED,
            amount=-self.amount,
            description="Withdrawal"
        )
        self.account.apply_transaction(txn)
        return txn

class TransferCommand(Command):
    def __init__(self, source_account: BankAccount, target_account: BankAccount, amount: float):
        self.source_account = source_account
        self.target_account = target_account
        self.amount = amount

    def execute(self):
        if self.amount <= 0:
            raise ValueError("Transfer amount must be positive.")
        if self.source_account.get_balance() < self.amount:
            raise ValueError("Insufficient funds for transfer.")
        withdraw_txn = Transaction(
            txn_type=TransactionType.TRANSFER_OUT,
            txn_status=TransactionStatus.COMPLETED,
            amount=-self.amount,
            description=f"Transfer to {self.target_account.account_id}"
        )
        self.source_account.apply_transaction(withdraw_txn)
        deposit_txn = Transaction(
            txn_type=TransactionType.TRANSFER_IN,
            txn_status=TransactionStatus.COMPLETED,
            amount=self.amount,
            description=f"Transfer from {self.source_account.account_id}"
        )
        self.target_account.apply_transaction(deposit_txn)
        return withdraw_txn, deposit_txn

class CommandInvoker:
    def __init__(self):
        self.history = []

    def execute_command(self, command: Command):
        result = command.execute()
        self.history.append(command)
        return result

if __name__ == "__main__":
    from persistence import save_accounts, save_transactions
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
