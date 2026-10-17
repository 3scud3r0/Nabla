"""Optional Python Typst binding behind a killable subprocess boundary."""
from pathlib import Path
import sys


def main():
    import typst
    source,destination,root = sys.argv[1:]
    Path(destination).write_bytes(typst.compile(source,root=root))


if __name__ == '__main__':
    main()
