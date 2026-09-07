from pathlib import Path
import sys


EXPECTED = (
    "PROJECT=ORCHID\n"
    "OWNER=Mira Chen\n"
    "RETENTION_DAYS=45\n"
    "CHECKSUM=ORCHID|Mira Chen|45\n"
)

answer = Path("answers/result.txt")
if not answer.is_file():
    print("answers/result.txt does not exist", file=sys.stderr)
    raise SystemExit(1)

actual = answer.read_text(encoding="utf-8")
if actual != EXPECTED:
    print("answers/result.txt does not match the required format or facts", file=sys.stderr)
    raise SystemExit(1)
