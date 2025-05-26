from abc import abstractmethod


class AppHook:
    """
    Abstract class for app hooks. App hooks are used to run code before
    actions of the framework are executed. This is useful for running code
    that needs to be run before the following events:
    - App initialization
    - Strategy run
    """

    @abstractmethod
    def on_run(self, context) -> None:
        """
        Method to run the app hook. This method should be implemented
        by the user. This method will be called when the app is performing
        a specific action.

        Args:
            context: The context of the app. This can be used to get the
                current state of the trading bot, such as portfolios,
                orders, positions, etc.

        Returns:
            None
        """
        raise NotImplementedError()
