"""
events.py — Server-Sent Events (SSE) real-time state bus.

Every mutation endpoint (announce, upload complete, delete, conflict resolve)
publishes an event to an in-memory broadcast channel.  Connected clients
(UI, agent) receive the event within milliseconds.

Architecture:
    POST /sync/announce  ──→  DB mutation  ──→  publish_event()  ──→  SSE stream
    POST /sync/upload    ──→  DB mutation  ──→  publish_event()  ──→  SSE stream
    DELETE /sync/file    ──→  DB mutation  ──→  publish_event()  ──→  SSE stream

The broadcast uses asyncio.Queue per subscriber — no Redis needed for
single-server deployments.  For multi-server, swap in Redis Pub/Sub.
"""

import asyncio
import json
from loguru import logger
import os
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
import redis.asyncio as aioredis
from ..dependencies import get_current_user
from .. import models

router = APIRouter(prefix="/events", tags=["Events"])

# ── In-memory broadcast ──────────────────────────────────────────────────────
# Key: user_id → set of asyncio.Queue
# Each connected client gets its own queue.  publish_event fans out to all.
_subscribers: dict[int, set[asyncio.Queue]] = {}
_lock = asyncio.Lock()


async def subscribe(user_id: int) -> asyncio.Queue:
    """Register a new subscriber queue for a user."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    async with _lock:
        if user_id not in _subscribers:
            _subscribers[user_id] = set()
        _subscribers[user_id].add(queue)
    return queue


async def unsubscribe(user_id: int, queue: asyncio.Queue):
    """Remove a subscriber queue."""
    async with _lock:
        if user_id in _subscribers:
            _subscribers[user_id].discard(queue)
            if not _subscribers[user_id]:
                del _subscribers[user_id]


async def publish_event(user_id: int, event_type: str, payload: dict):
    """Fan-out an event to all subscribers of a user.

    Events are JSON-serialized and sent as SSE `data:` lines.
    If a subscriber's queue is full (slow consumer), the event is dropped
    for that subscriber — this is a deliberate backpressure decision.
    Dropped events are harmless because the client can always re-fetch
    the full state via GET /sync/metadata.

    Args:
        user_id:    The user whose subscribers should receive the event.
        event_type: One of: file_created, file_updated, file_deleted,
                    upload_complete, upload_failed, conflict_detected.
        payload:    Arbitrary dict — typically {file_id, file_path, version_id, ...}
    """
    message = {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    async with _lock:
        queues = _subscribers.get(user_id, set()).copy()

    dropped = 0
    for q in queues:
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            dropped += 1

    if dropped:
        logger.warning(
            "Dropped SSE event for {} slow subscriber(s) of user_id={}",
            dropped, user_id,
        )


async def listen_to_redis(redis_url: str):
    """Background task to bridge Redis Pub/Sub events to the SSE stream.
    
    This listener allows the RQ worker (running in a separate process)
    to notify connected SSE clients when long-running jobs complete.
    """
    logger.info("[REDIS] Starting event bridge listener on {}", redis_url)
    r = aioredis.from_url(redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("shadowdrive:events")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    user_id = payload.get("user_id")
                    event_type = payload.get("type")
                    data = payload.get("data")
                    
                    if user_id and event_type:
                        logger.info(
                            "[REDIS] Forwarding {} to SSE for user_id={}",
                            event_type, user_id
                        )
                        await publish_event(user_id, event_type, data)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning("[REDIS] Invalid message payload: {}", e)
    except asyncio.CancelledError:
        logger.info("[REDIS] Listener task cancelled.")
    except Exception as e:
        logger.error("[REDIS] Listener bridge encountered an error: {}", e)
    finally:
        await pubsub.unsubscribe("shadowdrive:events")
        await r.aclose()


# ── SSE Streaming Endpoint ──────────────────────────────────────────────────

@router.get("/stream")
async def event_stream(
    request: Request,
    current_user: models.User = Depends(get_current_user),
):
    """GET /events/stream — SSE endpoint.

    The client opens a long-lived HTTP connection.  The server pushes
    JSON events as they occur.  On disconnect, the subscriber queue
    is cleaned up.

    Response format (SSE spec):
        event: file_updated
        data: {"type":"file_updated","timestamp":"...","data":{...}}

        event: heartbeat
        data: {"type":"heartbeat"}

    The heartbeat fires every 30 seconds to keep the connection alive
    through proxies and load balancers that kill idle connections.
    """
    user_id = current_user.id
    queue = await subscribe(user_id)

    async def generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for event with 30-second timeout (heartbeat interval)
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_type = message.get("type", "message")
                    data = json.dumps(message)
                    yield f"event: {event_type}\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f"event: heartbeat\ndata: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            await unsubscribe(user_id, queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
