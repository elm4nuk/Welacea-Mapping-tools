"""python -m app — server demo lokal. Bind loopback secara default; tidak dibuka ke LAN/internet."""
import argparse
import logging
import sys
from pathlib import Path

import uvicorn

from .config import API_ROOT
from .envfile import EnvFileError, load_env_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WALLACEA API (lokal)")
    parser.add_argument("--host", default="127.0.0.1", help="Default 127.0.0.1 (loopback). Jangan 0.0.0.0 tanpa autentikasi.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--env-file", type=Path, default=None,
                        help="Berkas .env yang dimuat sebelum start (default: apps/api/.env bila ada). "
                             "Variabel yang sudah diset di terminal tidak ditimpa.")
    parser.add_argument("--no-env-file", action="store_true", help="Jangan memuat berkas .env apa pun.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
    logging.getLogger("alembic").setLevel(logging.WARNING)
    if not args.no_env_file:
        env_file = args.env_file or API_ROOT / ".env"
        if args.env_file and not env_file.is_file():
            sys.exit(f"Berkas --env-file tidak ditemukan: {env_file}")
        if env_file.is_file():
            try:
                names = load_env_file(env_file)
            except EnvFileError as exc:
                sys.exit(str(exc))
            logging.info("Memuat %s: %s", env_file, ", ".join(names) if names else "(tidak ada variabel baru)")
    from .main import create_app  # setelah .env dimuat, karena load_settings() membaca os.environ

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        logging.warning("Server di-bind ke %s. API ini TIDAK memiliki autentikasi.", args.host)
    app = create_app()
    info = app.state.detector.info()
    logging.info("Model: mode=%s state=%s — %s", info.mode, info.state, info.message)
    uvicorn.run(app, host=args.host, port=args.port)
