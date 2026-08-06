#!/usr/bin/env python3
"""Vectorizer.AI client (stdlib only, no dependencies).

Converts a raster image (PNG/JPG/WebP/GIF/BMP) into a vector (SVG/PDF/EPS/DXF/PNG)
using the official Vectorizer.AI HTTP API.

Credentials come from the environment or the local `.env` file:
    VECTORIZER_API_ID      -> HTTP Basic username
    VECTORIZER_API_SECRET  -> HTTP Basic password

Get them at https://vectorizer.ai/api

Usage:
    cp .env.example .env          # fill in VECTORIZER_API_ID / SECRET
    python3 vectorizer_client.py logo.png -o logo.svg
    python3 vectorizer_client.py logo.png --format svg --output ./out/
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from urllib import request as urlrequest

API_BASE = "https://api.vectorizer.ai/api/v1"


def _read_env_file():
    env = {}
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return env
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def load_creds():
    env = _read_env_file()
    api_id = os.environ.get("VECTORIZER_API_ID") or env.get("VECTORIZER_API_ID", "")
    secret = os.environ.get("VECTORIZER_API_SECRET") or env.get("VECTORIZER_API_SECRET", "")
    if not api_id or not secret:
        sys.exit(
            "Missing VECTORIZER_API_ID / VECTORIZER_API_SECRET.\n"
            "Fill them in `.env` (see `.env.example`) or export them as environment variables."
        )
    return api_id, secret


def _auth(username, password):
    return "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()


def main():
    parser = argparse.ArgumentParser(description="Vectorize a raster image via Vectorizer.AI")
    parser.add_argument("image", help="Input raster image (PNG/JPG/WebP/GIF/BMP)")
    parser.add_argument("-o", "--output", default=".",
                        help="Output file or directory (default: current dir)")
    parser.add_argument("--format", default="svg", choices=["svg", "pdf", "eps", "dxf", "png"],
                        help="Output format (default: svg)")
    args = parser.parse_args()

    api_id, secret = load_creds()
    input_path = Path(args.image)
    if not input_path.exists():
        sys.exit(f"Image not found: {input_path}")

    boundary = "----Vectorizer" + uuid.uuid4().hex
    ctype = mimetypes.guess_type(input_path.name)[0] or "application/octet-stream"

    parts = []
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{input_path.name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n".encode()
    )
    parts.append(input_path.read_bytes())
    parts.append(f"\r\n--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="output.file_format"\r\n\r\n{args.format}\r\n'.encode()
    )
    parts.append(f"--{boundary}--\r\n".encode())

    req = urlrequest.Request(
        f"{API_BASE}/vectorize",
        data=b"".join(parts),
        method="POST",
        headers={
            "Authorization": _auth(api_id, secret),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json, application/octet-stream",
        },
    )
    try:
        with urlrequest.urlopen(req) as resp:
            blob = resp.read()
            image_token = resp.headers.get("X-Image-Token")
    except urlrequest.HTTPError as e:
        try:
            detail = json.loads(e.read().decode())
        except Exception:
            detail = ""
        sys.exit(f"API error {e.code}: {detail or e.reason}")

    out = Path(args.output)
    if out.exists() and out.is_dir():
        out = out / f"{input_path.stem}.{args.format}"
    out.write_bytes(blob)
    print(f"Saved {out} ({len(blob)} bytes)")
    if image_token:
        print(f"X-Image-Token: {image_token}")


if __name__ == "__main__":
    main()