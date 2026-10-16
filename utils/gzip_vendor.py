"""Write a .gz next to each compressible file under static/vendor.

Run from the project root after adding or upgrading a vendored library:
    python utils/gzip_vendor.py

app.py (PrecompressedStaticFlask) serves these to clients that accept gzip, so
nothing is compressed per request. Output is deterministic (no timestamp), so
re-running without changes leaves git clean. Fonts and images are skipped
because they are already compressed.
"""

import gzip
import os

VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'vendor')
EXTENSIONS = ('.css', '.js')


def main():
    for root, _dirs, files in os.walk(VENDOR_DIR):
        for name in sorted(files):
            if not name.endswith(EXTENSIONS):
                continue
            path = os.path.join(root, name)
            with open(path, 'rb') as f:
                data = f.read()
            with open(path + '.gz', 'wb') as raw, gzip.GzipFile(
                    filename='', mode='wb', fileobj=raw, compresslevel=9, mtime=0) as gz:
                gz.write(data)
            print(f'{os.path.relpath(path, VENDOR_DIR)}: {len(data)} -> {os.path.getsize(path + ".gz")} bytes')


if __name__ == '__main__':
    main()
