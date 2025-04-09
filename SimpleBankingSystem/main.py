# main.py
from persistence import load_accounts, load_transactions, save_accounts, save_transactions
from commands import DepositCommand, WithdrawCommand, TransferCommand, CommandInvoker
from entities import BankAccount
from decimal import Decimal


def initialize_system():
    accounts = load_accounts()
    if not accounts:
        # Create default accounts if CSV not found or empty.
        accounts = {
            "acc1": BankAccount("acc1", "Alice", initial_balance=100),
            "acc2": BankAccount("acc2", "Bob", initial_balance=50)
        }
    # Load transactions and apply them to the corresponding accounts.
    load_transactions(accounts)
    return accounts


def main():
    # Initialize system: load persisted accounts and transactions.
    accounts = initialize_system()
    print("System state loaded.")
    for account in accounts.values():
        print(f"{account.account_id}: {account.account_name} - Balance: {account.get_balance()}")

    invoker = CommandInvoker()

    # Demonstrate new operations.
    print("\nPerforming new operations...")
    deposit_cmd = DepositCommand(accounts["acc1"], 50)
    invoker.execute_command(deposit_cmd)

    withdraw_cmd = WithdrawCommand(accounts["acc1"], 30)
    invoker.execute_command(withdraw_cmd)

    transfer_cmd = TransferCommand(accounts["acc1"], accounts["acc2"], 40)
    invoker.execute_command(transfer_cmd)

    # Persist the updated state.
    save_accounts(accounts)
    save_transactions(accounts)

    print("\nUpdated state:")
    for account in accounts.values():
        print(f"{account.account_id}: {account.account_name} - Balance: {account.get_balance()}")
        print("Statement:")
        for entry in account.get_statement():
            print(entry)
        print("\n")


if __name__ == "__main__":
    main()
