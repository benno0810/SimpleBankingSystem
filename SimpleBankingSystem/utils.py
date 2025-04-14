# utils.py
import os
from typing import Optional, Union
from SimpleBankingSystem.constants import DATA_DIR_ENV_VAR, DEFAULT_DATA_DIR
from SimpleBankingSystem.logger import logger
from decimal import Decimal

def get_data_dir() -> str:
    """
    Get the data directory path.
    Can be overridden by setting SIMPLE_BANKING_DATA_DIR environment variable.
    """
    data_dir = os.environ.get(DATA_DIR_ENV_VAR)
    if not data_dir:
        data_dir = DEFAULT_DATA_DIR
    os.makedirs(data_dir, exist_ok=True)
    logger.debug(f"Using data directory: {data_dir}")
    return data_dir

def get_file_path(filename: str) -> str:
    """
    Get the full path for a data file.
    Ensures the data directory exists.
    """
    data_dir = get_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)

def validate_positive_whole_cents(amount: Union[Decimal, float, str], field_name: str = "amount", allow_zero: bool = False) -> Decimal:
    """
    Validate that an amount is a valid monetary value in whole cents and either positive or zero (if allowed).
    
    Args:
        amount: The amount to validate (can be Decimal, float, or string)
        field_name: The name of the field being validated (for error messages)
        allow_zero: Whether to allow zero amounts (default: False)
        
    Returns:
        Decimal: The validated amount as a Decimal
        
    Raises:
        ValueError: If the amount is negative, zero when not allowed, or not in whole cents
    """
    if isinstance(amount, (float, str)):
        amount = Decimal(str(amount))
    
    if amount < 0:
        raise ValueError(f"{field_name} cannot be negative")
    
    if not allow_zero and amount == 0:
        raise ValueError(f"{field_name} must be positive")
    
    # Check if the amount has more than 2 decimal places
    if amount.as_tuple().exponent < -2:
        raise ValueError(f"{field_name} must be in whole cents (no more than 2 decimal places)")
    
    return amount 