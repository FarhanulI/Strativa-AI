class AIError(Exception):
    """Base class for controlled AI infrastructure failures."""


class AIProviderNotConfiguredError(AIError):
    pass


class AIProviderUnavailableError(AIError):
    pass


class AIModelNotAvailableError(AIError):
    pass


class AICapabilityNotSupportedError(AIError):
    pass


class AIStructuredOutputError(AIError):
    pass


class AIProviderRequestError(AIError):
    pass