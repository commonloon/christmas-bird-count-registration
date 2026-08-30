# Updated by Claude AI on 2026-08-29
"""
IP blocking service for bot defense.
Tracks 404 errors, manages honeypot traps, and maintains blocked IP list in PostgreSQL.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from cachetools import TTLCache
from threading import Lock
import logging
from sqlalchemy.dialects.postgresql import insert as pg_insert
from config.ip_blocking import *
from models.db import BlockedIP, IPViolation

logger = logging.getLogger(__name__)

# In-memory cache for the blocked-IP lookup only. This is safe to keep
# per-instance: a cache miss just costs one extra DB read, it never
# causes a missed block. Violation counting (below) cannot use per-instance
# memory the same way - see track_404().
BLOCKED_IP_CACHE = TTLCache(maxsize=CACHE_SIZE, ttl=CACHE_TTL_SECONDS)
CACHE_LOCK = Lock()


class IPBlockerService:
    """Service for managing IP blocking with PostgreSQL persistence."""

    def __init__(self, db_session):
        self.db = db_session

    def is_blocked(self, ip_address: str) -> bool:
        """Check if IP is currently blocked (cache-first approach)."""
        with CACHE_LOCK:
            if ip_address in BLOCKED_IP_CACHE:
                return BLOCKED_IP_CACHE[ip_address]

        row = self.db.query(BlockedIP).filter_by(ip_address=ip_address).first()

        if row:
            if datetime.now(timezone.utc) < row.expires_at:
                with CACHE_LOCK:
                    BLOCKED_IP_CACHE[ip_address] = True
                return True
            else:
                self._auto_unblock(ip_address)
                return False

        return False

    def add_block(self, ip_address: str, reason: str,
                  trigger_count: int = 0, user_agent: str = '',
                  violation_url: str = '', violation_history: List[Dict] = None) -> str:
        """Add IP to block list with PostgreSQL persistence."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=BLOCK_DURATION_HOURS)

        row = self.db.query(BlockedIP).filter_by(ip_address=ip_address).first()
        if row:
            row.blocked_at = now
            row.expires_at = expires
            row.reason = reason
            row.trigger_count = trigger_count
            row.user_agent = user_agent
            row.last_violation_url = violation_url
            row.violation_history = violation_history or []
            row.total_violations = trigger_count
            row.auto_unblocked = False
        else:
            row = BlockedIP(
                ip_address=ip_address,
                blocked_at=now,
                expires_at=expires,
                reason=reason,
                trigger_count=trigger_count,
                user_agent=user_agent,
                last_violation_url=violation_url,
                violation_history=violation_history or [],
                total_violations=trigger_count,
                auto_unblocked=False,
            )
            self.db.add(row)
        self.db.commit()

        with CACHE_LOCK:
            BLOCKED_IP_CACHE[ip_address] = True

        if ENABLE_BLOCK_LOGGING:
            logger.warning(f"IP_BLOCK: {ip_address} blocked for {reason} (count: {trigger_count}, url: {violation_url})")

        return ip_address

    def remove_block(self, ip_address: str) -> bool:
        """Manually unblock an IP (admin action)."""
        try:
            self.db.query(BlockedIP).filter_by(ip_address=ip_address).delete()
            self.db.commit()

            with CACHE_LOCK:
                BLOCKED_IP_CACHE.pop(ip_address, None)

            logger.info(f"IP_UNBLOCK: {ip_address} manually unblocked")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to unblock {ip_address}: {e}")
            return False

    def track_404(self, ip_address: str, url_path: str, user_agent: str = '') -> Optional[str]:
        """
        Track 404 violation for IP. Returns block ID if threshold exceeded.

        Counter is stored in PostgreSQL (not per-instance memory) because the app can run
        with multiple processes/instances, each of which would otherwise keep its own
        undersized count and never see the true total (see services/limiter.py for the
        one remaining per-instance gap, and REMINDER.md for the planned fix).

        Uses an atomic upsert-increment (INSERT ... ON CONFLICT) rather than read-then-write,
        to avoid a race between concurrent requests from the same IP.
        """
        window_bucket = int(time.time() // VIOLATION_WINDOW_SECONDS)
        now = datetime.now(timezone.utc)

        stmt = pg_insert(IPViolation).values(
            ip_address=ip_address,
            window_bucket=window_bucket,
            count=1,
            last_violation_url=url_path,
            last_seen=now,
            expires_at=now + timedelta(minutes=5),
        ).on_conflict_do_update(
            index_elements=['ip_address', 'window_bucket'],
            set_={
                'count': IPViolation.count + 1,
                'last_violation_url': url_path,
                'last_seen': now,
            },
        )
        self.db.execute(stmt)
        self.db.commit()

        row = self.db.query(IPViolation).filter_by(
            ip_address=ip_address, window_bucket=window_bucket
        ).first()
        count = row.count if row else 0

        if count >= MAX_404_PER_MINUTE:
            block_id = self.add_block(
                ip_address=ip_address,
                reason='404_threshold',
                trigger_count=count,
                user_agent=user_agent,
                violation_url=url_path,
                violation_history=[{'timestamp': now.isoformat(), 'path': url_path}],
            )

            # Already blocked - no need to keep counting this window
            self.db.query(IPViolation).filter_by(
                ip_address=ip_address, window_bucket=window_bucket
            ).delete()
            self.db.commit()

            return block_id

        return None

    def trigger_honeypot(self, ip_address: str, trap_url: str, user_agent: str = '') -> str:
        """Immediately block IP that accessed honeypot trap."""
        return self.add_block(
            ip_address=ip_address,
            reason='honeypot_trap',
            trigger_count=1,
            user_agent=user_agent,
            violation_url=trap_url,
            violation_history=[{
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'path': trap_url,
            }],
        )

    def cleanup_expired(self, delete_old: bool = True) -> int:
        """
        Clean up expired blocks (must now be run periodically via FullHost Task Scheduler -
        PostgreSQL has no equivalent of Firestore's TTL-policy auto-expiry).
        """
        now = datetime.now(timezone.utc)
        count = 0

        expired_blocks = self.db.query(BlockedIP).filter(
            BlockedIP.expires_at < now, BlockedIP.auto_unblocked == False  # noqa: E712
        ).all()

        if delete_old:
            delete_cutoff = now - timedelta(days=7)
            for row in expired_blocks:
                if row.expires_at < delete_cutoff:
                    self.db.delete(row)
                else:
                    row.auto_unblocked = True
                count += 1
                with CACHE_LOCK:
                    BLOCKED_IP_CACHE.pop(row.ip_address, None)
        else:
            for row in expired_blocks:
                row.auto_unblocked = True
                count += 1
                with CACHE_LOCK:
                    BLOCKED_IP_CACHE.pop(row.ip_address, None)

        if count > 0:
            self.db.commit()
            logger.info(f"IP_CLEANUP: Processed {count} expired blocks")

        # Also prune stale violation-window rows (Firestore's TTL policy handled this before)
        self.db.query(IPViolation).filter(IPViolation.expires_at < now).delete()
        self.db.commit()

        return count

    def _auto_unblock(self, ip_address: str) -> None:
        """Mark block as auto-unblocked (called when expired block is accessed)."""
        try:
            row = self.db.query(BlockedIP).filter_by(ip_address=ip_address).first()
            if row:
                row.auto_unblocked = True
                self.db.commit()

            with CACHE_LOCK:
                BLOCKED_IP_CACHE.pop(ip_address, None)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to auto-unblock {ip_address}: {e}")

    def get_all_blocks(self, include_expired: bool = False) -> List[Dict]:
        """Get all blocked IPs for admin dashboard."""
        query = self.db.query(BlockedIP)
        if not include_expired:
            query = query.filter(BlockedIP.expires_at > datetime.now(timezone.utc))

        blocks = [row.to_dict() for row in query.all()]

        if include_expired:
            blocks.sort(key=lambda x: x.get('blocked_at') or datetime.min, reverse=True)
        else:
            blocks.sort(key=lambda x: (
                x.get('expires_at') or datetime.min,
                -(x.get('blocked_at') or datetime.min).timestamp() if x.get('blocked_at') else 0,
            ))

        return blocks

    def get_block_stats(self) -> Dict:
        """Get statistics for monitoring."""
        all_blocks = self.get_all_blocks(include_expired=True)
        active_blocks = [b for b in all_blocks if not b.get('auto_unblocked', False)]

        return {
            'total_blocks': len(all_blocks),
            'active_blocks': len(active_blocks),
            'honeypot_blocks': len([b for b in active_blocks if b['reason'] == 'honeypot_trap']),
            '404_blocks': len([b for b in active_blocks if b['reason'] == '404_threshold']),
            'cache_size': len(BLOCKED_IP_CACHE),
        }


def get_client_ip(request) -> str:
    """Extract client IP from request (handles X-Forwarded-For behind a reverse proxy)."""
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.remote_addr or 'unknown'
