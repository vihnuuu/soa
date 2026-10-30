class LoanNotFoundError(Exception):
    pass


class LoanAlreadyReturnedError(Exception):
    pass


class BookAlreadyLoanedError(Exception):
    pass


class BookCatalogNotFoundError(Exception):
    pass


class CatalogServiceUnavailableError(Exception):
    pass


class CatalogServiceBadResponseError(Exception):
    pass


class EventPublishError(Exception):
    pass