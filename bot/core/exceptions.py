class ImproperlyConfigured(Exception):
    """
    Exception class indicating a problem with the configuration of the bot
    """
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(ImproperlyConfigured, self).__init__(message)
