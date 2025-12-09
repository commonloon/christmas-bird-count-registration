# Updated by Claude AI on 2025-12-09
"""
IP blocking service for bot defense.
Tracks 404 errors, manages honeypot traps, and maintains blocked IP list in Firestore.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List
from cachetools import TTLCache
from threading import Lock
import logging
from flask import request
from config.ip_blocking import *

logger = logging.getLogger(__name__)

# In-memory caches with thread safety
BLOCKED_IP_CACHE = TTLCache(maxsize=CACHE_SIZE, ttl=CACHE_TTL_SECONDS)
VIOLATION_TRACKER = TTLCache(maxsize=VIOLATION_TRACKER_SIZE, ttl=VIOLATION_WINDOW_SECONDS)
CACHE_LOCK = Lock()
TRACKER_LOCK = Lock()


class IPBlockerService:
    """Service for managing IP blocking with Firestore persistence."""

    def __init__(self, db_client):
        self.db = db_client
        self.collection = 'blocked_ips'

    def is_blocked(self, ip_address: str) -> bool:
        """
        Check if IP is currently blocked (cache-first approach).

        Args:
            ip_address: Client IP address to check

        Returns:
            True if IP is blocked, False otherwise
        """
        # Check cache first (fast path)
        with CACHE_LOCK:
            if ip_address in BLOCKED_IP_CACHE:
                return BLOCKED_IP_CACHE[ip_address]

        # Check Firestore (slow path)
        doc = self.db.collection(self.collection).document(ip_address).get()

        if doc.exists:
            data = doc.to_dict()
            # Check if block expired
            if datetime.now() < data['expires_at']:
                # Still blocked - cache result
                with CACHE_LOCK:
                    BLOCKED_IP_CACHE[ip_address] = True
                return True
            else:
                # Expired - auto cleanup
                self._auto_unblock(ip_address)
                return False

        return False

    def add_block(self, ip_address: str, reason: str,
                  trigger_count: int = 0, user_agent: str = '',
                  violation_url: str = '', violation_history: List[Dict] = None) -> str:
        """
        Add IP to block list with Firestore persistence.

        Args:
            ip_address: IP to block
            reason: "404_threshold" or "honeypot_trap"
            trigger_count: Number of violations that triggered block
            user_agent: Browser/bot user agent string
            violation_url: Last URL that triggered the block
            violation_history: List of recent violations

        Returns:
            IP address (document ID)
        """
        now = datetime.now()
        expires = now + timedelta(hours=BLOCK_DURATION_HOURS)

        # Convert datetime objects in violation history to timestamps
        if violation_history:
            for entry in violation_history:
                if isinstance(entry.get('timestamp'), datetime):
                    entry['timestamp'] = entry['timestamp']

        block_data = {
            'ip_address': ip_address,
            'blocked_at': now,
            'expires_at': expires,
            'reason': reason,
            'trigger_count': trigger_count,
            'user_agent': user_agent,
            'last_violation_url': violation_url,
            'violation_history': violation_history or [],
            'total_violations': trigger_count,
            'auto_unblocked': False
        }

        # Store in Firestore with IP as document ID
        self.db.collection(self.collection).document(ip_address).set(block_data)

        # Update cache
        with CACHE_LOCK:
            BLOCKED_IP_CACHE[ip_address] = True

        # Log security event
        if ENABLE_BLOCK_LOGGING:
            logger.warning(f"IP_BLOCK: {ip_address} blocked for {reason} (count: {trigger_count}, url: {violation_url})")

        return ip_address

    def remove_block(self, ip_address: str) -> bool:
        """
        Manually unblock an IP (admin action).

        Args:
            ip_address: IP to unblock

        Returns:
            True if successful, False otherwise
        """
        try:
            self.db.collection(self.collection).document(ip_address).delete()

            # Clear from cache
            with CACHE_LOCK:
                BLOCKED_IP_CACHE.pop(ip_address, None)

            logger.info(f"IP_UNBLOCK: {ip_address} manually unblocked")
            return True
        except Exception as e:
            logger.error(f"Failed to unblock {ip_address}: {e}")
            return False

    def track_404(self, ip_address: str, url_path: str, user_agent: str = '') -> Optional[str]:
        """
        Track 404 violation for IP. Returns block ID if threshold exceeded.

        Args:
            ip_address: Client IP that triggered 404
            url_path: URL path that was not found
            user_agent: Browser/bot user agent string

        Returns:
            IP address if blocked, None otherwise
        """
        with TRACKER_LOCK:
            if ip_address not in VIOLATION_TRACKER:
                VIOLATION_TRACKER[ip_address] = {
                    'count': 0,
                    'first_seen': datetime.now(),
                    'urls': []
                }

            tracker = VIOLATION_TRACKER[ip_address]
            tracker['count'] += 1
            tracker['urls'].append({
                'timestamp': datetime.now(),
                'path': url_path
            })

            # Limit history size
            if len(tracker['urls']) > MAX_VIOLATION_HISTORY:
                tracker['urls'] = tracker['urls'][-MAX_VIOLATION_HISTORY:]

            # Check threshold
            if tracker['count'] >= MAX_404_PER_MINUTE:
                # Block this IP
                violation_history = tracker['urls'].copy()
                block_id = self.add_block(
                    ip_address=ip_address,
                    reason='404_threshold',
                    trigger_count=tracker['count'],
                    user_agent=user_agent,
                    violation_url=url_path,
                    violation_history=violation_history
                )

                # Clear tracker (already blocked)
                del VIOLATION_TRACKER[ip_address]

                return block_id

        return None

    def trigger_honeypot(self, ip_address: str, trap_url: str, user_agent: str = '') -> str:
        """
        Immediately block IP that accessed honeypot trap.

        Args:
            ip_address: IP that accessed honeypot
            trap_url: Honeypot URL that was accessed
            user_agent: Browser/bot user agent string

        Returns:
            IP address (document ID)
        """
        return self.add_block(
            ip_address=ip_address,
            reason='honeypot_trap',
            trigger_count=1,
            user_agent=user_agent,
            violation_url=trap_url,
            violation_history=[{
                'timestamp': datetime.now(),
                'path': trap_url
            }]
        )

    def cleanup_expired(self) -> int:
        """
        Clean up expired blocks (run periodically or on-demand).

        Returns:
            Number of blocks cleaned up
        """
        from google.cloud.firestore_v1.base_query import FieldFilter

        now = datetime.now()
        count = 0

        # Query expired blocks
        query = (self.db.collection(self.collection)
                .where(filter=FieldFilter('expires_at', '<', now))
                .where(filter=FieldFilter('auto_unblocked', '==', False)))

        batch = self.db.batch()
        for doc in query.stream():
            # Mark as auto-unblocked (keep for audit trail)
            doc_ref = self.db.collection(self.collection).document(doc.id)
            batch.update(doc_ref, {'auto_unblocked': True})
            count += 1

            # Clear from cache
            with CACHE_LOCK:
                BLOCKED_IP_CACHE.pop(doc.id, None)

        if count > 0:
            batch.commit()
            logger.info(f"IP_CLEANUP: Removed {count} expired blocks")

        return count

    def _auto_unblock(self, ip_address: str) -> None:
        """
        Mark block as auto-unblocked (called when expired block is accessed).

        Args:
            ip_address: IP to mark as auto-unblocked
        """
        try:
            self.db.collection(self.collection).document(ip_address).update({
                'auto_unblocked': True
            })

            with CACHE_LOCK:
                BLOCKED_IP_CACHE.pop(ip_address, None)
        except Exception as e:
            logger.error(f"Failed to auto-unblock {ip_address}: {e}")

    def get_all_blocks(self, include_expired: bool = False) -> List[Dict]:
        """
        Get all blocked IPs for admin dashboard.

        Args:
            include_expired: If True, include expired blocks

        Returns:
            List of block records
        """
        from google.cloud.firestore_v1.base_query import FieldFilter

        blocks = []

        if include_expired:
            query = self.db.collection(self.collection).order_by('blocked_at', direction='DESCENDING')
        else:
            now = datetime.now()
            query = (self.db.collection(self.collection)
                    .where(filter=FieldFilter('expires_at', '>', now))
                    .order_by('expires_at')
                    .order_by('blocked_at', direction='DESCENDING'))

        for doc in query.stream():
            data = doc.to_dict()
            data['ip_address'] = doc.id  # Document ID is the IP
            blocks.append(data)

        return blocks

    def get_block_stats(self) -> Dict:
        """
        Get statistics for monitoring.

        Returns:
            Dictionary with block statistics
        """
        all_blocks = self.get_all_blocks(include_expired=True)
        active_blocks = [b for b in all_blocks if not b.get('auto_unblocked', False)]

        stats = {
            'total_blocks': len(all_blocks),
            'active_blocks': len(active_blocks),
            'honeypot_blocks': len([b for b in active_blocks if b['reason'] == 'honeypot_trap']),
            '404_blocks': len([b for b in active_blocks if b['reason'] == '404_threshold']),
            'cache_size': len(BLOCKED_IP_CACHE),
            'tracker_size': len(VIOLATION_TRACKER)
        }

        return stats


def get_client_ip(request) -> str:
    """
    Extract client IP from request (handles X-Forwarded-For behind Cloud Run proxy).

    Args:
        request: Flask request object

    Returns:
        Client IP address
    """
    # Use X-Forwarded-For header if behind a proxy (like Cloud Run)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # Take first IP in chain (original client)
        return forwarded_for.split(',')[0].strip()
    return request.remote_addr or 'unknown'
