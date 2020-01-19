import os
import pkgutil
import inspect
from importlib import import_module
from typing import Type, Any, Dict, List


class PluginCollector:
    """
    Upon creation, this class will read the plugins package for modules
    that contain a class definition that is inheriting from the specified plugin class
    """

    def __init__(self, package_name: str, plugin_class_type: Type[Any]) -> None:
        """
        Constructor that initiates the reading of all available plugins
        when an instance of the PluginCollector object is created
        """

        self.package_name = package_name
        self.plugin_class_type = plugin_class_type
        self._plugins: List[plugin_class_type] = []
        self.seen_paths = []
        self._load_plugins(self.package_name)

    def _load_plugins(self, package_name: str, kwargs: Dict[str, Any] = None) -> None:
        """
        Functions that will search through all the files in a directory to locate the class matching the
        given class name.
        """

        package = import_module(package_name)

        for _, package_name, is_package in pkgutil.iter_modules(package.__path__, package.__name__ + '.'):

            if not is_package:
                # Load the given module
                module = import_module(package_name)
                cls_members = inspect.getmembers(module, inspect.isclass)

                for (_, class_definition) in cls_members:

                    # Only add classes that are a sub class of defined Plugin class, but NOT Plugin itself
                    if issubclass(class_definition, self.plugin_class_type) & (class_definition is not self.plugin_class_type):

                        if kwargs:
                            self._plugins.append(class_definition(**kwargs))
                        else:
                            self._plugins.append(class_definition())

        all_current_paths = []

        if isinstance(package.__path__, str):
            all_current_paths.append(package.__path__)
        else:
            all_current_paths.extend([x for x in package.__path__])

        for pkg_path in all_current_paths:

            if pkg_path not in self.seen_paths:
                self.seen_paths.append(pkg_path)

                # Get all subdirectory of the current package path directory
                child_pkgs = [p for p in os.listdir(pkg_path) if os.path.isdir(os.path.join(pkg_path, p))]

                # For each subdirectory, apply the walk_package method recursively
                for child_pkg in child_pkgs:
                    self._load_plugins(package + '.' + child_pkg)


    @property
    def plugins(self) -> List[Any]:
        return self._plugins
