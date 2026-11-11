"""Errors raised while reading or running an Easy program."""


class EasyError(Exception):
    def __init__(self, message, line=None):
        self.message = message
        self.line = line
        if line:
            super().__init__(f"line {line}: {message}")
        else:
            super().__init__(message)
