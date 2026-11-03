"""Make a QR code image for a web address.

Usage (from the project folder, with the virtual environment active):
    python tools/make_qr.py http://192.168.1.23:5173/team team-qr.png
"""
import sys

import qrcode

url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173/team"
out = sys.argv[2] if len(sys.argv) > 2 else "team-qr.png"
qrcode.make(url).save(out)
print(f"Saved {out} for {url}")
