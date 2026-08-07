import sys

from .cli import main
from .pipeline import console

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Afgebroken.[/]")
        sys.exit(130)
