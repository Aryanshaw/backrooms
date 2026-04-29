# tools/messaging.py
from typing import Optional
from fastmcp import FastMCP, Context
from config.logger import get_logger
from sqlalchemy import text

# from tools import messaging


logger = get_logger(__name__)

messaging_router = FastMCP("messaging")