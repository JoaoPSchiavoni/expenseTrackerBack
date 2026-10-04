"""
Domain Exceptions for Expense Tracker.

Why: Domain exceptions represent pure business rule violations and are
completely decoupled from web frameworks (FastAPI) or database engines.
"""


class DomainError(Exception):
    """Base class for all domain exceptions."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InsufficientFundsError(DomainError):
    """Raised when a wallet lacks sufficient funds for an expense.

    Why: Prevents a bank account or wallet from reaching unauthorized negative balances,
    protecting a core business invariant.
    """

    def __init__(self, wallet_id: int, current_balance: object, requested_amount: object) -> None:
        msg = f"Insufficient funds in wallet {wallet_id}. Current balance: {current_balance}, Requested amount: {requested_amount}"
        super().__init__(msg)
        self.wallet_id = wallet_id
        self.current_balance = current_balance
        self.requested_amount = requested_amount


class WalletNotFoundError(DomainError):
    """Raised when the requested wallet does not exist."""

    def __init__(self, wallet_id: int) -> None:
        super().__init__(f"Wallet with ID {wallet_id} was not found.")
        self.wallet_id = wallet_id


class UnauthorizedWalletAccessError(DomainError):
    """Raised when a user attempts to operate on a wallet belonging to someone else."""

    def __init__(self, wallet_id: int, user_id: int) -> None:
        super().__init__(f"User {user_id} is not authorized to operate on wallet {wallet_id}.")
        self.wallet_id = wallet_id
        self.user_id = user_id


class UserAlreadyExistsError(DomainError):
    """Raised when attempting to register a user with an already registered email."""

    def __init__(self, email: str) -> None:
        super().__init__(f"A user with email {email} is already registered.")
        self.email = email


class InvalidCredentialsError(DomainError):
    """Raised when provided email or password credentials fail authentication."""

    def __init__(self) -> None:
        super().__init__("Invalid authentication credentials.")


class ImportNotFoundError(DomainError):
    """Raised when an import batch is missing or belongs to another user."""

    def __init__(self, batch_id: int) -> None:
        super().__init__(f"Import batch with ID {batch_id} was not found.")


class InvalidImportStateError(DomainError):
    """Raised when an operation is incompatible with the batch lifecycle."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class GoalNotFoundError(DomainError):
    """Raised when a goal is missing or belongs to another user."""

    def __init__(self, goal_id: int) -> None:
        super().__init__(f"Financial goal with ID {goal_id} was not found.")


class ContributionNotFoundError(DomainError):
    """Raised when a contribution is missing from the requested goal."""

    def __init__(self, contribution_id: int) -> None:
        super().__init__(f"Goal contribution with ID {contribution_id} was not found.")


class InvalidGoalStateError(DomainError):
    """Raised when a requested goal transition violates a business rule."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class BudgetAlertNotFoundError(DomainError):
    """Raised when an alert is missing or belongs to another user."""

    def __init__(self, alert_id: int) -> None:
        super().__init__(f"Budget alert with ID {alert_id} was not found.")
