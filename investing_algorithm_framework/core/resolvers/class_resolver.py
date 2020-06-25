import pkgutil
import inspect
from typing import Type, Any, List
from importlib import import_module


class ClassResolver:
    """
    Class ClassCollector: This class will load all the classes of a specific
    type given the package_path. You can specify a module name if you
    know where the class is located
    """

    def __init__(
            self,
            package_path: str,
            class_type: Type[Any],
            module_name: str = None
    ) -> None:
        """
        Constructor that initiates the reading of all available plugins
        when an instance of the PluginCollector object is created
        """

        self.package_path = package_path
        self.class_type = class_type
        self._class_instances: List[class_type] = []

        if module_name:
            self._find_classes(self.package_path, module_name)
        else:
            self._find_classes(self.package_path)

    def _find_classes(self, package_path: str, module_name: str = None) \
            -> None:
        """
        Functions that will search through all the files in a directory to
        locate the class matching the given class name.
        """

        loaded_package = import_module(package_path)

        for _, package_name, is_package in pkgutil.iter_modules(
                loaded_package.__path__, loaded_package.__name__ + '.'
        ):

            if not is_package:

                if module_name is not None and not \
                        package_name == "{}.{}".format(package_path,
                                                       module_name):
                    continue

                # Load the given module
                module = import_module(package_name)

                cls_members = inspect.getmembers(module, inspect.isclass)

                for (name, class_definition) in cls_members:

                    # Only add classes that are a sub class of defined Plugin
                    # class, but NOT Plugin itself
                    if issubclass(class_definition, self.class_type) \
                            and (class_definition is not self.class_type):
                        self._class_instances.append(class_definition())

    @property
    def instances(self) -> List[Any]:
        return self._class_instances
