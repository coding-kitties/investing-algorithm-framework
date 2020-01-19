import importlib
import pkgutil

discovered_plugins = {
    name: importlib.import_module(name)
    for finder, name, ispkg
    in pkgutil.iter_modules()
    if name.startswith('data_provider')
}


