import importlib
import pkgutil
from pathlib import Path


def load_plugins(registry, config) -> list[str]:
    """`jarvis/plugins/` ichidagi barcha plugin modullarni yuklaydi.

    Har bir plugin faylida quyidagi imzoga ega funksiya bo'lishi kerak::

        def register(registry: ToolRegistry, config: Config) -> None:
            registry.register(MyTool())

    Yangi tool (masalan Telegram bot, Gmail) qo'shish uchun shu papkaga
    yangi `.py` fayl tashlash kifoya — hech narsani qo'lda import qilish
    shart emas.
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
