import sys
from pathlib import Path

# My HW9 modules import each other as "hw9.<module>", 
# so web_application/ must be importable.
_WEB_APP = str(Path(__file__).resolve().parents[1])
if _WEB_APP not in sys.path:
    sys.path.append(_WEB_APP)