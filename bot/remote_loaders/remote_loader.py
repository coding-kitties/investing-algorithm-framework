import logging
from abc import ABC
from pathlib import Path
from inspect import getmembers, isclass
from typing import List, Type, Generator, Any
from importlib.util import spec_from_file_location, module_from_spec

from bot import OperationalException, DependencyException


logger = logging.getLogger(__name__)


class RemoteLoader(ABC):
    """
    RemoteLoader class: abstract class with some util functions to handle searching for modules,
    classes and instantiating classes
    """

    @staticmethod
    def locate_python_modules(dir_path: Path) -> List[Path]:
        """
        Functions that will search through all the files in a directory to locate the class matching the
        given class name.
        """

        if not dir_path.is_dir():
            raise OperationalException("Given directory path is not a directory")

        modules: List[Path] = []

        logger.info("Searching in directory {} ...".format(dir_path))

        for entry in dir_path.iterdir():

            if not str(entry).endswith('.py'):
                continue

            logger.info("Found module: {}, appending it to search paths".format(str(entry)))
            modules.append(entry)

        return modules

    @staticmethod
    def locate_class(modules: List[Path], class_name: str) -> Path:
        """
        Function that will search all the given modules and will return the corresponding path where
        the class is located.
        """

        for module_path in modules:
            spec = spec_from_file_location(module_path.stem, str(module_path))
            module = module_from_spec(spec)

            try:
                spec.loader.exec_module(module)
            except (ModuleNotFoundError, SyntaxError) as err:
                # Catch errors in case a specific module is not installed
                logger.warning(f"Could not import {module_path} due to '{err}'")

            if hasattr(module, class_name):
                logger.info("Found class {} in module {}".format(class_name, str(module_path)))
                return module_path

        raise DependencyException("Could not find given class {} in selection of modules. "
                                  "Please make sure you placed the plugin in the dedicated plugin "
                                  "directory".format(class_name))

    @staticmethod
    def create_class_generators(module_path: Path, class_name: str,
                                class_type: Type[Any]) -> Generator[Any, None, None]:
        """
        Function that creates a generator for a given module path and class name
        """
        spec = spec_from_file_location(module_path.stem, str(module_path))
        module = module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except (ModuleNotFoundError, SyntaxError) as err:
            # Catch errors in case a specific module is not installed
            logger.warning(f"Could not import {module_path} due to '{err}'")

        object_generators = (
            obj for name, obj in getmembers(module, isclass) if (class_name is None or class_name == name)
            and class_type in obj.__bases__
        )
       
        return object_generators
