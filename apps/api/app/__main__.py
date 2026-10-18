"""python -m app — server demo lokal. Bind loopback secara default; tidak dibuka ke LAN/internet."""
import argparse
import logging

import uvicorn

from .main import create_app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WALLACEA API (lokal)")
    parser.add_argument("--host", default="127.0.0.1", help="Default 127.0.0.1 (loopback). Jangan 0.0.0.0 tanpa autentikasi.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        logging.warning("Server di-bind ke %s. API ini TIDAK memiliki autentikasi.", args.host)
    uvicorn.run(create_app(), host=args.host, port=args.port)
