from enum import Enum
class TransactionType(Enum):
    DEPOSIT = 1
    WITHDRAW = 2
    TRANSFER_IN= 3
    TRANSFER_OUT = 4
class TransactionStatus(Enum):
    PENDING = 0
    COMPLETED = 1
    PROCESSING = 2
    FAILED = 3