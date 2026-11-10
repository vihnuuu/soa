class AgentBaseException(Exception):
    pass


class GuardrailError(AgentBaseException):
    pass


class TokenBudgetExceededError(GuardrailError):
    pass


BudgetExceeded = TokenBudgetExceededError


class RateLimitExceeded(GuardrailError):
    pass


class RateLimitExceededError(RateLimitExceeded):
    pass


class ToolExecutionError(AgentBaseException):
    pass


class ToolInputError(ToolExecutionError):
    pass


class ToolPermissionError(ToolExecutionError):
    pass


class LibraryApiError(AgentBaseException):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


LibraryAPIError = LibraryApiError


class BookNotFoundError(LibraryApiError):
    pass


class LoanNotFoundError(LibraryApiError):
    pass


class BookAlreadyLoanedError(LibraryApiError):
    pass


class ServiceUnavailableError(LibraryApiError):
    pass


class ServiceBadResponseError(LibraryApiError):
    pass


class A2ACommunicationError(AgentBaseException):
    pass