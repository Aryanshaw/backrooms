import json
import os
from pathlib import Path

from fastmcp import Context
from config.logger import get_logger

logger = get_logger(__name__)


class BackroomsBase:
    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.user_id = os.getenv("BACKROOMS_USER_ID")
        if not self.user_id:
            raise ValueError("BACKROOMS_USER_ID is not set in environment.")

        self.db = self.ctx.lifespan_context.get("db")
        if not self.db:
            raise ValueError("FAILED: db is None — lifespan context not populated")

    def _config_path(self) -> Path:
        return Path.cwd() / ".backroom.json"

    def _read_config(self) -> dict:
        return json.loads(self._config_path().read_text())

    def _write_config(self, config_data: dict) -> None:
        self._config_path().write_text(json.dumps(config_data, indent=4))
