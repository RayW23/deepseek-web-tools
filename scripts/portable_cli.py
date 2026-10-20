import multiprocessing
import sys

from deepseek_web.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main(sys.argv[1:] or ["gui"]))
