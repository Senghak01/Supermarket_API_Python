import datetime
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService

logger = logging.getLogger("supermarket.background")
scheduler = AsyncIOScheduler()


async def job_expire_unpaid_orders() -> None:
    """Runs every minute: cancels orders still Pending 30 minutes after creation."""
    db = SessionLocal()
    try:
        order_service = OrderService(db)
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            minutes=settings.UNPAID_ORDER_EXPIRY_MINUTES
        )
        cancelled = order_service.expire_unpaid_orders(cutoff)
        if cancelled > 0:
            logger.info(f"Order expiry job: cancelled {cancelled} unpaid expired orders.")
    except Exception as ex:
        logger.error(f"Error in order expiry job: {ex}")
    finally:
        db.close()


async def job_verify_pending_payments() -> None:
    """Runs every 5 seconds: checks pending online payments from past 35 minutes."""
    db = SessionLocal()
    try:
        payment_service = PaymentService(db)
        # 30 min expiry + 5 min safety window
        created_after = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            minutes=settings.UNPAID_ORDER_EXPIRY_MINUTES + 5
        )
        verified = await payment_service.verify_pending_payments(created_after)
        if verified > 0:
            logger.info(f"Payment verification job: verified and confirmed {verified} payments.")
    except Exception as ex:
        logger.error(f"Error in payment verification job: {ex}")
    finally:
        db.close()


def start_scheduler() -> None:
    """Start background scheduler if not already running."""
    if not scheduler.running:
        scheduler.add_job(
            job_expire_unpaid_orders,
            trigger="interval",
            minutes=1,
            id="job_expire_unpaid_orders",
            replace_existing=True,
        )
        scheduler.add_job(
            job_verify_pending_payments,
            trigger="interval",
            seconds=settings.BAKONG_POLL_INTERVAL_SECONDS,
            id="job_verify_pending_payments",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Background job scheduler started.")


def stop_scheduler() -> None:
    """Stop background scheduler."""
    if scheduler.running:
        try:
            if scheduler._eventloop and not scheduler._eventloop.is_closed():
                scheduler.shutdown(wait=False)
        except Exception:
            pass
        logger.info("Background job scheduler stopped.")
