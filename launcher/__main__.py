"""python -m launcher  ->  Launcher-Kern starten."""
from . import config, logsetup
from .core import Launcher


def main() -> None:
    settings = config.load_settings()
    logsetup.setup("launcher", config.logs_dir(settings), settings.get("logging", {}).get("level", "INFO"))
    Launcher().run()


if __name__ == "__main__":
    main()
