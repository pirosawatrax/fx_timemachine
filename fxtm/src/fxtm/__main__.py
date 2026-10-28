"""``python -m fxtm`` is the same as the ``fxtm`` command."""
import sys

from fxtm.cli import main

sys.exit(main())
