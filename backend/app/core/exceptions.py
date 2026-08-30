"""
Custom exceptions mapped to clean, user-facing HTTP responses by the
handlers registered in app/main.py. Nothing here ever carries a Python
traceback, a filesystem path, or a credential — those go to the server log
only (see core/logging_config.py), per spec section 30.
"""


class NexusError(Exception):
    status_code = 500
    user_message = "Something went wrong while processing your request."

    def __init__(self, user_message: str | None = None):
        if user_message:
            self.user_message = user_message
        super().__init__(self.user_message)


class FileValidationError(NexusError):
    status_code = 400


class DatasetNotFoundError(NexusError):
    status_code = 404

    def __init__(self, dataset_id: str):
        super().__init__(f"Dataset '{dataset_id}' was not found.")


class MappingNotConfirmedError(NexusError):
    status_code = 409


class RequiredFieldMissingError(NexusError):
    status_code = 422


class ProcessingError(NexusError):
    status_code = 500
    user_message = "Processing could not be completed. Your original dataset remains unchanged."
