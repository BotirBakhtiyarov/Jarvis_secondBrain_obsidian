import importlib
import pkgutil
from pathlib import Path


def load_plugins(registry, config) -> list[str]:
    """Load every plugin module in ``orion/plugins/``.

    Each module defines ``register(registry, config)``. Adding a tool is
    just dropping a new ``.py`` file here — no manual imports needed.
    """

    loaded = []

    package_dir = Path(__file__).parent

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        name = module_info.name
        if name.startswith("_"):
            continue

        module = importlib.import_module(f"{__package__}.{name}")
        register = getattr(module, "register", None)

        if callable(register):
            register(registry, config)
            loaded.append(name)

    return loaded
