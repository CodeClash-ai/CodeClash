from pathlib import Path

from codeclash import PACKAGE_DIR

DIR_LOGS = Path("logs")  # this is used also for parts of the paths in the environment
LOCAL_LOG_DIR = PACKAGE_DIR / DIR_LOGS  # this one is always relative to the location of this code
DIR_WORK = Path("/testbed")
FILE_RESULTS = "results.json"
GH_ORG = "emagedoc"
RESULT_TIE = "Tie"
