"""
heartbeat.py — Device Heartbeat and Command Handler

Sends periodic heartbeats to the server and processes remote commands.
Extracted from sync_engine.py for maintainability.
"""

import os
import sys
import time
from typing import Optional

import config
import network_client
from loguru import logger
from state import _stop_event

from database import get_connection


def get_device_id() -> Optional[int]:
    """Gets device_id from the local settings table."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'device_id'")
        row = cur.fetchone()
        if row:
            return int(row[0])
        return None
    except Exception as e:
        logger.error("Error reading device_id: {}", e)
        return None


def heartbeat_worker():
    """Lightweight daemon thread: send heartbeat every 60s, process commands."""
    while not _stop_event.is_set():
        try:
            if not config.sync_suspended and network_client.health_check():
                device_id = get_device_id()
                if device_id is None:
                    _stop_event.wait(60)
                    continue

                hb_success, pending_commands = network_client.send_heartbeat(device_id)
                if hb_success and pending_commands:
                    for cmd in pending_commands:
                        command_name = cmd.get("command")
                        cmd_id = cmd.get("id")
                        logger.info("Received remote command: {}", command_name)

                        if command_name == "WAKE":
                            logger.info("WAKE signal received from server")
                            network_client.ack_command(device_id, cmd_id)
                        elif command_name == "REVOKE":
                            logger.warning("DEVICE ACCESS REVOKED — wiping local credentials")
                            conn = get_connection()
                            cur = conn.cursor()
                            cur.execute("DELETE FROM settings WHERE key IN ('access_token', 'device_id', 'encryption_key')")
                            conn.commit()
                            network_client.ack_command(device_id, cmd_id)
                            os._exit(0)
                        else:
                            network_client.ack_command(device_id, cmd_id)
        except Exception:
            logger.exception("Error in heartbeat worker")

        _stop_event.wait(60)
