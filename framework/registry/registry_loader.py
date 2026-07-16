"""Dynamic tool discovery and registration loader for framework.

Scans Python packages for subclasses of BaseTool and registers them
with the tool registry automatically.
"""

import importlib
import inspect
import pkgutil
from typing import Type
from framework.registry.tool_registry import BaseTool, ToolRegistry, global_registry
from framework.utils.logger import get_logger

logger = get_logger(__name__)


def load_tools_from_package(package_name: str, registry: ToolRegistry = global_registry) -> None:
    """Dynamically imports and registers all tools found within a package.

    Args:
        package_name: The dotted path of the package (e.g. 'tools').
        registry: The ToolRegistry instance to load tools into.
    """
    logger.info("Initializing dynamic tool discovery", package=package_name)
    try:
        package = importlib.import_module(package_name)
    except ModuleNotFoundError as e:
        logger.error("Failed to load tool package", package=package_name, error=str(e))
        return

    # Check if the package has a path (it should be a folder containing modules)
    if not hasattr(package, "__path__"):
        logger.warning("Target package does not have __path__. Cannot scan modules.", package=package_name)
        return

    # Iterate through all submodules in the package
    for _, module_name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        try:
            # Dynamically import the submodule
            module = importlib.import_module(module_name)
            
            # Find classes inside the module that inherit from BaseTool
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Ensure the class inherits from BaseTool and is defined in the imported module 
                # (to prevent registering classes imported from other files)
                if issubclass(obj, BaseTool) and obj is not BaseTool and obj.__module__ == module.__name__:
                    logger.info("Discovered tool class", class_name=name, module=module_name)
                    try:
                        registry.register(obj)
                    except Exception as reg_err:
                        logger.error("Failed to register discovered tool class", class_name=name, error=str(reg_err))
        except Exception as e:
            logger.error("Error loading module during tool discovery", module=module_name, error=str(e))
