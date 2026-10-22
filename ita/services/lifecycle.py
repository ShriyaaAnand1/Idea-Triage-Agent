import asyncio
from contextlib import asynccontextmanager
from database.connection import get_checkpointer
from database.queries import ensure_ideas_table
from fastapi import FastAPI
from database.approvals import escalate_expired_approvals
from logger.logging import logger

ESCALATION_CHECK_SECONDS = 10


async def escalation_loop():
    logger.info("Approval escalation loop started")

    while True:
        try:
            count = await asyncio.to_thread(
                escalate_expired_approvals
            )
            if count:
                logger.warning(
                    "Escalated %s approval(s)",
                    count,
                )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Approval escalation check failed"
            )

        await asyncio.sleep(ESCALATION_CHECK_SECONDS)

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_ideas_table()

    context = get_checkpointer()
    checkpointer = context.__enter__()
    escalation_task = None

    try:
        checkpointer.setup()
        escalation_task = asyncio.create_task(
            escalation_loop()
        )

        yield

    finally:
        if escalation_task:
            escalation_task.cancel()

            try:
                await escalation_task
            except asyncio.CancelledError:
                pass

        context.__exit__(None, None, None)