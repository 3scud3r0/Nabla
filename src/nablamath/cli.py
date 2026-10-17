"""Legacy file entry point; the public CLI now lives in ``nablamath.cli.main``."""
from nablamath.cli.main import main

if __name__ == '__main__':
    raise SystemExit(main())
