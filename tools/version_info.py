"""Write a PyInstaller version resource so the .exe shows name, version and author
in Explorer > Properties > Details.

Usage: python tools/version_info.py OUT_FILE
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aqj import APP_NAME, __version__

TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'lime98'),
      StringStruct('FileDescription', '{name}'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'ArmaQueueJoiner'),
      StringStruct('LegalCopyright', 'MIT licence, lime98 aka micorytican'),
      StringStruct('OriginalFilename', 'ArmaQueueJoiner.exe'),
      StringStruct('ProductName', '{name}'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    parts = [int(p) for p in __version__.split(".")[:4]]
    nums = tuple(parts + [0] * (4 - len(parts)))
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.format(nums=nums, name=APP_NAME, version=__version__), "utf-8")
    print(out)


if __name__ == "__main__":
    main()
