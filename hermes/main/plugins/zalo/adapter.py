"""
Zalo Platform Adapter for Hermes Agent.

Bridges to a companion Node.js process (hermes-zalo-plugin) that runs
zca-js (the unofficial Zalo personal API). Communication:

    inbound  : SSE stream  GET  {bridge}/events   (Zalo -> Hermes)
    outbound : REST        POST {bridge}/send, /send-attachment, ...

Configuration in config.yaml::

    gateway:
      platforms:
        zalo:
          enabled: true
          extra:
            bridge_url: "http://127.0.0.1:8787"
            bridge_token: ""              # optional shared secret
            allowed_users: []             # empty = allow all (with allow_all), or list of uidFrom
            allow_all_users: false
            group_require_mention: true   # only reply in groups when addressed
            max_message_length: 4000

Or via environment variables (override config.yaml):
    ZALO_PLUGIN_URL, ZALO_PLUGIN_TOKEN, ZALO_ALLOWED_USERS,
    ZALO_ALLOW_ALL_USERS, ZALO_HOME_CHANNEL, ZALO_GROUP_REQUIRE_MENTION
"""

import asyncio
import json
import logging
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Hermes loads this file as hermes_plugins.zalo_platform.adapter. Relative
# imports then miss siblings next to the repo plugin. Put both dirs on path.
_ZALO_PLUGIN_DIR = Path(__file__).resolve().parent
_ZALO_SHARED_PLUGIN = Path(os.getenv("HERMES_SHARED_DATA") or "/opt/data") / "plugins" / "zalo"
for _zalo_dir in (_ZALO_PLUGIN_DIR, _ZALO_SHARED_PLUGIN):
    _zalo_s = str(_zalo_dir)
    if _zalo_dir.is_dir() and _zalo_s not in sys.path:
        sys.path.insert(0, _zalo_s)


def _replica_id() -> str:
    return (os.getenv("HOSTNAME") or socket.gethostname() or "").strip()


def _try_claim_zalo_owner(shared: str, rid: str) -> bool:
    """Atomic mkdir lock + owner file (same contract as hermes-replica-entry.sh)."""
    lockdir = Path(shared) / "zalo_owner.lock"
    owner_path = Path(shared) / "zalo_owner"
    try:
        lockdir.mkdir()
        owner_path.write_text(rid + "\n", encoding="utf-8")
        return True
    except FileExistsError:
        try:
            current = owner_path.read_text(encoding="utf-8").strip()
        except OSError:
            return False
        if current == rid:
            return True
        # Stale: previous owner hostname no longer resolves on the Docker network.
        try:
            socket.getaddrinfo(current, None)
            return False
        except OSError:
            try:
                if lockdir.exists():
                    # Best-effort steal (race-safe enough for 2 replicas).
                    for child in lockdir.iterdir():
                        child.unlink(missing_ok=True)
                    lockdir.rmdir()
                owner_path.unlink(missing_ok=True)
            except OSError:
                return False
            try:
                lockdir.mkdir()
                owner_path.write_text(rid + "\n", encoding="utf-8")
                return True
            except FileExistsError:
                return False


def _is_zalo_owner_replica() -> bool:
    """When Hermes is scaled, only the elected owner may attach to the bridge.

    Compose injects ZALO_PLUGIN_URL into every replica; s6 may restore that env
    after entrypoint clears it. Ownership is recorded by hermes-replica-entry.sh
    at HERMES_SHARED_DATA/zalo_owner (hostname of the winner).
    """
    try:
        replicas = int(os.getenv("HERMES_REPLICAS") or "1")
    except ValueError:
        replicas = 1
    if replicas <= 1:
        return True
    shared = (os.getenv("HERMES_SHARED_DATA") or "/opt/data").rstrip("/")
    rid = _replica_id()
    if not rid:
        return False
    owner_path = Path(shared) / "zalo_owner"
    try:
        owner = owner_path.read_text(encoding="utf-8").strip()
    except OSError:
        owner = ""
    if owner == rid:
        return True
    if owner:
        try:
            socket.getaddrinfo(owner, None)
            return False
        except OSError:
            return _try_claim_zalo_owner(shared, rid)
    return _try_claim_zalo_owner(shared, rid)

logger = logging.getLogger(__name__)

# ── zca-js action → permission-group map (KEEP IN SYNC WITH permissions.js) ──
# Mirrors ACTION_GROUP in the bridge's permissions.js (145 APIs). Bundled
# statically so `hermes gateway setup` can offer a custom action picker even
# when the bridge is offline. If permissions.js changes, regenerate this.
_ACTION_GROUP = {
    "acceptFriendRequest": "manage",
    "addGroupBlockedMember": "destructive",
    "addGroupDeputy": "manage",
    "addPollOptions": "interact",
    "addQuickMessage": "manage",
    "addReaction": "interact",
    "addUnreadMark": "manage",
    "addUserToGroup": "manage",
    "blockUser": "destructive",
    "blockViewFeed": "destructive",
    "changeAccountAvatar": "destructive",
    "changeFriendAlias": "manage",
    "changeGroupAvatar": "manage",
    "changeGroupName": "manage",
    "changeGroupOwner": "destructive",
    "createAutoReply": "manage",
    "createCatalog": "manage",
    "createGroup": "manage",
    "createNote": "interact",
    "createPoll": "interact",
    "createProductCatalog": "manage",
    "createReminder": "interact",
    "deleteAutoReply": "destructive",
    "deleteAvatar": "destructive",
    "deleteCatalog": "destructive",
    "deleteChat": "destructive",
    "deleteGroupInviteBox": "destructive",
    "deleteMessage": "destructive",
    "deleteProductCatalog": "destructive",
    "disableGroupLink": "destructive",
    "disperseGroup": "destructive",
    "editNote": "interact",
    "editReminder": "interact",
    "enableGroupLink": "manage",
    "fetchAccountInfo": "read",
    "findUser": "read",
    "findUserByUsername": "read",
    "forwardMessage": "send",
    "getAliasList": "read",
    "getAllFriends": "read",
    "getAllGroups": "read",
    "getArchivedChatList": "read",
    "getAutoDeleteChat": "read",
    "getAutoReplyList": "read",
    "getAvatarList": "read",
    "getAvatarUrlProfile": "read",
    "getBizAccount": "read",
    "getCatalogList": "read",
    "getCloseFriends": "read",
    "getContext": "read",
    "getCookie": "read",
    "getFriendBoardList": "read",
    "getFriendOnlines": "read",
    "getFriendRecommendations": "read",
    "getFriendRequestStatus": "read",
    "getFullAvatar": "read",
    "getGroupBlockedMember": "read",
    "getGroupChatHistory": "read",
    "getGroupInfo": "read",
    "getGroupInviteBoxInfo": "read",
    "getGroupInviteBoxList": "read",
    "getGroupLinkDetail": "read",
    "getGroupLinkInfo": "read",
    "getGroupMembersInfo": "read",
    "getHiddenConversations": "read",
    "getLabels": "read",
    "getListBoard": "read",
    "getListReminder": "read",
    "getMultiUsersByPhones": "read",
    "getMute": "read",
    "getOwnId": "read",
    "getPendingGroupMembers": "read",
    "getPinConversations": "read",
    "getPollDetail": "read",
    "getProductCatalogList": "read",
    "getQR": "read",
    "getQuickMessageList": "read",
    "getRelatedFriendGroup": "read",
    "getReminder": "read",
    "getReminderResponses": "read",
    "getSentFriendRequest": "read",
    "getSettings": "read",
    "getStickerCategoryDetail": "read",
    "getStickers": "read",
    "getStickersDetail": "read",
    "getUnreadMark": "read",
    "getUserInfo": "read",
    "inviteUserToGroups": "manage",
    "joinGroupInviteBox": "manage",
    "joinGroupLink": "manage",
    "keepAlive": "read",
    "lastOnline": "read",
    "leaveGroup": "destructive",
    "lockPoll": "interact",
    "parseLink": "send",
    "rejectFriendRequest": "manage",
    "removeFriend": "destructive",
    "removeFriendAlias": "manage",
    "removeGroupBlockedMember": "manage",
    "removeGroupDeputy": "manage",
    "removeQuickMessage": "destructive",
    "removeReminder": "destructive",
    "removeUnreadMark": "manage",
    "removeUserFromGroup": "destructive",
    "resetHiddenConversPin": "destructive",
    "reuseAvatar": "manage",
    "reviewPendingMemberRequest": "manage",
    "searchSticker": "read",
    "sendBankCard": "send",
    "sendCard": "send",
    "sendDeliveredEvent": "interact",
    "sendFriendRequest": "manage",
    "sendLink": "send",
    "sendMessage": "send",
    "sendReport": "send",
    "sendSeenEvent": "interact",
    "sendSticker": "send",
    "sendTypingEvent": "send",
    "sendVideo": "send",
    "sendVoice": "send",
    "setHiddenConversations": "manage",
    "setMute": "manage",
    "setPinnedConversations": "manage",
    "sharePoll": "interact",
    "unblockUser": "manage",
    "undo": "interact",
    "undoFriendRequest": "manage",
    "updateActiveStatus": "manage",
    "updateArchivedChatList": "manage",
    "updateAutoDeleteChat": "manage",
    "updateAutoReply": "manage",
    "updateCatalog": "manage",
    "updateGroupSettings": "manage",
    "updateHiddenConversPin": "destructive",
    "updateLabels": "manage",
    "updateLang": "destructive",
    "updateProductCatalog": "manage",
    "updateProfile": "destructive",
    "updateProfileBio": "destructive",
    "updateQuickMessage": "manage",
    "updateSettings": "destructive",
    "upgradeGroupToCommunity": "destructive",
    "uploadAttachment": "send",
    "uploadProductPhoto": "manage",
    "votePoll": "interact",
}

from gateway.platforms.base import (
    BasePlatformAdapter,
    SendResult,
    MessageEvent,
    MessageType,
    cache_image_from_bytes,
    cache_audio_from_bytes,
    cache_document_from_bytes,
)
from gateway.config import Platform

# Component toggles (admin-editable via env; no hardcoded user-facing copy).
ZALO_AUTO_SETHOME_ENV = "ZALO_AUTO_SETHOME"
ZALO_AUTO_SETHOME_DM_ONLY_ENV = "ZALO_AUTO_SETHOME_DM_ONLY"
ZALO_HOME_CHANNEL_ENV = "ZALO_HOME_CHANNEL"

# Inbound attachment reading: worker routing + recall memory live in attachment.py.
from attachment import (  # noqa: E402
    ATTACHMENT_CONTEXT_TTL_S_DEFAULT,
    PROMPT_CHARS as ATTACHMENT_PROMPT_CHARS,
    TEXT_CHARS as ATTACHMENT_TEXT_CHARS,
    attachment_kind,
    caption_payload,
    context_blocks,
    context_decode,
    context_encode,
    context_merge,
    context_newest,
    file_extract_ack_message,
    archive_password_ack_message,
    image_ocr_ack_message,
    image_analyze_ack_message,
    image_analyze_vision_body,
    image_analyze_vision_prompt,
    IMAGE_ANALYZE_VISION_PROMPT_RETRY,
    IMAGE_ANALYZE_VISION_PROMPT_SCENE,
    ocr_excerpt_for_ack,
    vision_image_b64_for_describe,
    quoted_context_snip,
    extract_media_from_quote,
    merge_inbound_quote_media,
    normalize_zalo_msg_type,
    sheet_ref_from_text,
    song_hint_from_filename,
    stage_shared_media,
    workbook_sheet_reply,
    worker_media_path,
)

ATTACHMENT_OCR_TIMEOUT_S = 90.0
ATTACHMENT_OFFICE_TIMEOUT_S = 45.0
ATTACHMENT_AV_TIMEOUT_S = 240.0
# Folder zips with OCR members need a long worker budget (within 15m turn wait).
ATTACHMENT_ARCHIVE_TIMEOUT_S = 600.0
# Default Zalo queue / answering wait: 15 minutes.
ZALO_TURN_WAIT_DEFAULT_S = 900.0
ZALO_TURN_WAIT_MAX_S = 1800.0
ZALO_DRAIN_DEFAULT_S = 1200.0

# AV readiness polling: fast first tick, exponential backoff, same total budget.
AV_POLL_MIN_S = 0.1
AV_POLL_MAX_S = 1.0
AV_POLL_BUDGET_S = 20.0


def _truthy(v) -> bool:
    return str(v if v is not None else "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "active",
    }


def _falsy(v) -> bool:
    return str(v if v is not None else "").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
        "inactive",
    }


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    if _falsy(raw):
        return False
    return _truthy(raw)


def _parse_home_channel(raw: str) -> tuple[str, str]:
    """Parse ZALO_HOME_CHANNEL into (chat_id, thread_type).

    Accepts ``<threadId>`` (defaults to user) or ``<type>:<threadId>``
    where type is ``user`` or ``group``.
    """
    raw = str(raw or "").strip()
    if not raw:
        return "", "user"
    if ":" in raw:
        prefix, _, rest = raw.partition(":")
        prefix = prefix.strip().lower()
        if prefix in {"user", "group"}:
            return rest.strip(), prefix
    return raw, "user"


class ZaloAdapter(BasePlatformAdapter):
    """Zalo adapter that talks to a zca-js bridge over HTTP/SSE."""

    def __init__(self, config, **kwargs):
        platform = Platform("zalo")
        super().__init__(config=config, platform=platform)

        extra = getattr(config, "extra", {}) or {}

        # Empty ZALO_PLUGIN_URL means explicitly disabled (scaled non-owner replicas).
        # Do not fall back to a default bridge URL — that caused dual SSE on Hermes×2.
        if "ZALO_PLUGIN_URL" in os.environ:
            self.bridge_url = (os.environ.get("ZALO_PLUGIN_URL") or "").strip().rstrip("/")
        else:
            self.bridge_url = str(extra.get("bridge_url") or "").strip().rstrip("/")
        if self.bridge_url and not _is_zalo_owner_replica():
            logger.info(
                "Zalo: skipping bridge on non-owner replica host=%s",
                _replica_id(),
            )
            self.bridge_url = ""
        self.bridge_token = os.getenv("ZALO_PLUGIN_TOKEN") or extra.get("bridge_token", "")

        # ── Access control (Telegram-style: empty list = allow everyone) ──────
        # A) ALLOWED_USERS  — uids permitted to command the bot. Empty = all.
        # B) ALLOWED_THREADS — thread/group ids the bot operates in. Empty = all.
        # C) GROUP_MODE     — in groups: "mention" (default) | "all" | "off".
        def _csv_env(name, fallback_key):
            raw = os.getenv(name)
            if raw is not None:
                return [x.strip() for x in raw.split(",") if x.strip()]
            return [str(x).strip() for x in (extra.get(fallback_key, []) or []) if str(x).strip()]

        self.allowed_users = _csv_env("ZALO_ALLOWED_USERS", "allowed_users")
        self._allowed_users = {str(u) for u in self.allowed_users}
        self.allowed_threads = _csv_env("ZALO_ALLOWED_THREADS", "allowed_threads")
        self._allowed_threads = {str(t) for t in self.allowed_threads}

        # Group response mode. Back-compat: legacy ZALO_GROUP_REQUIRE_MENTION=false
        # maps to "all"; true/unset maps to "mention".
        mode = (os.getenv("ZALO_GROUP_MODE") or extra.get("group_mode") or "").strip().lower()
        if not mode:
            legacy = os.getenv("ZALO_GROUP_REQUIRE_MENTION")
            if legacy is not None and not _truthy(legacy):
                mode = "all"
            elif extra.get("group_require_mention") is False:
                mode = "all"
            else:
                mode = "mention"
        if mode not in {"mention", "all", "off"}:
            mode = "mention"
        self.group_mode = mode

        # Deprecated flag: warn but honor (allow_all_users=true had no real effect
        # beyond the old confusing gate; empty allowlist already means "all").
        if os.getenv("ZALO_ALLOW_ALL_USERS") is not None or extra.get("allow_all_users") is not None:
            logger.warning(
                "Zalo: ZALO_ALLOW_ALL_USERS is deprecated and ignored. "
                "Leave ZALO_ALLOWED_USERS empty to allow everyone, or list specific uids."
            )

        # Log inbound uid/threadId to help operators discover ids for allowlists.
        self.log_ids = _truthy(os.getenv("ZALO_LOG_IDS")) if os.getenv("ZALO_LOG_IDS") else bool(extra.get("log_ids", False))

        max_msg = extra.get("max_message_length")
        self.max_message_length = int(max_msg or 4000)

        self._own_id: Optional[str] = None
        self._pending_media = {}  # ASSISTANT_MEDIA_COALESCE
        self._own_name: Optional[str] = None
        # Remember the thread type per chat_id from inbound messages so replies
        # route correctly (user vs group). Zalo thread IDs don't encode type.
        self._thread_types: Dict[str, str] = {}
        self._policy: Optional[Dict[str, Any]] = None

        self._session = None  # aiohttp.ClientSession
        self._sse_task: Optional[asyncio.Task] = None
        self._stop = False
        self._last_event_id = 0
        # Silent auto-sethome (mirrors Yuanbao): stop gateway "📬 No home channel" spam.
        _existing_home = (os.getenv(ZALO_HOME_CHANNEL_ENV) or "").strip()
        self._auto_sethome_done: bool = bool(_existing_home)
        self._as_hold_inflight: set[str] = set()
        self._as_part_delivered: Dict[str, asyncio.Event] = {}
        self._as_inbound_locks: Dict[str, asyncio.Lock] = {}
        self._as_inbound_tasks: set[asyncio.Task] = set()
        self._as_queue_tasks: Dict[str, asyncio.Task] = {}
        self._as_compound_after: Dict[str, int] = {}
        self._as_compound_defer_ack: set[str] = set()
        self._as_compound_thread_type: Dict[str, str] = {}
        self._as_compound_seq_t0: Dict[str, float] = {}
        self._as_workflow_task: Optional[asyncio.Task] = None
        self._as_workflow_inflight: set[asyncio.Task] = set()
        self._as_dest_send_locks: Dict[str, asyncio.Lock] = {}

    @property
    def name(self) -> str:
        return "Zalo"

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.bridge_token:
            h["x-bridge-token"] = self.bridge_token
        return h

    def _sender_may_designate_home(self, sender_id: str, chat_type: str) -> bool:
        """Who may claim ZALO_HOME_CHANNEL via silent auto-sethome."""
        if not _env_flag(ZALO_AUTO_SETHOME_ENV, True):
            return False
        if self._auto_sethome_done:
            return False
        if _env_flag(ZALO_AUTO_SETHOME_DM_ONLY_ENV, True) and chat_type != "dm":
            return False
        # Empty allowlist = everyone (Telegram-style); otherwise only listed uids.
        if self._allowed_users and str(sender_id) not in self._allowed_users:
            return False
        return True

    def _maybe_auto_set_home(self, *, thread_id: str, chat_type: str, sender_id: str, sender_name: str) -> None:
        """Silently designate home before gateway sees the first empty-history turn.

        Hermes gateway emits a /sethome notice on every new session when
        ZALO_HOME_CHANNEL / config home is unset. Setting env + config here
        (before handle_message) makes that check pass for the same turn.
        """
        if not self._sender_may_designate_home(sender_id, chat_type):
            return
        cur = (os.getenv(ZALO_HOME_CHANNEL_ENV) or "").strip()
        # Prefer a DM over a previously empty/group placeholder when DM arrives.
        should_set = (not cur) or (cur.startswith("group:") and chat_type == "dm")
        if chat_type == "dm":
            self._auto_sethome_done = True
        if not should_set:
            return

        home_raw = str(thread_id)
        if chat_type == "group":
            home_raw = f"group:{thread_id}"

        try:
            os.environ[ZALO_HOME_CHANNEL_ENV] = home_raw
            try:
                from hermes_cli.config import save_env_value

                save_env_value(ZALO_HOME_CHANNEL_ENV, home_raw)
            except Exception as e:
                logger.warning("Zalo auto-sethome: save_env_value failed: %s", e)

            try:
                from gateway.config import HomeChannel, persist_home_channel

                persist_home_channel(
                    HomeChannel(
                        platform=self.platform,
                        chat_id=str(thread_id),
                        name=sender_name or str(thread_id),
                        thread_id=None,
                        user_id=str(sender_id) if sender_id else None,
                        scope_id=None,
                    ),
                    enabled_if_new=True,
                )
            except Exception as e:
                logger.warning("Zalo auto-sethome: persist_home_channel failed: %s", e)

            logger.info(
                "Zalo auto-sethome: designated %s (%s) as home channel (silent)",
                home_raw,
                chat_type,
            )
            self._auto_sethome_done = True
        except Exception as e:
            logger.warning("Zalo auto-sethome failed: %s", e)

    # ── Connection lifecycle ──────────────────────────────────────────────

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if not self.bridge_url:
            self._set_fatal_error("config_missing", "ZALO_PLUGIN_URL must be set", retryable=False)
            return False
        try:
            import aiohttp  # noqa
        except ImportError:
            self._set_fatal_error(
                "dependency_missing",
                "aiohttp is required for the Zalo adapter (pip install aiohttp)",
                retryable=False,
            )
            return False

        import aiohttp

        self._stop = False
        self._session = aiohttp.ClientSession()

        # Probe bridge health and login state.
        try:
            async with self._session.get(
                f"{self.bridge_url}/health", timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
        except Exception as e:
            logger.error("Zalo: cannot reach bridge at %s — %s", self.bridge_url, e)
            await self._close_session()
            self._set_fatal_error("bridge_unreachable", f"Bridge unreachable: {e}", retryable=True)
            return False

        if not data.get("loggedIn"):
            qr = data.get("qr")
            msg = (
                "Zalo plugin is running but not logged in. "
                f"Scan the QR (bridge state: {qr}). See {self.bridge_url}/qr.png"
            )
            logger.error("Zalo: %s", msg)
            await self._close_session()
            self._set_fatal_error("not_logged_in", msg, retryable=True)
            return False

        self._own_id = str(data.get("ownId") or "") or None

        # Fetch + log the active action policy (transparency; helps the agent
        # understand what it can/can't do without hitting 403 blindly).
        try:
            async with self._session.get(
                f"{self.bridge_url}/policy", timeout=aiohttp.ClientTimeout(total=10)
            ) as presp:
                policy = await presp.json()
            self._policy = policy
            logger.info(
                "Zalo: action policy groups=%s destructive=%s allowed=%s/%s",
                policy.get("groups"),
                policy.get("allowDestructive"),
                policy.get("allowedActionCount"),
                policy.get("totalActions"),
            )
        except Exception as e:
            self._policy = None
            logger.warning("Zalo: could not fetch action policy: %s", e)

        # Start the SSE inbound loop.
        self._sse_task = asyncio.create_task(self._sse_loop())
        self._as_workflow_task = asyncio.create_task(self._as_workflow_worker())
        self._mark_connected()
        logger.info("Zalo: connected to bridge %s (ownId=%s)", self.bridge_url, self._own_id)
        return True

    async def disconnect(self) -> None:
        self._stop = True
        self._mark_disconnected()
        if self._sse_task and not self._sse_task.done():
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
        if self._as_workflow_task and not self._as_workflow_task.done():
            self._as_workflow_task.cancel()
            try:
                await self._as_workflow_task
            except asyncio.CancelledError:
                pass
        pending = [t for t in getattr(self, "_as_workflow_inflight", set()) if not t.done()]
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await self._close_session()

    async def _close_session(self) -> None:
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass
        self._session = None

    # ── Inbound: SSE loop ─────────────────────────────────────────────────

    async def _wait_for_bridge_ready(self, max_wait_s: float = 30.0) -> bool:
        """Gate SSE connect until host bridge /health responds (bridge restart window)."""
        import aiohttp
        import time as _time

        deadline = _time.monotonic() + max_wait_s
        delay = 0.5
        while _time.monotonic() < deadline and not self._stop:
            try:
                if self._session is None or self._session.closed:
                    self._session = aiohttp.ClientSession()
                headers: dict[str, str] = {}
                if self.bridge_token:
                    headers["x-bridge-token"] = self.bridge_token
                timeout = aiohttp.ClientTimeout(total=8)
                async with self._session.get(
                    f"{self.bridge_url}/health", headers=headers, timeout=timeout
                ) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"health status {resp.status}")
                    data = await resp.json(content_type=None)
                    if isinstance(data, dict) and (
                        data.get("loggedIn") is True or data.get("ownId")
                    ):
                        return True
            except Exception:
                pass
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 3.0)
        return False

    async def _sse_loop(self) -> None:
        """Consume the bridge SSE stream with reconnect + backoff + loop breaker.

        If the same error repeats (poison Last-Event-ID / dead session), drop the
        cursor and recreate the HTTP session so inbound recovers without a
        manual `docker restart hermes`.
        """
        import aiohttp
        import time as _time

        backoff = 1.0
        fail_streak = 0
        same_streak = 0
        last_err_key = ""
        healthy_mark = _time.monotonic()
        while not self._stop:
            try:
                # Session can be closed/nulled after errors or hermes reloads — recreate.
                if self._session is None or self._session.closed:
                    self._session = aiohttp.ClientSession()
                    logger.info("Zalo: recreated aiohttp session for SSE")

                wait_s = min(max(backoff * 2, 5.0), 30.0)
                if not await self._wait_for_bridge_ready(max_wait_s=wait_s):
                    raise RuntimeError(f"bridge health timeout ({self.bridge_url})")

                headers = {}
                if self.bridge_token:
                    headers["x-bridge-token"] = self.bridge_token
                if self._last_event_id:
                    headers["Last-Event-ID"] = str(self._last_event_id)

                timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=None)
                async with self._session.get(
                    f"{self.bridge_url}/events", headers=headers, timeout=timeout
                ) as resp:
                    if resp.status != 200:
                        raise RuntimeError(f"SSE status {resp.status}")
                    backoff = 1.0  # reset after a successful connect
                    fail_streak = 0
                    same_streak = 0
                    last_err_key = ""
                    healthy_mark = _time.monotonic()
                    await self._consume_sse(resp)
                    # Clean stream end — treat as soft disconnect
                    if _time.monotonic() - healthy_mark < 2.0:
                        raise RuntimeError("SSE closed immediately after connect")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if self._stop:
                    break
                fail_streak += 1
                err_key = f"{type(e).__name__}:{str(e)[:120]}"
                if err_key == last_err_key:
                    same_streak += 1
                else:
                    same_streak = 1
                    last_err_key = err_key

                logger.warning(
                    "Zalo: SSE disconnected (%s); reconnecting in %.1fs (fail=%s same=%s)",
                    e,
                    backoff,
                    fail_streak,
                    same_streak,
                )

                # Loop breaker: same error thrashing → drop poison cursor + session
                if same_streak >= 3 or fail_streak in {5, 10, 20}:
                    logger.error(
                        "Zalo: SSE self-heal — drop Last-Event-ID=%s and reset session "
                        "(streak fail=%s same=%s)",
                        self._last_event_id,
                        fail_streak,
                        same_streak,
                    )
                    self._last_event_id = 0
                    try:
                        await self._close_session()
                    except Exception:
                        self._session = None
                    backoff = min(max(backoff, 2.0), 10.0)

                if fail_streak >= 30:
                    # Still keep trying — mark fatal so gateway/watch can restart us,
                    # then soft-reset counters so we don't spam forever at max backoff.
                    try:
                        self._set_fatal_error(
                            "sse_reconnect_loop",
                            f"Zalo SSE reconnect loop ({err_key}). Auto-recovering…",
                            retryable=True,
                        )
                    except Exception:
                        pass
                    fail_streak = 0
                    same_streak = 0
                    self._last_event_id = 0
                    backoff = 5.0

                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _consume_sse(self, resp) -> None:
        event_type = "message"
        data_lines: List[str] = []
        event_id: Optional[int] = None

        async for raw_line in resp.content:
            if self._stop:
                return
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")

            if line == "":
                # Dispatch the accumulated event.
                if data_lines:
                    payload = "\n".join(data_lines)
                    # Never let a poison inbound tear down SSE. Always advance
                    # last_event_id so Last-Event-ID reconnect does not redeliver
                    # the same bad event forever (bridge still "DM fire", hermes silent).
                    try:
                        await self._handle_sse_event(event_type, payload)
                    except Exception as exc:
                        logger.exception(
                            "Zalo: inbound SSE handler error (event=%s id=%s): %s",
                            event_type,
                            event_id,
                            exc,
                        )
                    if event_id is not None:
                        self._last_event_id = event_id
                event_type = "message"
                data_lines = []
                event_id = None
                continue

            if line.startswith(":"):
                continue  # heartbeat / comment
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].lstrip())
            elif line.startswith("id:"):
                try:
                    event_id = int(line[len("id:"):].strip())
                except ValueError:
                    event_id = None
            elif line.startswith("retry:"):
                pass

    async def _handle_sse_event(self, event_type: str, payload: str) -> None:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return

        if not isinstance(data, dict):
            logger.warning(
                "Zalo: ignoring non-object SSE %s payload type=%s",
                event_type,
                type(data).__name__,
            )
            return

        if event_type == "status":
            logger.info("Zalo: bridge status %s", data)
            return
        if event_type == "session_dead":
            await self._on_session_dead(data)
            return
        if event_type == "message":
            # Do not await OCR/AV here — blocking the SSE reader drops follow-up
            # photos while the first image is still being scanned.
            task = asyncio.create_task(self._on_inbound_guarded(data))
            self._as_inbound_tasks.add(task)
            task.add_done_callback(self._as_inbound_tasks.discard)
            return
        # Reaction / undo / friend / group events: surface as a synthetic
        # context line for the agent (no media). These don't trigger a turn by
        # default unless a handler wants them; we log + optionally dispatch.
        if event_type in ("reaction", "undo", "friend_event", "group_event"):
            logger.info("Zalo: %s event %s", event_type, data)
            return

    def _as_inbound_is_admin(self, data: Dict[str, Any] | None) -> bool:
        """True when this SSE payload is a !zalo admin command."""
        blob = data if isinstance(data, dict) else {}
        text = str(blob.get("text") or "")
        return bool(self._zalo_admin_extract_cmd(text))

    async def _on_inbound_guarded(self, data: Dict[str, Any]) -> None:
        """Serialize per-thread inbound work; never raise into the SSE loop.

        ``!zalo`` admin must not wait behind a stuck media/LLM turn on the same thread.
        """
        tid = str((data or {}).get("threadId") or "")
        if self._as_inbound_is_admin(data):
            try:
                await self._on_inbound_message(data)
            except Exception:
                logger.exception("Zalo: inbound admin failed thread=%s", tid or "?")
            return
        locks = getattr(self, "_as_inbound_locks", None)
        if not isinstance(locks, dict):
            self._as_inbound_locks = {}
            locks = self._as_inbound_locks
        lock = locks.get(tid) if tid else None
        if tid and lock is None:
            lock = asyncio.Lock()
            locks[tid] = lock
        try:
            if lock is not None:
                async with lock:
                    await self._on_inbound_message(data)
            else:
                await self._on_inbound_message(data)
        except Exception:
            logger.exception("Zalo: inbound message failed thread=%s", tid or "?")

    async def _on_session_dead(self, data: Dict[str, Any]) -> None:
        """Zalo session ended (logout / kicked / cookie expired)."""
        msg = (data or {}).get("message") or "Zalo session ended."
        code = (data or {}).get("code")
        logger.error("Zalo: SESSION DEAD (code=%s): %s", code, msg)
        # Mark fatal so `hermes gateway status` shows Zalo as down and the
        # gateway can surface/heal it.
        self._set_fatal_error(
            "session_dead",
            f"{msg} Re-scan the QR (POST {self.bridge_url}/relogin then open "
            f"{self.bridge_url}/qr.png) to recover.",
            retryable=True,
        )
        try:
            await self._notify_fatal_error()
        except Exception:
            pass
        # Best-effort: notify the operator in their home channel if known.
        home = os.getenv("ZALO_HOME_CHANNEL")
        if home and self._message_handler:
            chat_id, ttype = _parse_home_channel(home)
            if chat_id:
                try:
                    src = self.build_source(
                        chat_id=chat_id,
                        chat_name=chat_id,
                        chat_type="group" if ttype == "group" else "dm",
                        user_id=self._own_id or "system",
                        user_name="Zalo",
                    )
                    ev = MessageEvent(
                        text=(
                            "⚠️ Zalo session đã hết hạn / bị đăng xuất. "
                            f"({msg}) Cần quét lại QR để khôi phục: "
                            f"POST {self.bridge_url}/relogin rồi mở {self.bridge_url}/qr.png"
                        ),
                        message_type=MessageType.TEXT,
                        source=src,
                        internal=True,
                        timestamp=datetime.now(),
                    )
                    await self.handle_message(ev)
                except Exception:
                    pass



    def _allowed_threads_effective(self):  # ASSISTANT_ZALO_ADMIN_v8
        """Env allowlist ∪ file managed by Admin API, minus denied (kicked) threads."""
        out = set(getattr(self, "_allowed_threads", set()) or set())
        path = os.getenv("ZALO_ALLOWED_THREADS_FILE", "/opt/data/zalo_allowed_threads.txt")
        try:
            if path and os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    for line in fh:
                        t = line.strip()
                        if not t or t.startswith("#"):
                            continue
                        if "|" in t:
                            t = t.split("|", 1)[0].strip()
                        elif " #" in t:
                            t = t.split(" #", 1)[0].strip()
                        if t:
                            out.add(t)
        except Exception:
            pass
        deny_path = os.getenv("ZALO_DENIED_THREADS_FILE", "/opt/data/zalo_denied_threads.txt")
        try:
            if deny_path and os.path.isfile(deny_path):
                with open(deny_path, encoding="utf-8") as fh:
                    for line in fh:
                        t = line.strip()
                        if not t or t.startswith("#"):
                            continue
                        if "|" in t:
                            t = t.split("|", 1)[0].strip()
                        out.discard(t)
        except Exception:
            pass
        return out

    def _users_strict_mode(self) -> bool:  # ASSISTANT_ZALO_ADMIN_v8
        env = (os.getenv("ZALO_USERS_STRICT") or "").strip().lower()
        if env in {"1", "true", "yes", "on", "strict"}:
            return True
        path = os.getenv("ZALO_USERS_MODE_FILE", "/opt/data/zalo_users_mode.txt")
        try:
            if path and os.path.isfile(path):
                raw = open(path, encoding="utf-8").read().strip().lower()
                return raw in {"strict", "on", "lock"}
        except Exception:
            pass
        return False

    def _allowed_users_effective(self):  # ASSISTANT_ZALO_ADMIN_v8
        """Env ∪ file of approved users. Empty + open mode = everyone."""
        out = set(getattr(self, "_allowed_users", set()) or set())
        out |= self._zalo_admin_uids()
        path = os.getenv("ZALO_ALLOWED_USERS_FILE", "/opt/data/zalo_allowed_users.txt")
        try:
            if path and os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    for line in fh:
                        t = line.strip()
                        if not t or t.startswith("#"):
                            continue
                        if "|" in t:
                            t = t.split("|", 1)[0].strip()
                        if t:
                            out.add(t)
        except Exception:
            pass
        return out

    def _zalo_admin_extract_cmd(self, text: str) -> str:  # ASSISTANT_ZALO_ADMIN_v8
        """Pull '!zalo …' out of '@Bot !zalo who @Friend' (group mention prefix)."""
        import re

        raw = (text or "").strip()
        if not raw:
            return ""
        if raw.lower().startswith("!zalo"):
            return raw
        m = re.search(r"!zalo\b[\s\S]*", raw, flags=re.I)
        return (m.group(0).strip() if m else "")

    def _zalo_admin_mentions(self, m: Dict[str, Any]) -> list:  # ASSISTANT_ZALO_ADMIN_v8
        """Collect @tag uids from inbound payload (list of uids or dicts)."""
        out = []
        for key in ("mentions", "mention"):
            raw = m.get(key)
            if not raw:
                continue
            if isinstance(raw, list):
                for x in raw:
                    if isinstance(x, dict):
                        uid = x.get("uid") or x.get("userId") or x.get("id")
                        if uid is not None:
                            out.append(str(uid))
                    elif x is not None:
                        out.append(str(x))
        # Also dig into raw/attach JSON if bridge nested mentions there
        for key in ("raw", "attach", "params"):
            blob = m.get(key)
            if isinstance(blob, str) and "mention" in blob.lower():
                try:
                    import json as _json
                    data = _json.loads(blob)
                except Exception:
                    data = None
                if isinstance(data, dict):
                    for x in data.get("mentions") or []:
                        if isinstance(x, dict) and x.get("uid") is not None:
                            out.append(str(x.get("uid")))
                        elif x is not None and not isinstance(x, dict):
                            out.append(str(x))
        return out

    def _zalo_admin_reply_uid(self, m: Dict[str, Any]) -> str:  # ASSISTANT_ZALO_ADMIN_v8
        q = m.get("quoted") if isinstance(m.get("quoted"), dict) else None
        if not isinstance(q, dict):
            q = m.get("quote") if isinstance(m.get("quote"), dict) else {}
        if not isinstance(q, dict):
            return ""
        return str(q.get("uidFrom") or q.get("ownerId") or q.get("uid") or "").strip()

    def _zalo_admin_sender_name(self, m: Dict[str, Any]) -> str:  # ASSISTANT_ZALO_ADMIN_v8
        for key in ("sender_name", "senderName", "dName", "displayName", "zaloName"):
            v = m.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        sender = m.get("sender") or m.get("from") or {}
        if isinstance(sender, dict):
            for key in ("displayName", "dName", "zaloName", "name"):
                v = sender.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        return ""

    async def _try_zalo_admin_command(self, m, text, sender_id, thread_id, thread_type):  # ASSISTANT_ZALO_ADMIN_v8
        """Intercept !zalo … before LLM. Always consume — never fall through to LLM."""
        import aiohttp

        raw = self._zalo_admin_extract_cmd(text or "")
        if not raw:
            return False
        admin_url = (
            os.getenv("ZALO_API_URL")
            or os.getenv("ADMIN_API_URL")  # legacy alias
            or "http://zalo-api:8100"
        ).rstrip("/")
        token = (
            os.getenv("ZALO_API_TOKEN")
            or os.getenv("ADMIN_API_TOKEN")  # legacy alias
            or ""
        ).strip()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = {
            "sender_id": str(sender_id or ""),
            "thread_id": str(thread_id or ""),
            "text": raw,
            "chat_type": "group" if thread_type == "group" else "user",
            "mentions": self._zalo_admin_mentions(m),
            "reply_uid": self._zalo_admin_reply_uid(m),
            "bot_id": str(getattr(self, "_own_id", None) or os.getenv("ZALO_OWN_ID") or ""),
            "sender_name": self._zalo_admin_sender_name(m),
        }
        reply = ""
        reply_dm = False
        group_ack = ""
        data = {}
        try:
            timeout = aiohttp.ClientTimeout(total=45)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{admin_url}/v1/zalo/chat", json=body, headers=headers) as resp:
                    status = resp.status
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = {}
            if not isinstance(data, dict):
                data = {}
            if status >= 400 or not data.get("handled"):
                detail = data.get("detail") or data.get("reply") or f"HTTP {status}"
                logger.warning("Zalo API rejected !zalo: %s", detail)
                reply = f"admin: {detail}"
            else:
                reply = (data.get("reply") or "").strip()
                reply_dm = bool(data.get("reply_dm"))
                group_ack = (data.get("group_ack") or "").strip()
        except Exception as e:
            logger.warning("Zalo admin command failed: %s: %s", type(e).__name__, e)
            reply = "zalo-api unavailable"
        # Group !zalo who → DM admin; other cmds stay in-thread unless API asks for DM.
        if reply_dm and sender_id:
            try:
                await self.send(
                    chat_id=str(sender_id),
                    content=reply or "(empty)",
                    metadata={"thread_type": "user", "zalo_admin_reply": True},
                )
                logger.info("Zalo admin: DM → %s (%s)", sender_id, raw.split()[:3])
            except Exception as e:
                logger.warning("Zalo admin DM failed: %s", type(e).__name__)
            if group_ack and thread_type == "group":
                try:
                    await self.send(
                        chat_id=str(thread_id),
                        content=group_ack,
                        metadata={"thread_type": "group", "zalo_admin_reply": True},
                    )
                except Exception as e:
                    logger.warning("Zalo admin group_ack failed: %s", type(e).__name__)
        elif reply:
            try:
                meta = {
                    "thread_type": "group" if thread_type == "group" else "user",
                    "zalo_admin_reply": True,
                }
                await self.send(chat_id=str(thread_id), content=reply, metadata=meta)
            except Exception as e:
                logger.warning("Zalo admin reply failed: %s", type(e).__name__)
        return True





    def _as_gate_store(self):  # ASSISTANT_RATE_LIMIT_v4
        """Valkey gate store (rate + answering). None = fail-open."""
        st = getattr(self, "_as_gate_store_obj", False)
        if st is not False:
            return st
        try:
            import importlib.util
            from pathlib import Path
            p = Path(__file__).resolve().parent / "gate_valkey.py"
            spec = importlib.util.spec_from_file_location("gate_valkey", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._as_gate_store_obj = mod.GateStore.from_env()
        except Exception:
            self._as_gate_store_obj = None
        return self._as_gate_store_obj

    def _zalo_rate_limit_cfg(self):  # ASSISTANT_RATE_LIMIT_v4
        """Return (max_msgs, window_s). max_msgs=0 disables. Default 1 / 10s."""
        import os
        raw = (os.getenv("ZALO_RATE_LIMIT") or "1").strip().lower()
        if raw in {"0", "off", "false", "no"}:
            return 0, 10.0
        try:
            n = int(raw)
        except ValueError:
            n = 1
        try:
            window = float(os.getenv("ZALO_RATE_LIMIT_WINDOW_S") or "10")
        except ValueError:
            window = 10.0
        return max(0, n), max(3.0, window)

    async def _as_schedule_fire_verbatim(
        self,
        m: dict,
        *,
        text: str,
        thread_id: str,
        thread_type: str,
    ) -> bool:
        """If this inject is a verbatim schedule fire, send body and skip Hermes.

        Returns True when handled (caller must return). Process-mode fires return False.
        """
        delivery = str(
            m.get("scheduleDelivery")
            or m.get("schedule_delivery")
            or ""
        ).strip().lower()
        if delivery not in {"verbatim", "send", "deliver"}:
            return False
        body = (text or "").strip()
        if not body:
            logger.warning(
                "Zalo: scheduleFire verbatim empty body thread=%s id=%s",
                thread_id,
                m.get("scheduleId") or m.get("schedule_id"),
            )
            return True
        tt = "group" if str(thread_type or "").lower() in {"group", "g"} else "user"
        logger.info(
            "Zalo: scheduleFire verbatim send thread=%s id=%s chars=%s",
            thread_id,
            m.get("scheduleId") or m.get("schedule_id"),
            len(body),
        )
        await self.send(
            chat_id=str(thread_id),
            content=body,
            metadata={
                "thread_type": tt,
                "as_skip_dest": True,
                "as_skip_autosend": True,
                "as_skip_inflight": True,
                "as_skip_quote": True,
                "skip_outbound_filter": True,
                "schedule_fire": True,
                "schedule_delivery": "verbatim",
            },
        )
        return True

    async def _as_gate_announce(self, thread_id, thread_type, content: str) -> None:  # ASSISTANT_RATE_LIMIT_v4
        """Send a gate line only to this thread. Never quote. Never retarget via global dest."""
        tid = str(thread_id or "").strip()
        if not tid:
            return
        pq = getattr(self, "_pending_reply_quote", None)
        if isinstance(pq, dict):
            pq.pop(tid, None)
            pq.pop(str(tid), None)
        tt = "group" if str(thread_type or "").lower() in {"group", "g"} else "user"
        await self.send(
            chat_id=tid,
            content=content,
            metadata={
                "thread_type": tt,
                "as_skip_dest": True,
                "as_skip_autosend": True,
                "as_skip_inflight": True,
                "as_skip_quote": True,
                "skip_outbound_filter": True,
            },
        )

    def _as_ux_line(
        self,
        env_name: str,
        json_path: tuple,
        default: str,
        *,
        user_text: str = "",
    ) -> str:
        """Env override, then messages/ux.json (locale map or string), then default.

        Locale maps use the user's message script (see ``ux_copy.reply_lang``).
        Operators add languages in ux.json — do not hardcode user copy in Python.
        """
        raw = (os.getenv(env_name) or "").strip()
        if raw:
            return raw
        try:
            from .ux_copy import pick_localized, reply_lang
        except ImportError:
            from ux_copy import pick_localized, reply_lang  # type: ignore
        cache = getattr(self, "_as_ux_cache", None)
        if cache is False:
            return default
        if cache is None:
            path = (
                os.getenv("ZALO_UX_PATH")
                or os.getenv("ASSISTANT_UX_PATH")
                or "/opt/data/messages/ux.json"
            ).strip()
            try:
                cache = json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception:
                cache = False
            self._as_ux_cache = cache
        if not isinstance(cache, dict):
            return default
        cur: Any = cache
        for key in json_path:
            if not isinstance(cur, dict) or key not in cur:
                return default
            cur = cur[key]
        if isinstance(cur, dict):
            return pick_localized(cur, reply_lang(user_text), default)
        s = str(cur or "").strip()
        return s if s else default

    def _zalo_rate_check(self, sender_id, thread_id) -> tuple:
        """(over_limit, should_announce). Never sends. Fail-open = not over."""
        n, window = self._zalo_rate_limit_cfg()
        if n <= 0:
            return False, False
        sid = str(sender_id or "")
        tid = str(thread_id or "")
        if not sid or not tid:
            return False, False
        store = self._as_gate_store()
        if store is None:
            return False, False
        try:
            over, notify = store.rate_take(sid, tid, n, window)
        except Exception:
            return False, False
        return bool(over), bool(notify)

    async def _zalo_rate_limit_drop(self, sender_id, thread_id, thread_type) -> bool:  # ASSISTANT_RATE_LIMIT_v4
        """True = drop inbound (too many messages). Announce at most once per window."""
        over, notify = self._zalo_rate_check(sender_id, thread_id)
        if not over:
            return False
        logger.info(
            "Zalo: rate-limit drop sender=%s thread=%s type=%s via valkey",
            sender_id, thread_id, thread_type,
        )
        if notify:
            msg = self._as_ux_line(
                "ZALO_RATE_LIMIT_MSG",
                ("queue", "rate_limited"),
                "Bạn gửi hơi nhanh — tin này đã vào hàng chờ, mình trả lời lần lượt.",
            )
            try:
                await self._as_gate_announce(thread_id, thread_type, msg)
            except Exception as e:
                logger.warning("Zalo: rate-limit announce failed: %s", type(e).__name__)
        return True


    def _as_answering_ttl_s(self) -> int:
        """How long the per-thread answering lock lasts (match queue turn wait)."""
        # Keep answering lock alive for the full turn wait (default 15 minutes).
        return int(self._as_queue_turn_timeout_s())

    def _as_already_answering_max(self) -> int:  # ASSISTANT_INFLIGHT_v6
        import os
        raw = (os.getenv("HERMES_MAX_ANSWERING") or os.getenv("HERMES_MAX_INFLIGHT") or "3").strip().lower()
        if raw in {"0", "off", "false", "no"}:
            return 0
        try:
            return max(0, int(raw))
        except ValueError:
            return 3

    def _as_inflight_try(self, thread_id) -> bool:  # ASSISTANT_INFLIGHT_v6
        """True = this chat has a free answering slot. False = already answering (max)."""
        cap = self._as_already_answering_max()
        if cap <= 0:
            return True
        store = self._as_gate_store() if hasattr(self, "_as_gate_store") else None
        if store is None:
            return True
        try:
            return bool(
                store.answering_try(
                    str(thread_id or ""), cap, self._as_answering_ttl_s()
                )
            )
        except Exception:
            return True

    def _as_inflight_done(self, thread_id, metadata=None) -> None:  # ASSISTANT_INFLIGHT_v6
        meta = metadata if isinstance(metadata, dict) else {}
        if meta.get("as_skip_inflight"):
            return
        if self._as_already_answering_max() <= 0:
            return
        store = self._as_gate_store() if hasattr(self, "_as_gate_store") else None
        if store is None:
            return
        try:
            store.answering_done(str(thread_id or ""))
        except Exception:
            pass

    async def _as_inflight_drop(self, sender_id, thread_id, thread_type) -> bool:  # ASSISTANT_INFLIGHT_v6
        """True = this chat already answering (at max). Other chats are never blocked."""
        if self._as_inflight_try(thread_id):
            return False
        logger.info("Zalo: already answering wait thread=%s type=%s via valkey", thread_id, thread_type)
        logger.info(f"[zalo] already answering wait thread={thread_id}")
        try:
            announce = getattr(self, "_as_gate_announce", None)
            msg = self._as_ux_line(
                "ZALO_ALREADY_ANSWERING_MSG",
                ("queue", "already_answering"),
                "Bot đang trả lời tin này. Đợi xong rồi gửi tiếp nhé (tối đa khoảng 15 phút).",
            )
            if callable(announce):
                await announce(thread_id, thread_type, msg)
            else:
                await self.send(
                    chat_id=str(thread_id),
                    content=msg,
                    metadata={
                        "thread_type": "group" if thread_type == "group" else "user",
                        "as_skip_inflight": True,
                        "as_skip_dest": True,
                        "as_skip_autosend": True,
                        "as_skip_quote": True,
                    },
                )
        except Exception:
            pass
        return True


    def _as_env_float(self, name: str, default: float, lo: float, hi: float) -> float:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return default
        try:
            val = float(raw)
        except ValueError:
            return default
        return max(lo, min(hi, val))

    def _as_compound_begin(self, thread_id: str) -> None:
        tid = str(thread_id or "")
        if not tid:
            return
        self._as_hold_inflight.add(tid)
        ev = self._as_part_delivered.get(tid)
        if ev is None:
            self._as_part_delivered[tid] = asyncio.Event()
        else:
            ev.clear()
        seq = getattr(self, "_as_compound_seq_t0", None)
        if not isinstance(seq, dict):
            self._as_compound_seq_t0 = {}
            seq = self._as_compound_seq_t0
        if tid not in seq:
            seq[tid] = __import__("time").time()

    def _as_compound_end(self, thread_id: str) -> None:
        tid = str(thread_id or "")
        self._as_hold_inflight.discard(tid)
        self._as_part_delivered.pop(tid, None)
        self._as_inflight_done(tid)

    def _as_compound_seq_done(self, thread_id: str) -> None:
        tid = str(thread_id or "")
        seq = getattr(self, "_as_compound_seq_t0", None)
        if isinstance(seq, dict):
            seq.pop(tid, None)

    async def _as_schedule_lifecycle(
        self,
        *,
        text: str,
        current: str,
        thread_id: str,
        thread_type: str,
        plan: dict,
    ) -> bool:
        action = str(plan.get("skill_action") or "").strip().lower()
        try:
            from .schedule_client import (
                match_schedules_by_selector,
                resolve_schedule_timing,
                schedule_enabled,
                schedules_for_thread,
                upsert_schedule_from_row,
            )
        except ImportError:
            from schedule_client import (  # type: ignore
                match_schedules_by_selector,
                resolve_schedule_timing,
                schedule_enabled,
                schedules_for_thread,
                upsert_schedule_from_row,
            )

        async def _say(kind: str, fallback: str) -> None:
            try:
                msg = self._as_ux_line(
                    "ZALO_SCHEDULE_FAILED_MSG" if kind == "failed" else "ZALO_SCHEDULE_SAVED_MSG",
                    ("schedule", kind),
                    fallback,
                    user_text=text,
                )
                await self._as_gate_announce(thread_id, thread_type, msg)
            except Exception:
                pass

        if not schedule_enabled():
            await _say("failed", "Chưa bật schedule-worker nên chưa đổi được lịch.")
            return True
        selector = plan.get("schedule_selector") if isinstance(plan.get("schedule_selector"), dict) else {}
        rows = schedules_for_thread(thread_id)
        hits = match_schedules_by_selector(rows, selector)
        resolution = str(plan.get("schedule_resolution") or "").strip().lower()
        if resolution == "ambiguous" or len(hits) > 1:
            await _say(
                "failed",
                "Có nhiều lịch khớp. Nêu rõ nội dung hoặc giờ chạy của lịch cần đổi.",
            )
            return True
        if not hits:
            await _say("failed", "Không tìm thấy lịch khớp. Dùng xem lịch rồi nêu rõ lịch cần đổi.")
            return True
        row = hits[0]
        sid = str(row.get("id") or "").strip()
        if action == "pause":
            data = upsert_schedule_from_row(row, enabled=False)
            await _say("saved", f"Đã tạm dừng lịch{(' id=' + sid) if sid else ''}.")
            return bool(data) or True
        if action == "resume":
            data = upsert_schedule_from_row(row, enabled=True)
            await _say("saved", f"Đã tiếp tục lịch{(' id=' + sid) if sid else ''}.")
            return bool(data) or True
        if action in {"run_now", "run"}:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            data = upsert_schedule_from_row(row, enabled=True, next_run_at=now)
            await _say("saved", f"Đã xếp chạy ngay{(' id=' + sid) if sid else ''}.")
            return bool(data) or True
        if action == "update":
            timing = resolve_schedule_timing(
                plan,
                current,
                tz=str(plan.get("timezone") or "Asia/Ho_Chi_Minh"),
            )
            nxt = str(timing.get("next_run_at") or "")
            cron = str(timing.get("cron_expr") or "")
            if not nxt and not cron:
                await _say("failed", "Chưa rõ giờ chạy mới. Gửi lại thời điểm cụ thể.")
                return True
            data = upsert_schedule_from_row(
                row,
                enabled=True,
                next_run_at=nxt or None,
                cron_expr=cron or None,
                cadence=str(timing.get("cadence") or row.get("cadence") or ""),
            )
            await _say("saved", f"Đã cập nhật lịch{(' id=' + sid) if sid else ''}.")
            return bool(data) or True
        await _say("failed", "Chưa hỗ trợ thao tác lịch này.")
        return True

    async def _as_run_host_media_shortcut(
        self,
        *,
        user_text: str,
        thread_id: str,
        thread_type: str,
        bare_text: str | None = None,
        plan: dict | None = None,
        media_urls: list | None = None,
        has_image_attachment: bool = False,
    ) -> bool:
        """Run host-owned media shortcuts. True when the turn was consumed."""
        shortcut_user_text = (user_text or "").strip()
        bare = (bare_text if bare_text is not None else shortcut_user_text).strip()
        urls = list(media_urls or [])
        if (
            not shortcut_user_text
            or urls
            or has_image_attachment
            or "[Attachment text —" in bare
            or "[Attached file:" in bare
            or "[Attached image:" in bare
        ):
            return False
        try:
            from .classify_client import (
                classify_text_async,
                plan_allows_office_shortcut,
                plan_allows_poster_shortcut,
                plan_allows_scene_image,
                plan_allows_search_then_info_card,
                plan_allows_search_then_office,
                plan_allows_search_then_live_scene,
                plan_is_image_analyze_chat,
                plan_is_media_policy_refuse,
                plan_media_shortcut_gate,
                plan_output_type,
                plan_search_then_office_output,
                plan_skips_media_shortcut,
                apply_image_analyze_plan_coercion,
            )
            from .media_shortcuts import (
                media_fail_line,
                run_office_create,
                run_scene_image,
                run_search_then_info_card,
                run_search_then_office,
                run_search_then_live_scene,
                run_text_poster,
                run_video_policy_refuse,
                shortcut_ok,
                shortcut_was_consumed,
            )
        except ImportError:
            from classify_client import (  # type: ignore
                classify_text_async,
                plan_allows_office_shortcut,
                plan_allows_poster_shortcut,
                plan_allows_scene_image,
                plan_allows_search_then_info_card,
                plan_allows_search_then_office,
                plan_allows_search_then_live_scene,
                plan_is_image_analyze_chat,
                plan_is_media_policy_refuse,
                plan_media_shortcut_gate,
                plan_output_type,
                plan_search_then_office_output,
                plan_skips_media_shortcut,
                apply_image_analyze_plan_coercion,
            )
            from media_shortcuts import (  # type: ignore
                media_fail_line,
                run_office_create,
                run_scene_image,
                run_search_then_info_card,
                run_search_then_office,
                run_search_then_live_scene,
                run_text_poster,
                run_video_policy_refuse,
                shortcut_ok,
                shortcut_was_consumed,
            )
        shortcut = None
        shortcut_gate = ""
        try:
            attach_hint = "image" if has_image_attachment else "none"
            # Never block the asyncio loop on Omni classify (watchdog exit 75).
            early_plan = (
                plan
                if isinstance(plan, dict)
                else await classify_text_async(
                    shortcut_user_text, attachments=attach_hint
                )
            )
            if has_image_attachment and plan_is_image_analyze_chat(early_plan, has_image=True):
                return False
            if has_image_attachment:
                early_plan = apply_image_analyze_plan_coercion(early_plan)
            shortcut_gate = plan_media_shortcut_gate(early_plan)
            inner = ""
            ins = early_plan.get("instructions") or []
            if isinstance(ins, list) and ins:
                inner = str(ins[0] or "").strip()
            work = inner or shortcut_user_text
            if plan_is_media_policy_refuse(early_plan):
                shortcut = await asyncio.to_thread(
                    run_video_policy_refuse,
                    shortcut_user_text,
                    early_plan,
                    str(thread_id),
                    str(thread_type),
                    classified=True,
                )
                if shortcut_ok(shortcut):
                    self._as_flow("video_policy_refuse", thread_id=thread_id)
            elif plan_allows_office_shortcut(early_plan) and not plan_skips_media_shortcut(early_plan):
                shortcut = await asyncio.to_thread(
                    run_office_create,
                    work,
                    str(thread_id),
                    str(thread_type),
                    classified=True,
                    output_type=plan_output_type(early_plan),
                )
                if shortcut_ok(shortcut):
                    self._as_flow("office_shortcut", thread_id=thread_id, file=shortcut.get("file"))
            elif plan_allows_search_then_office(early_plan):
                shortcut = await asyncio.to_thread(
                    run_search_then_office,
                    shortcut_user_text,
                    early_plan,
                    str(thread_id),
                    str(thread_type),
                    classified=True,
                    output_type=plan_search_then_office_output(early_plan)
                    or plan_output_type(early_plan)
                    or "pdf",
                )
                if shortcut_ok(shortcut):
                    self._as_flow(
                        "search_office_shortcut",
                        thread_id=thread_id,
                        file=shortcut.get("file"),
                    )
            elif plan_allows_search_then_live_scene(early_plan):
                try:
                    self._as_autosend_remember_turn(
                        str(thread_id),
                        "group" if str(thread_type).lower() in {"group", "g"} else "user",
                    )
                except Exception:
                    pass
                shortcut = await asyncio.to_thread(
                    run_search_then_live_scene,
                    shortcut_user_text,
                    early_plan,
                    str(thread_id),
                    str(thread_type),
                    classified=True,
                )
                if shortcut_ok(shortcut):
                    self._as_flow(
                        "search_live_scene_shortcut",
                        thread_id=thread_id,
                        file=shortcut.get("file"),
                    )
            elif plan_allows_search_then_info_card(early_plan):
                try:
                    self._as_autosend_remember_turn(
                        str(thread_id),
                        "group" if str(thread_type).lower() in {"group", "g"} else "user",
                    )
                except Exception:
                    pass
                shortcut = await asyncio.to_thread(
                    run_search_then_info_card,
                    shortcut_user_text,
                    early_plan,
                    str(thread_id),
                    str(thread_type),
                    classified=True,
                )
                if shortcut_ok(shortcut):
                    self._as_flow(
                        "search_info_card_shortcut",
                        thread_id=thread_id,
                        file=shortcut.get("file"),
                    )
            elif plan_allows_scene_image(early_plan):
                try:
                    self._as_autosend_remember_turn(
                        str(thread_id),
                        "group" if str(thread_type).lower() in {"group", "g"} else "user",
                    )
                except Exception:
                    pass
                shortcut = await asyncio.to_thread(
                    run_scene_image,
                    shortcut_user_text,
                    early_plan,
                    str(thread_id),
                    str(thread_type),
                    classified=True,
                )
                if shortcut_ok(shortcut):
                    self._as_flow(
                        "scene_image_shortcut",
                        thread_id=thread_id,
                        file=shortcut.get("file"),
                    )
            elif plan_allows_poster_shortcut(early_plan):
                shortcut = await asyncio.to_thread(
                    run_text_poster,
                    work,
                    str(thread_id),
                    str(thread_type),
                    classified=True,
                    poster_n=early_plan.get("poster_n"),
                    poster_phrase=str(early_plan.get("poster_phrase") or work),
                    poster_bw=early_plan.get("poster_bw"),
                )
                if shortcut_ok(shortcut):
                    self._as_flow("poster_shortcut", thread_id=thread_id, file=shortcut.get("file"))
        except Exception as e:
            logger.warning("Zalo: media shortcut error: %s", type(e).__name__)
            shortcut = None
        if shortcut_ok(shortcut):
            try:
                self._as_last_user_text = getattr(self, "_as_last_user_text", {}) or {}
                self._as_last_user_text[str(thread_id)] = bare
            except Exception:
                pass
            try:
                self._as_autosend_remember_turn(
                    str(thread_id),
                    "group" if str(thread_type).lower() in {"group", "g"} else "user",
                )
            except Exception:
                pass
            refuse_text = ""
            try:
                if str((shortcut or {}).get("kind") or "") == "text_refuse":
                    refuse_text = str((shortcut or {}).get("text") or "").strip()
            except Exception:
                refuse_text = ""
            if refuse_text:
                try:
                    await self._as_gate_announce(
                        str(thread_id),
                        str(thread_type),
                        refuse_text,
                    )
                except Exception as e:
                    logger.warning(
                        "Zalo: video-policy refuse send failed: %s",
                        type(e).__name__,
                    )
                try:
                    from .session_memory import append_turn
                except ImportError:
                    from session_memory import append_turn  # type: ignore
                try:
                    append_turn(str(thread_id), str(thread_type), bare, refuse_text)
                except Exception:
                    pass
                try:
                    self._as_inflight_done(str(thread_id), {})
                except Exception:
                    pass
                try:
                    self._as_queue_kick(str(thread_id))
                except Exception:
                    pass
                return True
            image_delivered = False
            try:
                img_path = str((shortcut or {}).get("file") or (shortcut or {}).get("path") or "")
                if img_path:
                    p = Path(img_path)
                    if p.is_file() and p.suffix.lower() in {
                        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
                    }:
                        meta = {"as_skip_autosend": True, "as_claimed": True}
                        res = await self.send_image_file(
                            str(thread_id),
                            img_path,
                            caption="",
                            metadata=meta,
                        )
                        image_delivered = bool(
                            res and getattr(res, "success", None) is not False
                        )
            except Exception as e:
                logger.warning(
                    "Zalo: shortcut direct image send failed: %s",
                    type(e).__name__,
                )
            if not image_delivered:
                try:
                    await self._as_autosend_late_files(
                        str(thread_id),
                        "group" if str(thread_type).lower() in {"group", "g"} else "user",
                    )
                except Exception:
                    pass
            try:
                from .session_memory import append_turn
            except ImportError:
                from session_memory import append_turn  # type: ignore
            try:
                append_turn(str(thread_id), str(thread_type), bare, "Đã gửi hình.")
            except Exception:
                pass
            try:
                self._as_inflight_done(str(thread_id), {})
            except Exception:
                pass
            try:
                self._as_queue_kick(str(thread_id))
            except Exception:
                pass
            return True
        if shortcut_gate or shortcut_was_consumed(shortcut):
            fail_line = media_fail_line()
            if str(shortcut_gate) == "refuse":
                fail_line = (
                    "This stack does not download or transcribe video/music links. "
                    "Use the native app, or ask for a still image / office file instead."
                )
            try:
                await self._as_gate_announce(
                    str(thread_id),
                    str(thread_type),
                    fail_line,
                )
            except Exception as e:
                logger.warning(
                    "Zalo: media shortcut fail-line send failed: %s",
                    type(e).__name__,
                )
            try:
                self._as_last_user_text = getattr(self, "_as_last_user_text", {}) or {}
                self._as_last_user_text[str(thread_id)] = bare
            except Exception:
                pass
            try:
                from .session_memory import append_turn
            except ImportError:
                from session_memory import append_turn  # type: ignore
            try:
                append_turn(str(thread_id), str(thread_type), bare, fail_line)
            except Exception:
                pass
            try:
                self._as_inflight_done(str(thread_id), {})
            except Exception:
                pass
            try:
                self._as_queue_kick(str(thread_id))
            except Exception:
                pass
            return True
        return False

    def _as_has_image_attachment(
        self,
        media_urls: list | None,
        *,
        media_types: list | None = None,
        message_type=None,
        attach_is_image: bool = False,
    ) -> bool:
        if attach_is_image:
            return True
        urls = [u for u in (media_urls or []) if str(u or "").strip()]
        if not urls:
            return False
        if message_type == MessageType.PHOTO:
            return True
        for mt in media_types or []:
            if str(mt or "").lower().startswith("image/"):
                return True
        for u in urls:
            low = str(u or "").lower()
            if low.endswith(
                (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
            ):
                return True
        return False

    async def _as_ocr_vision_describe(
        self, local_path: str, *, prompt: str, file_name: str = ""
    ) -> str:
        """Scene describe via router-worker combo vision-ocr."""
        import asyncio

        try:
            from .vision_ocr import resolve_media_path, vision_describe
            from .attachment import vision_image_b64_for_describe
        except ImportError:
            from vision_ocr import resolve_media_path, vision_describe  # type: ignore
            from attachment import vision_image_b64_for_describe  # type: ignore

        src = resolve_media_path(str(local_path or ""))
        if src is None:
            self._as_flow(
                "attach_vision_miss",
                path=str(local_path or "")[:120],
            )
            return ""
        name = file_name or src.name

        def _read() -> dict:
            b64 = vision_image_b64_for_describe(str(src))
            if b64:
                return vision_describe(image_b64=b64, prompt=prompt)
            return vision_describe(path=str(src), prompt=prompt)

        out = await asyncio.to_thread(_read)
        text = (out.get("text") or "").strip()
        if out.get("ok") is True and text:
            self._as_flow("attach_vision_read", file=name, chars=len(text))
            return text
        self._as_flow(
            "attach_vision_empty",
            file=name,
            error=out.get("error") or "empty",
            status=out.get("status"),
            model=out.get("model"),
            detail=(out.get("detail") or "")[:120],
            preview=text[:120],
        )
        return ""

    async def _as_try_image_analyze_vision_reply(
        self,
        *,
        text: str,
        thread_id: str,
        thread_type: str,
        media_urls: list | None,
        has_image_attachment: bool = False,
        plan: dict | None = None,
    ) -> bool:
        """Image-analyze chat: host reply via combo vision-ocr (bypass Hermes chat)."""
        if not has_image_attachment:
            return False
        urls = [u for u in (media_urls or []) if str(u or "").strip()]
        if not urls:
            return False
        try:
            from .classify_client import (
                classify_text_async,
                coerce_image_analyze_plan,
                plan_is_image_analyze_chat,
                strip_prior_for_classify,
            )
        except ImportError:
            from classify_client import (  # type: ignore
                classify_text_async,
                coerce_image_analyze_plan,
                plan_is_image_analyze_chat,
                strip_prior_for_classify,
            )
        current = strip_prior_for_classify(text) or str(text or "").strip()
        if not isinstance(plan, dict):
            plan = await classify_text_async(
                current,
                thread=("group" if str(thread_type or "").lower() == "group" else "dm"),
                attachments="image",
            )
        coerced = coerce_image_analyze_plan(plan, has_image=True, user_text=current)
        if coerced is None:
            return False
        plan = coerced
        if not plan_is_image_analyze_chat(plan, has_image=True):
            return False
        prompt = image_analyze_vision_prompt(current)
        raw = await self._as_ocr_vision_describe(str(urls[0]), prompt=prompt)
        reply = image_analyze_vision_body(raw, prompt=prompt)
        if not reply:
            raw2 = await self._as_ocr_vision_describe(
                str(urls[0]), prompt=IMAGE_ANALYZE_VISION_PROMPT_RETRY
            )
            reply = image_analyze_vision_body(raw2, prompt=IMAGE_ANALYZE_VISION_PROMPT_RETRY)
            if reply:
                raw = raw2
        if not reply:
            raw3 = await self._as_ocr_vision_describe(
                str(urls[0]), prompt=IMAGE_ANALYZE_VISION_PROMPT_SCENE
            )
            reply = image_analyze_vision_body(raw3, prompt=IMAGE_ANALYZE_VISION_PROMPT_SCENE)
            if reply:
                raw = raw3
        meta = {
            "thread_type": "group" if thread_type == "group" else "user",
            "as_skip_autosend": True,
            "as_skip_dest": True,
            "skip_outbound_filter": True,
        }
        if not reply:
            self._as_flow(
                "attach_image_vision_fail",
                thread_id=thread_id,
                chars=len(raw or ""),
                preview=(raw or "")[:120],
                noise=bool(raw and not reply),
            )
            try:
                await self.send(
                    chat_id=str(thread_id),
                    content="Không mô tả được ảnh — gửi lại giúp mình.",
                    metadata={**meta, "as_skip_inflight": True},
                )
            except Exception:
                logger.warning("[zalo] image vision fail ack failed thread=%s", thread_id)
            try:
                self._as_inflight_done(str(thread_id), {})
            except Exception:
                pass
            try:
                self._as_queue_kick(str(thread_id))
            except Exception:
                pass
            return True
        self._as_flow(
            "attach_image_vision_reply",
            thread_id=thread_id,
            chars=len(reply),
        )
        try:
            await self.send(
                chat_id=str(thread_id),
                content=reply,
                metadata=meta,
            )
        except Exception:
            logger.warning("[zalo] image vision reply failed thread=%s", thread_id)
            return False
        try:
            self._as_inflight_done(str(thread_id), {})
        except Exception:
            pass
        try:
            self._as_queue_kick(str(thread_id))
        except Exception:
            pass
        return True

    async def _as_try_workflow_submit(
        self,
        *,
        text: str,
        thread_id: str,
        thread_type: str,
        sender_id: str,
        sender_name: str,
        chat_type: str,
        plan: dict | None = None,
        schedule_fire: bool = False,
        _schedule_fanout_child: bool = False,
        received_at=None,
        has_image_attachment: bool = False,
    ) -> bool:
        try:
            from .workflow_client import create_schedule, create_workflow, workflow_enabled
            from .schedule_client import create_schedule as go_create_schedule
            from .schedule_client import (
                fire_text_from_plan,
                schedule_delivery_mode,
                schedule_enabled,
            )
            from .classify_client import (
                classify_text_async,
                plan_compound_sequential,
                plan_is_async,
                plan_is_host_direct_reply,
                plan_is_immediate_deliver,
                plan_is_image_analyze_chat,
                plan_is_search_then_image_turn,
                plan_media_shortcut_gate,
                apply_image_analyze_plan_coercion,
                plan_output_type,
                _instruction_is_office_file_body,
            )
            from .classify_client import strip_prior_for_classify
            from .knowledge_cite import plan_is_knowledge
        except ImportError:
            from workflow_client import create_schedule, create_workflow, workflow_enabled  # type: ignore
            from schedule_client import create_schedule as go_create_schedule  # type: ignore
            from schedule_client import (  # type: ignore
                fire_text_from_plan,
                schedule_delivery_mode,
                schedule_enabled,
            )
            from classify_client import (  # type: ignore
                classify_text_async,
                plan_compound_sequential,
                plan_is_async,
                plan_is_host_direct_reply,
                plan_is_immediate_deliver,
                plan_is_image_analyze_chat,
                plan_is_search_then_image_turn,
                plan_media_shortcut_gate,
                apply_image_analyze_plan_coercion,
                plan_output_type,
                _instruction_is_office_file_body,
            )
            from classify_client import strip_prior_for_classify  # type: ignore
            from knowledge_cite import plan_is_knowledge  # type: ignore
        if received_at is None:
            received_at = datetime.now(timezone.utc)
        current = strip_prior_for_classify(text) or str(text or "").strip()
        attach_hint = "image" if has_image_attachment else "none"
        if not isinstance(plan, dict):
            plan = await classify_text_async(
                text or current,
                thread=("group" if str(thread_type or "").lower() == "group" else "dm"),
                attachments=attach_hint,
            )
        if has_image_attachment and plan_is_image_analyze_chat(plan, has_image=True):
            plan = apply_image_analyze_plan_coercion(plan)
        if plan.get("ok") is False:
            # Omni/classify outages must not dead-end chat. Fall through to Hermes.
            logger.info(
                "[zalo] classify failed error=%s — fall through to Hermes",
                plan.get("error"),
            )
            return False
        if plan_is_host_direct_reply(plan) and not schedule_fire:
            # Classify refuse (secret/env soft asks, etc.): never stage knowledge-learn.
            mark = getattr(self, "_as_learn_skip_mark", None)
            if callable(mark):
                mark(thread_id, sender_id)
            body = str(plan.get("message") or "").strip()
            if not body:
                body = "\n".join(
                    str(x).strip()
                    for x in (plan.get("instructions") or [])
                    if str(x).strip()
                )
            try:
                await self.send(
                    chat_id=str(thread_id),
                    content=body,
                    metadata={
                        "thread_type": "group" if thread_type == "group" else "user",
                        "skip_outbound_filter": True,
                    },
                )
            except Exception:
                logger.warning("[zalo] host direct reply failed thread=%s", thread_id)
            return True
        if plan_is_immediate_deliver(plan) and not schedule_fire:
            try:
                from .channels_client import apply_schedule_delivery_target
            except ImportError:
                from channels_client import apply_schedule_delivery_target  # type: ignore
            dest_origin = {
                "platform": "zalo",
                "chat_id": thread_id,
                "thread_id": thread_id,
                "user_id": sender_id,
                "chat_name": sender_name,
            }
            dest_ctx = {
                "thread_id": thread_id,
                "thread_type": thread_type,
                "chat_type": chat_type,
                "sender_id": sender_id,
                "sender_name": sender_name,
            }
            dest_origin, dest_ctx, target_note = apply_schedule_delivery_target(
                text=current,
                plan=plan,
                origin=dest_origin,
                context=dest_ctx,
                current_thread_type=thread_type,
            )
            if target_note and str(target_note).startswith("group_not_found:"):
                ref = target_note.split(":", 1)[-1]
                try:
                    msg = self._as_ux_line(
                        "ZALO_SCHEDULE_GROUP_NOT_FOUND_MSG",
                        ("schedule", "group_not_found"),
                        (
                            f"Chưa biết nhóm '{ref}'. Vào nhóm đó gửi !zalo allow / "
                            f"!zalo label, hoặc !zalo refresh rồi gửi lại."
                        ),
                        user_text=text,
                    )
                    await self._as_gate_announce(thread_id, thread_type, msg)
                except Exception:
                    pass
                return True
            body = fire_text_from_plan(plan, current)
            dest_id = str(dest_origin.get("thread_id") or thread_id)
            dest_type = str(dest_ctx.get("thread_type") or thread_type)
            try:
                await self.send(
                    chat_id=dest_id,
                    content=body,
                    metadata={
                        "thread_type": "group" if dest_type == "group" else "user",
                        "skip_outbound_filter": True,
                    },
                )
            except Exception:
                logger.warning("[zalo] immediate deliver failed dest=%s", dest_id)
                return True
            dest_name = str(dest_origin.get("target_name") or dest_origin.get("chat_name") or "").strip()
            if dest_id != str(thread_id) and dest_name:
                try:
                    ack = self._as_ux_line(
                        "ZALO_DELIVERED_MSG",
                        ("schedule", "saved"),
                        f"Đã gửi → nhóm {dest_name}.",
                        user_text=text,
                    )
                    await self._as_gate_announce(thread_id, thread_type, ack)
                except Exception:
                    pass
            return True
        if plan_is_knowledge(plan):
            await self._as_knowledge_cite_reply(
                {"text": text},
                sender_id,
                thread_id,
                thread_type,
                plan=plan,
            )
            return True
        # A process schedule fires its inner work with the timing wrapper already
        # removed. Let that classified media/search plan use the same host-owned
        # shortcut as an immediate request; otherwise scheduled images fall
        # through to a text-only Hermes job.
        if plan_media_shortcut_gate(plan) or plan_is_search_then_image_turn(plan):
            return await self._as_run_host_media_shortcut(
                user_text=current,
                thread_id=thread_id,
                thread_type=thread_type,
                bare_text=current,
                plan=plan,
            )
        origin = {
            "platform": "zalo",
            "chat_id": thread_id,
            "thread_id": thread_id,
            "user_id": sender_id,
            "chat_name": sender_name,
        }
        context = {
            "thread_id": thread_id,
            "thread_type": thread_type,
            "chat_type": chat_type,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "execute": "hermes",
            "plan": plan,
        }
        if plan.get("task_hint") == "schedule" and not schedule_fire:
            skill_action = str(plan.get("skill_action") or "").strip().lower()
            task_type = str(plan.get("task_type") or "").strip().lower()
            if skill_action in {"list", "inspect", "show", "status"} or task_type == "list_schedule":
                try:
                    from .schedule_client import (
                        format_schedule_list_lines,
                        schedule_enabled,
                        schedules_for_thread,
                    )
                    from .channels_client import extract_target_group_ref, resolve_channel
                except ImportError:
                    from schedule_client import (  # type: ignore
                        format_schedule_list_lines,
                        schedule_enabled,
                        schedules_for_thread,
                    )
                    from channels_client import extract_target_group_ref, resolve_channel  # type: ignore
                target_tid = thread_id
                target_label = ""
                ref = extract_target_group_ref(current, plan)
                if ref:
                    hit = resolve_channel(ref)
                    gid = str((hit or {}).get("external_id") or "").strip()
                    if not gid:
                        try:
                            msg = self._as_ux_line(
                                "ZALO_SCHEDULE_GROUP_NOT_FOUND_MSG",
                                ("schedule", "group_not_found"),
                                (
                                    f"Chưa biết nhóm '{ref}'. Vào nhóm đó gửi !zalo allow / "
                                    f"!zalo label, hoặc !zalo refresh rồi xem lịch lại."
                                ),
                                user_text=text,
                            )
                            await self._as_gate_announce(thread_id, thread_type, msg)
                        except Exception:
                            pass
                        return True
                    target_tid = gid
                    target_label = str((hit or {}).get("name") or ref).strip()
                if not schedule_enabled():
                    try:
                        msg = self._as_ux_line(
                            "ZALO_SCHEDULE_LIST_UNAVAILABLE_MSG",
                            ("schedule", "list_unavailable"),
                            "Chưa bật schedule-worker nên chưa xem được lịch.",
                            user_text=text,
                        )
                        await self._as_gate_announce(thread_id, thread_type, msg)
                    except Exception:
                        pass
                    return True
                rows = schedules_for_thread(target_tid)
                base = format_schedule_list_lines(rows)
                if target_label and rows:
                    base = f"{base}\n(→ nhóm {target_label})"
                try:
                    msg = self._as_ux_line(
                        "ZALO_SCHEDULE_LIST_MSG",
                        ("schedule", "list"),
                        base,
                        user_text=text,
                    )
                    await self._as_gate_announce(thread_id, thread_type, msg)
                except Exception:
                    pass
                return True
            if skill_action == "delete" or task_type == "delete_schedule":
                try:
                    from .schedule_client import (
                        delete_schedules_for_thread,
                        schedule_enabled,
                    )
                    from .channels_client import extract_target_group_ref, resolve_channel
                except ImportError:
                    from schedule_client import (  # type: ignore
                        delete_schedules_for_thread,
                        schedule_enabled,
                    )
                    from channels_client import extract_target_group_ref, resolve_channel  # type: ignore
                target_tid = thread_id
                target_label = ""
                ref = extract_target_group_ref(current, plan)
                if ref:
                    hit = resolve_channel(ref)
                    gid = str((hit or {}).get("external_id") or "").strip()
                    if not gid:
                        try:
                            msg = self._as_ux_line(
                                "ZALO_SCHEDULE_GROUP_NOT_FOUND_MSG",
                                ("schedule", "group_not_found"),
                                (
                                    f"Chưa biết nhóm '{ref}'. Vào nhóm đó gửi !zalo allow / "
                                    f"!zalo label, hoặc !zalo refresh rồi xóa lịch lại."
                                ),
                                user_text=text,
                            )
                            await self._as_gate_announce(thread_id, thread_type, msg)
                        except Exception:
                            pass
                        return True
                    target_tid = gid
                    target_label = str((hit or {}).get("name") or ref).strip()
                if not schedule_enabled():
                    try:
                        msg = self._as_ux_line(
                            "ZALO_SCHEDULE_DELETE_UNAVAILABLE_MSG",
                            ("schedule", "delete_unavailable"),
                            "Chưa bật schedule-worker nên chưa xóa được lịch.",
                            user_text=text,
                        )
                        await self._as_gate_announce(thread_id, thread_type, msg)
                    except Exception:
                        pass
                    return True
                deleted = delete_schedules_for_thread(target_tid)
                try:
                    if deleted:
                        where = f" nhóm {target_label}" if target_label else ""
                        base = f"Đã xóa {len(deleted)} lịch{where}."
                    else:
                        where = f" nhóm {target_label}" if target_label else " chat này"
                        base = f"Không có lịch nào để xóa trong{where}."
                    msg = self._as_ux_line(
                        "ZALO_SCHEDULE_DELETED_MSG",
                        ("schedule", "deleted"),
                        base,
                        user_text=text,
                    )
                    await self._as_gate_announce(thread_id, thread_type, msg)
                except Exception:
                    pass
                return True
            lifecycle_actions = {"pause", "resume", "update", "run_now", "run"}
            lifecycle_types = {
                "pause_schedule",
                "resume_schedule",
                "update_schedule",
                "run_schedule",
            }
            if skill_action in lifecycle_actions or task_type in lifecycle_types:
                return await self._as_schedule_lifecycle(
                    text=text,
                    current=current,
                    thread_id=thread_id,
                    thread_type=thread_type,
                    plan=plan,
                )
            if not _schedule_fanout_child:
                try:
                    from .schedule_client import (
                        independent_schedule_plans,
                        plan_needs_schedule_ask,
                    )
                except ImportError:
                    from schedule_client import (  # type: ignore
                        independent_schedule_plans,
                        plan_needs_schedule_ask,
                    )
                if plan_needs_schedule_ask(plan):
                    try:
                        missing = plan.get("missing") or []
                        miss = ", ".join(str(x) for x in missing if str(x).strip()) or "time"
                        msg = self._as_ux_line(
                            "ZALO_SCHEDULE_FAILED_MSG",
                            ("schedule", "failed"),
                            f"Chưa đủ thông tin để lưu lịch ({miss}). Gửi lại giờ chạy cụ thể.",
                            user_text=text,
                        )
                        await self._as_gate_announce(thread_id, thread_type, msg)
                    except Exception:
                        pass
                    return True
                sched_jobs = independent_schedule_plans(plan)
                if len(sched_jobs) > 1:
                    ok_n = 0
                    for job in sched_jobs:
                        if await self._as_try_workflow_submit(
                            text=current,
                            thread_id=thread_id,
                            thread_type=thread_type,
                            sender_id=sender_id,
                            sender_name=sender_name,
                            chat_type=chat_type,
                            plan=job,
                            schedule_fire=False,
                            _schedule_fanout_child=True,
                            received_at=received_at,
                        ):
                            ok_n += 1
                    if ok_n:
                        try:
                            msg = self._as_ux_line(
                                "ZALO_SCHEDULE_SAVED_MSG",
                                ("schedule", "saved"),
                                f"Đã lưu {ok_n} lịch (mỗi yêu cầu một giờ chạy).",
                                user_text=text,
                            )
                            await self._as_gate_announce(thread_id, thread_type, msg)
                        except Exception:
                            pass
                        return True
                    logger.warning("[zalo] independent schedule fanout stored 0 jobs")
                    try:
                        msg = self._as_ux_line(
                            "ZALO_SCHEDULE_FAILED_MSG",
                            ("schedule", "failed"),
                            "Could not save this lịch. Please send it again.",
                            user_text=text,
                        )
                        await self._as_gate_announce(thread_id, thread_type, msg)
                    except Exception:
                        pass
                    return True
            try:
                from .channels_client import apply_schedule_delivery_target
            except ImportError:
                from channels_client import apply_schedule_delivery_target  # type: ignore
            origin, context, target_note = apply_schedule_delivery_target(
                text=current,
                plan=plan,
                origin=origin,
                context=context,
                current_thread_type=thread_type,
            )
            if target_note and str(target_note).startswith("group_not_found:"):
                ref = target_note.split(":", 1)[-1]
                try:
                    msg = self._as_ux_line(
                        "ZALO_SCHEDULE_GROUP_NOT_FOUND_MSG",
                        ("schedule", "group_not_found"),
                        (
                            f"Chưa biết nhóm '{ref}'. Vào nhóm đó gửi !zalo allow / "
                            f"!zalo label, hoặc !zalo refresh rồi đặt lịch lại."
                        ),
                        user_text=text,
                    )
                    await self._as_gate_announce(thread_id, thread_type, msg)
                except Exception:
                    pass
                return True
            if target_note:
                logger.info("[zalo] schedule %s", target_note)
            fire_text = fire_text_from_plan(plan, current)
            delivery = schedule_delivery_mode(plan, current)
            origin["schedule_delivery"] = delivery
            context["schedule_delivery"] = delivery
            recv_iso = (
                received_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if hasattr(received_at, "astimezone")
                else str(received_at or "")
            )
            context["original_request"] = current
            context["execution_payload"] = fire_text
            context["request_received_at"] = recv_iso
            context["reference_time_source"] = "schedule_request_received_at"
            context["plan"] = plan
            # Authoritative timing: once_after uses host clock + delay_seconds.
            # Never prefer LLM-invented next_run_at / cron for relative delays.
            try:
                from .schedule_client import resolve_schedule_timing
            except ImportError:
                from schedule_client import resolve_schedule_timing  # type: ignore
            timing = resolve_schedule_timing(
                plan,
                current,
                tz=str((plan or {}).get("timezone") or "Asia/Ho_Chi_Minh"),
                received_at=received_at,
            )
            next_run_at = str(timing.get("next_run_at") or "")
            cron_expr = str(timing.get("cron_expr") or plan.get("cron_expr") or "")
            cadence = str(timing.get("cadence") or plan.get("cadence") or "")
            if str(timing.get("schedule_form") or "") == "once_after" and not next_run_at:
                logger.warning("[zalo] once_after missing delay_seconds from classify")
                try:
                    msg = self._as_ux_line(
                        "ZALO_SCHEDULE_FAILED_MSG",
                        ("schedule", "failed"),
                        "Could not save this lịch. Please send it again.",
                        user_text=text,
                    )
                    await self._as_gate_announce(thread_id, thread_type, msg)
                except Exception:
                    pass
                return True
            if schedule_enabled():
                data = go_create_schedule(
                    cron_expr=cron_expr,
                    text=current,
                    fire_text=fire_text,
                    origin=origin,
                    context=context,
                    cadence=cadence,
                    timezone=str(plan.get("timezone") or "Asia/Ho_Chi_Minh"),
                    next_run_at=next_run_at or None,
                )
            else:
                data = create_schedule(
                    cron_expr=cron_expr,
                    text=current,
                    origin=origin,
                    context=context,
                    cadence=cadence,
                    next_run_at=next_run_at or None,
                )
            if data.get("ok"):
                logger.info("[zalo] schedule stored delivery=%s", delivery)
                if _schedule_fanout_child:
                    return True
                try:
                    dest = str(
                        origin.get("target_name")
                        or origin.get("chat_name")
                        or origin.get("thread_id")
                        or ""
                    ).strip()
                    dest_is_group = str(context.get("thread_type") or "").lower() in {
                        "group",
                        "g",
                    }
                    cross = dest_is_group and str(origin.get("thread_id") or "") != str(
                        thread_id
                    )
                    sid = str(data.get("id") or (data.get("schedule") or {}).get("id") or "")
                    next_at = str(
                        data.get("next_run_at")
                        or (data.get("schedule") or {}).get("next_run_at")
                        or ""
                    )
                    base_msg = "Đã lưu lịch."
                    if next_at:
                        base_msg = f"Đã lưu lịch. Lần chạy tới: {next_at}."
                    if sid:
                        base_msg = f"{base_msg} id={sid}"
                    if cross and dest:
                        base_msg = f"{base_msg} → nhóm {dest}."
                    msg = self._as_ux_line(
                        "ZALO_SCHEDULE_SAVED_MSG",
                        ("schedule", "saved"),
                        base_msg,
                        user_text=text,
                    )
                    # UX file may return a short fixed string — always re-append destination.
                    if cross and dest and "→ nhóm" not in msg and "nhóm" not in msg.lower():
                        msg = f"{msg.rstrip()} → nhóm {dest}."
                    await self._as_gate_announce(thread_id, thread_type, msg)
                except Exception:
                    pass
                return True
            logger.warning("[zalo] schedule store failed")
            try:
                msg = self._as_ux_line(
                    "ZALO_SCHEDULE_FAILED_MSG",
                    ("schedule", "failed"),
                    "Could not save this lịch. Please send it again.",
                    user_text=text,
                )
                await self._as_gate_announce(thread_id, thread_type, msg)
            except Exception:
                pass
            return True
        if has_image_attachment:
            ins_parts = [str(x).strip() for x in (plan.get("instructions") or []) if str(x).strip()]
            explicit_office = bool(
                plan_output_type(plan) and _instruction_is_office_file_body(ins_parts)
            )
            if plan_is_image_analyze_chat(plan, has_image=True) or not explicit_office:
                return False
        if not workflow_enabled():
            return False
        if plan_media_shortcut_gate(plan) or plan_is_search_then_image_turn(plan):
            return await self._as_run_host_media_shortcut(
                user_text=current,
                thread_id=thread_id,
                thread_type=thread_type,
                bare_text=current,
                plan=plan,
                has_image_attachment=has_image_attachment,
            )
        parts = [str(x).strip() for x in (plan.get("instructions") or []) if str(x).strip()]
        async_job = plan_is_async(plan) or (
            len(parts) >= 2
            and not plan_media_shortcut_gate(plan)
            and not plan_is_search_then_image_turn(plan)
        )
        if not async_job or not parts:
            return False
        data = create_workflow(
            instructions=parts,
            origin=origin,
            context=context,
            task_details=plan.get("task_details") if isinstance(plan.get("task_details"), list) else [],
            sequential=plan_compound_sequential(plan),
        )
        if not data.get("ok"):
            return False
        try:
            if plan_is_async(plan) or len(parts) >= 2:
                msg = self._as_ux_line(
                    "ZALO_WORKFLOW_ACK_MSG",
                    ("workflow", "started"),
                    "Đang xử lý…",
                    user_text=current,
                )
                await self._as_gate_announce(thread_id, thread_type, msg)
        except Exception:
            pass
        logger.info(f"[zalo] workflow created jobs={len(parts)} class={plan.get('execution_class')}")
        logger.info("Zalo: workflow %s jobs=%s", (data.get("workflow") or {}).get("id"), len(parts))
        return True

    def _as_workflow_parallel(self) -> int:
        return int(self._as_env_float("ZALO_WORKFLOW_PARALLEL", 4.0, 1.0, 16.0))

    def _as_zalo_api_chat_id(self, chat_id: str) -> str:
        try:
            from .turn_wait import real_thread_id
        except ImportError:
            from turn_wait import real_thread_id  # type: ignore
        return real_thread_id(chat_id)

    async def _as_with_dest_send_lock(self, dest_id: str, fn):
        did = str(dest_id or "")
        locks = self._as_dest_send_locks
        lock = locks.get(did)
        if lock is None:
            lock = asyncio.Lock()
            locks[did] = lock
        async with lock:
            return await fn()

    async def _as_workflow_worker(self) -> None:
        try:
            from .workflow_client import claim_job, fail_job, workflow_enabled
        except ImportError:
            from workflow_client import claim_job, fail_job, workflow_enabled  # type: ignore
        wid = _replica_id() or "zalo"
        inflight = self._as_workflow_inflight
        while not self._stop:
            if not workflow_enabled():
                await asyncio.sleep(5)
                continue
            inflight.difference_update({t for t in list(inflight) if t.done()})
            if len(inflight) >= self._as_workflow_parallel():
                await asyncio.sleep(0.25)
                continue
            try:
                job = claim_job(wid)
            except Exception:
                job = None
            if not isinstance(job, dict) or not job.get("id"):
                await asyncio.sleep(1.2)
                continue
            jid = str(job.get("id"))
            instruction = str(job.get("instruction") or "").strip()
            ctx = job.get("context") if isinstance(job.get("context"), dict) else {}
            tid = str(ctx.get("thread_id") or "")
            if not tid or not instruction:
                fail_job(jid, "missing thread or instruction")
                continue
            task = asyncio.create_task(self._as_run_workflow_job(job, wid))
            inflight.add(task)
            task.add_done_callback(inflight.discard)

    async def _as_run_workflow_job(self, job: dict, wid: str) -> None:
        try:
            from .workflow_client import complete_job, fail_job, heartbeat
        except ImportError:
            from workflow_client import complete_job, fail_job, heartbeat  # type: ignore
        try:
            from .turn_wait import isolate_session_chat_id
        except ImportError:
            from turn_wait import isolate_session_chat_id  # type: ignore
        jid = str(job.get("id"))
        instruction = str(job.get("instruction") or "").strip()
        if instruction and "images/generations" not in instruction and "skill image-gen" not in instruction.lower():
            instruction = (
                instruction
                + "\n\nIf this task creates a still image: use skill image-gen "
                "(diffusion via the image-gen combo; English photorealistic prompt, save under /opt/data/media/out). "
                "Video/music asks: skill video-gen (policy refuse). User-facing: the file only."
            )
        ctx = job.get("context") if isinstance(job.get("context"), dict) else {}
        tid = str(ctx.get("thread_id") or "")
        tt = str(ctx.get("thread_type") or "user")
        chat_type = str(ctx.get("chat_type") or "dm")
        sender_id = str(ctx.get("sender_id") or "")
        sender_name = str(ctx.get("sender_name") or tid)
        iso = isolate_session_chat_id(tid, jid)
        zalo_tt = "group" if tt == "group" or chat_type == "group" else "user"
        try:
            self._thread_types[iso] = zalo_tt
            self._thread_types[tid] = zalo_tt
        except Exception:
            pass
        self._as_autosend_remember_turn(iso, zalo_tt)
        source = self.build_source(
            chat_id=iso,
            chat_name=sender_name if chat_type == "dm" else tid,
            chat_type=chat_type,
            user_id=f"{sender_id}:{jid}" if sender_id else jid,
            user_name=sender_name,
        )
        event = MessageEvent(
            text=instruction,
            message_type=MessageType.TEXT,
            source=source,
            message_id=jid,
            raw_message={},
            timestamp=datetime.now(),
        )
        self._as_compound_begin(iso)
        stop = asyncio.Event()
        watch = asyncio.create_task(self._as_watch_job_files(iso, zalo_tt, stop))
        try:
            def _pulse() -> None:
                heartbeat(jid, wid)

            _pulse()
            blocked, block_msg = await self._as_security_message_gate(
                text=instruction,
                thread_id=tid,
                user_id=sender_id,
                correlation_id=jid,
            )
            if blocked:
                if block_msg:
                    await self._as_gate_announce(tid, zalo_tt, block_msg)
                complete_job(jid, {"ok": False, "blocked": "security"})
                return
            await self.handle_message(event)
            idle = await self._as_wait_thread_idle(
                iso, pulse=_pulse, arm_first=True
            )
            await self._as_autosend_late_files(iso, zalo_tt)
            complete_job(jid, {"ok": True, "idle": idle, "isolated": True})
            logger.info(f"[zalo] workflow job done {jid[:16]} idle={idle}")
        except Exception as e:
            logger.exception("Zalo: workflow job failed")
            try:
                msg = self._as_ux_line(
                    "ZALO_SESSION_INTERRUPTED_MSG",
                    ("session", "interrupted"),
                    "This session was interrupted. Please try again later.",
                    user_text=instruction,
                )
                await self._as_gate_announce(tid, zalo_tt, msg)
            except Exception:
                pass
            try:
                complete_job(
                    jid,
                    {"ok": False, "error": type(e).__name__},
                )
            except Exception:
                fail_job(jid, type(e).__name__)
        finally:
            self._as_set_file_ceiling(iso)
            self._as_cancel_late_autosend(iso)
            stop.set()
            watch.cancel()
            try:
                await watch
            except (asyncio.CancelledError, Exception):
                pass
            self._as_compound_end(iso)
            self._as_compound_seq_done(iso)

    async def _as_wait_thread_idle(
        self,
        thread_id: str,
        *,
        pulse=None,
        arm_first: bool = False,
    ) -> bool:
        try:
            from .turn_wait import wait_thread_idle
        except ImportError:
            from turn_wait import wait_thread_idle  # type: ignore
        timeout = self._as_env_float("ZALO_WORKFLOW_TURN_TIMEOUT_S", 420.0, 30.0, 900.0)
        return await wait_thread_idle(
            lambda: getattr(self, "_active_sessions", None),
            thread_id,
            timeout_s=timeout,
            pulse=pulse,
            arm_first=arm_first,
        )

    def _as_compound_mark_delivered(self, thread_id: str) -> None:
        ev = self._as_part_delivered.get(str(thread_id or ""))
        if ev is not None:
            ev.set()

    def _as_media_done_caption(self) -> str:
        return ""

    def _as_is_media_ack_only(self, content: str) -> bool:
        t = (content or "").strip().lower().rstrip(".!?")
        if not t:
            return True
        return t in {"đã xong", "da xong", "done", "xong"}

    def _as_compound_set_after(self, thread_id: str, after: int, thread_type: str = "") -> None:
        tid = str(thread_id or "")
        if after > 0:
            self._as_compound_after[tid] = after
            if thread_type:
                self._as_compound_thread_type[tid] = thread_type
        else:
            self._as_compound_after.pop(tid, None)

    def _as_compound_has_more_after(self, thread_id: str) -> bool:
        return self._as_compound_after.get(str(thread_id or ""), 0) > 0

    async def _as_compound_maybe_final_ack(self, thread_id: str) -> None:
        tid = str(thread_id or "")
        self._as_compound_defer_ack.discard(tid)
        self._as_compound_thread_type.pop(tid, None)

    async def _as_compound_wait_part(self, thread_id: str) -> None:
        """Optionally wait for outbound delivery; default is no wait.

        Queue UX: once a part is dequeued and handle_message returns, release
        answering so the next FIFO item can run. Waiting on mark_delivered
        (historically up to 180s) burned the queue turn budget and often
        prevented the timeout UX from reaching the user.
        Set ZALO_COMPOUND_WAIT_FOR_DELIVERY=1 to restore the old wait.
        """
        tid = str(thread_id or "")
        wait = (os.getenv("ZALO_COMPOUND_WAIT_FOR_DELIVERY") or "0").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        gap = self._as_env_float("ZALO_COMPOUND_GAP_S", 0.0 if not wait else 4.0, 0.0, 30.0)
        if wait:
            timeout = self._as_env_float("ZALO_COMPOUND_PART_TIMEOUT_S", 35.0, 5.0, 120.0)
            ev = self._as_part_delivered.get(tid)
            if ev is not None:
                if ev.is_set():
                    ev.clear()
                else:
                    try:
                        await asyncio.wait_for(ev.wait(), timeout=timeout)
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Zalo: compound part wait timeout thread=%s — continue without delivery",
                            tid,
                        )
                    ev.clear()
        else:
            # Do not block the queue on delivery; clear a stale event if present.
            ev = self._as_part_delivered.get(tid)
            if ev is not None and ev.is_set():
                ev.clear()
        if gap > 0:
            await asyncio.sleep(gap)

    async def _as_watch_job_files(
        self, thread_id: str, thread_type: str, stop: asyncio.Event
    ) -> None:
        """While an isolated lịch job runs, attach files as soon as they land."""
        tid = str(thread_id or "")
        if not tid:
            return
        meta = {"thread_type": thread_type or "user", "as_skip_dest": True}
        while not stop.is_set():
            try:
                await self._as_autosend_turn_files(tid, "", meta)
            except Exception:
                logger.warning("Zalo: job file watch failed thread=%s", tid[:24], exc_info=True)
            try:
                await asyncio.wait_for(stop.wait(), timeout=1.2)
            except asyncio.TimeoutError:
                continue

    async def _as_autosend_late_files(self, thread_id: str, thread_type: str = "") -> bool:
        """After handle_message, attach a file that landed as the model finished."""
        tid = str(thread_id or "")
        if not tid:
            return False
        grace = self._as_env_float("ZALO_AUTOSEND_LATE_S", 8.0, 0.0, 180.0)
        try:
            from .turn_wait import is_isolated_session
        except ImportError:
            from turn_wait import is_isolated_session  # type: ignore
        if is_isolated_session(tid):
            grace = max(grace, self._as_env_float("ZALO_AUTOSEND_JOB_LATE_S", 45.0, 8.0, 180.0))
        if grace <= 0:
            return False
        start = __import__("time").time()
        deadline = start + grace
        # Mid-sequence: don't stall text parts. Isolated lịch jobs wait for media.
        idle = grace if not self._as_compound_has_more_after(tid) else min(1.6, grace)
        seen = getattr(self, "_as_sent_fp", None)
        n_before = len(seen) if isinstance(seen, set) else 0
        meta = {"thread_type": thread_type or "user", "as_skip_dest": True}
        sent = False
        last_hit = start
        while True:
            await self._as_autosend_turn_files(tid, "", meta)
            seen = getattr(self, "_as_sent_fp", None)
            n_after = len(seen) if isinstance(seen, set) else 0
            now = __import__("time").time()
            if n_after > n_before:
                sent = True
                n_before = n_after
                last_hit = now
                continue
            if now >= deadline:
                break
            if (now - last_hit) >= idle:
                break
            await asyncio.sleep(0.45)
        # Only mark delivered when a file actually went out. A timeout here
        # used to flip the event and let the next sequential item start while
        # the current Hermes turn was still running.
        if sent:
            self._as_compound_mark_delivered(tid)
        return sent

    def _as_kick_late_autosend(self, chat_id, metadata=None) -> None:
        """Cron / single-turn: keep watching media-out after the text send returns."""
        tid = str(chat_id or "")
        if not tid:
            return
        try:
            from .turn_wait import is_isolated_session
        except ImportError:
            from turn_wait import is_isolated_session  # type: ignore
        # Isolated lịch jobs watch files themselves; do not spawn a late
        # task that outlives the job and steals the next run's media.
        if is_isolated_session(tid):
            return
        if tid in self._as_hold_inflight:
            return
        meta = metadata if isinstance(metadata, dict) else {}
        if meta.get("as_skip_autosend"):
            return
        tasks = getattr(self, "_as_late_tasks", None)
        if not isinstance(tasks, dict):
            self._as_late_tasks = {}
            tasks = self._as_late_tasks
        prev = tasks.get(tid)
        if prev is not None and not prev.done():
            return
        tt = str(meta.get("thread_type") or "user")
        tasks[tid] = asyncio.create_task(self._as_autosend_late_files(tid, tt))

    def _as_cancel_late_autosend(self, thread_id: str) -> None:
        tid = str(thread_id or "")
        tasks = getattr(self, "_as_late_tasks", None)
        if not isinstance(tasks, dict):
            return
        prev = tasks.pop(tid, None)
        if prev is not None and not prev.done():
            prev.cancel()

    def _as_set_file_ceiling(self, thread_id: str, when=None) -> None:
        tid = str(thread_id or "")
        if not tid:
            return
        caps = getattr(self, "_as_file_ceiling", None)
        if not isinstance(caps, dict):
            self._as_file_ceiling = {}
            caps = self._as_file_ceiling
        caps[tid] = float(when if when is not None else __import__("time").time())

    def _as_mark_job_file_sent(self, thread_id: str) -> None:
        tid = str(thread_id or "")
        if not tid:
            return
        seen = getattr(self, "_as_job_file_sent", None)
        if not isinstance(seen, set):
            self._as_job_file_sent = set()
            seen = self._as_job_file_sent
        seen.add(tid)

    def _as_clear_job_file_sent(self, thread_id: str) -> None:
        """Clear same-turn media-result mute so later schedule/chat text can send."""
        tid = str(thread_id or "")
        if not tid:
            return
        seen = getattr(self, "_as_job_file_sent", None)
        if isinstance(seen, set):
            seen.discard(tid)

    def _as_job_already_sent_file(self, thread_id: str) -> bool:
        seen = getattr(self, "_as_job_file_sent", None)
        return isinstance(seen, set) and str(thread_id or "") in seen

    def _as_remux_zalo_video(self, path: str) -> str:
        """Re-encode mp4 to baseline H.264 so Zalo send-attachment accepts it."""
        import shutil
        import subprocess
        from pathlib import Path

        src = Path(str(path or ""))
        if not src.is_file():
            return str(path or "")
        if src.suffix.lower() not in {".mp4", ".mov", ".m4v", ".webm", ".mkv"}:
            return str(src)
        ffmpeg = shutil.which("ffmpeg")
        overwrite = src.name.endswith(".zalo.mp4")
        dest = src.with_name(src.stem + ".next.mp4") if overwrite else src.with_name(src.stem + ".zalo.mp4")
        if ffmpeg:
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(src),
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=mono:sample_rate=44100",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                "baseline",
                "-level",
                "3.1",
                "-vf",
                "scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
                "-b:v",
                "800k",
                "-r",
                "25",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(dest),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=90)
            except Exception:
                logger.warning("Zalo: ffmpeg remux failed for %s", src.name)
                ffmpeg = None
        if not ffmpeg or not dest.is_file():
            try:
                import json as _json
                import os
                import urllib.request

                base = (os.getenv("DISPATCHER_URL") or "http://dispatcher:8090").rstrip("/")
                body = _json.dumps({"filename": src.name}).encode("utf-8")
                req = urllib.request.Request(
                    base + "/v1/video-remux",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = _json.loads(resp.read().decode("utf-8") or "{}")
                remote = str((data or {}).get("file") or "")
                if remote:
                    mapped = Path(remote.replace("/data/media/out", str(src.parent)))
                    if mapped.is_file():
                        return str(mapped)
                    sibling = src.with_name(src.stem + ".zalo.mp4")
                    if sibling.is_file():
                        return str(sibling)
            except Exception:
                logger.warning("Zalo: dispatcher remux failed for %s", src.name)
                return str(src)
        try:
            if dest.is_file() and dest.stat().st_size > 1000:
                if overwrite:
                    dest.replace(src)
                    logger.info("Zalo: remuxed video %s", src.name)
                    return str(src)
                logger.info("Zalo: remuxed video %s → %s", src.name, dest.name)
                return str(dest)
        except OSError:
            pass
        return str(src)

    def _as_inbound_queue_enabled(self) -> bool:
        try:
            from .inbound_queue import queue_flag_on
        except ImportError:
            from inbound_queue import queue_flag_on  # type: ignore
        if not queue_flag_on():
            return False
        return self._as_gate_store() is not None

    def _as_queue_turn_timeout_s(self) -> float:
        """Max seconds for one queued Hermes turn (handle_message + late files + wait).

        Product floor is 15 minutes so archive/OCR/LLM work is not cut off early.
        """
        val = self._as_env_float(
            "ZALO_QUEUE_TURN_TIMEOUT_S",
            ZALO_TURN_WAIT_DEFAULT_S,
            30.0,
            ZALO_TURN_WAIT_MAX_S,
        )
        return max(ZALO_TURN_WAIT_DEFAULT_S, val)

    def _as_queue_drain_max_s(self) -> float:
        """Max seconds one drain task may hold the per-thread worker lock.

        Must stay above turn timeout so a long zip extract is not cancelled mid-ack.
        """
        val = self._as_env_float(
            "ZALO_QUEUE_DRAIN_MAX_S",
            ZALO_DRAIN_DEFAULT_S,
            60.0,
            max(ZALO_TURN_WAIT_MAX_S * 2, 3600.0),
        )
        return max(ZALO_DRAIN_DEFAULT_S, val, self._as_queue_turn_timeout_s())

    def _as_queue_kick(self, thread_id: str) -> None:
        tid = str(thread_id or "")
        if not tid:
            return
        prev = self._as_queue_tasks.get(tid)
        if prev is not None and not prev.done():
            # Stuck drain: cancel after drain-max so a new kick can restart.
            started = float(getattr(prev, "_as_drain_started", 0.0) or 0.0)
            age = (__import__("time").time() - started) if started > 0 else 0.0
            if age < self._as_queue_drain_max_s():
                return
            logger.warning(
                "Zalo: cancel stuck queue drain thread=%s age=%.0fs",
                tid,
                age,
            )
            prev.cancel()
        task = asyncio.create_task(self._as_queue_drain(tid))
        task._as_drain_started = __import__("time").time()  # type: ignore[attr-defined]
        self._as_queue_tasks[tid] = task

    async def _as_enqueue_inbound(
        self,
        *,
        text: str,
        thread_id: str,
        thread_type: str,
        sender_id: str,
        sender_name: str,
        chat_type: str,
        message_id: str,
        media_urls: List[str],
        media_types: List[str],
        message_type: str,
        rate_over: bool,
        rate_notify: bool,
        event,
        schedule_fire: bool = False,
        has_image_attachment: bool = False,
    ) -> None:
        try:
            from .inbound_queue import (
                KIND_INBOUND,
                encode_item,
                make_item,
                queue_max,
                queue_ttl_s,
            )
        except ImportError:
            from inbound_queue import (  # type: ignore
                KIND_INBOUND,
                encode_item,
                make_item,
                queue_max,
                queue_ttl_s,
            )
        store = self._as_gate_store()
        if store is None:
            if await self._as_try_image_analyze_vision_reply(
                text=text,
                thread_id=thread_id,
                thread_type=thread_type,
                media_urls=media_urls,
                has_image_attachment=has_image_attachment,
            ):
                return
            if await self._as_try_workflow_submit(
                text=text,
                thread_id=thread_id,
                thread_type=thread_type,
                sender_id=sender_id,
                sender_name=sender_name,
                chat_type=chat_type,
                schedule_fire=schedule_fire,
                has_image_attachment=has_image_attachment,
            ):
                return
            await self._as_dispatch_event(event, text)
            return
        item = make_item(
            kind=KIND_INBOUND,
            text=text,
            thread_id=thread_id,
            thread_type=thread_type,
            sender_id=sender_id,
            sender_name=sender_name,
            chat_type=chat_type,
            message_id=message_id,
            media_urls=media_urls,
            media_types=media_types,
            message_type=message_type,
            schedule_fire=schedule_fire,
        )
        mid = str(message_id or "")
        try:
            if await self._as_try_image_analyze_vision_reply(
                text=text,
                thread_id=thread_id,
                thread_type=thread_type,
                media_urls=media_urls,
                has_image_attachment=has_image_attachment,
            ):
                return
            if await self._as_try_workflow_submit(
                text=text,
                thread_id=thread_id,
                thread_type=thread_type,
                sender_id=sender_id,
                sender_name=sender_name,
                chat_type=chat_type,
                schedule_fire=schedule_fire,
                has_image_attachment=has_image_attachment,
            ):
                return
            # Schedule fires must not wait behind stuck answering / FIFO queue —
            # inject already delivered the work text; run it immediately.
            if schedule_fire:
                logger.info(
                    "Zalo: scheduleFire bypass queue thread=%s",
                    thread_id[:24],
                )
                await self._as_dispatch_event(event, text)
                return
            if mid and hasattr(store, "queue_seen") and not store.queue_seen(mid):
                logger.info("Zalo: skip duplicate queue id=%s", mid[:24])
                self._as_queue_kick(thread_id)
                return
            n = store.queue_push(thread_id, encode_item(item), queue_max(), queue_ttl_s())
        except Exception as e:
            logger.warning("Zalo: queue push failed %s — inline", type(e).__name__)
            await self._as_dispatch_event(event, text)
            return
        if n < 0:
            msg = self._as_ux_line(
                "ZALO_QUEUE_FULL_MSG",
                ("queue", "full"),
                "Hàng chờ đầy. Gửi lại sau giúp mình.",
            )
            try:
                await self._as_gate_announce(thread_id, thread_type, msg)
            except Exception:
                pass
            return
        # Per-thread FIFO: one worker drains; later messages wait in Valkey queue.
        if n > 1 or rate_over:
            msg = self._as_ux_line(
                "ZALO_QUEUE_QUEUED_MSG",
                ("queue", "queued"),
                "Mình đang trả lời tin trước. Vui lòng chờ — tin mới đã vào hàng chờ.",
            )
            try:
                if rate_over and rate_notify:
                    await self._as_gate_announce(thread_id, thread_type, msg)
                elif n > 1:
                    await self._as_gate_announce(thread_id, thread_type, msg)
            except Exception as e:
                logger.warning("Zalo: queue announce failed: %s", type(e).__name__)
        elif rate_over and rate_notify:
            msg = self._as_ux_line(
                "ZALO_RATE_LIMIT_MSG",
                ("queue", "rate_limited"),
                "Bạn gửi hơi nhanh — tin này đã vào hàng chờ, mình trả lời lần lượt.",
            )
            try:
                await self._as_gate_announce(thread_id, thread_type, msg)
            except Exception as e:
                logger.warning("Zalo: rate-limit announce failed: %s", type(e).__name__)
        logger.info("Zalo: inbound queued thread=%s len=%s rate_over=%s", thread_id, n, rate_over)
        try:
            from .queue_history import record as history_record
        except ImportError:
            from queue_history import record as history_record  # type: ignore
        history_record(
            thread_id=thread_id,
            thread_type=thread_type,
            message_id=mid,
            event="enqueued",
            role="user",
            content=text,
            task_hint="normal",
            queue_depth=n if n >= 0 else None,
        )
        self._as_queue_kick(thread_id)

    async def _as_queue_drain(self, thread_id: str) -> None:
        tid = str(thread_id or "")
        store = self._as_gate_store()
        if store is None or not tid:
            return
        try:
            if not store.worker_try(tid, 300):
                return
        except Exception:
            return
        try:
            from .inbound_queue import KIND_PART, decode_item, encode_item, make_item, queue_ttl_s
        except ImportError:
            from inbound_queue import KIND_PART, decode_item, encode_item, make_item, queue_ttl_s  # type: ignore
        try:
            from .multi_request import split_compound_requests
        except ImportError:
            split_compound_requests = lambda t: [t]  # type: ignore[misc, assignment]
        loop = asyncio.get_running_loop()
        drain_deadline = loop.time() + self._as_queue_drain_max_s()
        try:
            while True:
                if loop.time() >= drain_deadline:
                    logger.warning(
                        "Zalo: queue drain max exceeded thread=%s — release for next kick",
                        tid,
                    )
                    break
                try:
                    raw = store.queue_pop(tid)
                except Exception:
                    break
                if not raw:
                    break
                try:
                    store.worker_touch(tid, 300)
                except Exception:
                    pass
                item = decode_item(raw)
                if not item:
                    continue
                text = str(item.get("text") or "")
                kind = str(item.get("kind") or KIND_PART)
                if kind != KIND_PART:
                    parts = split_compound_requests(text) or [text]
                    rest = parts[1:]
                    text = parts[0] if parts else text
                    total = len(parts)
                    if len(parts) >= 2:
                        try:
                            from .multi_request import wrap_compound_part
                        except ImportError:
                            from multi_request import wrap_compound_part  # type: ignore
                        total = len(parts)
                        text = wrap_compound_part(1, total, text)
                        logger.info(f"[zalo] compound split n={total} via queue")
                        logger.info("Zalo: compound message split into %d parts (queue)", total)
                    item["text"] = text
                    item["kind"] = KIND_PART
                    for i, part in enumerate(reversed(rest)):
                        part_n = total - i if len(parts) >= 2 else 2
                        body = wrap_compound_part(part_n, total, part) if len(parts) >= 2 else part
                        nxt = make_item(
                            kind=KIND_PART,
                            text=body,
                            thread_id=tid,
                            thread_type=str(item.get("thread_type") or "user"),
                            sender_id=str(item.get("sender_id") or ""),
                            sender_name=str(item.get("sender_name") or ""),
                            chat_type=str(item.get("chat_type") or "dm"),
                            message_id=str(item.get("message_id") or "") + f":part{part_n}",
                            media_urls=[],
                            media_types=[],
                            message_type=str(item.get("message_type") or "TEXT"),
                        )
                        try:
                            store.queue_push_front(tid, encode_item(nxt), queue_ttl_s())
                        except Exception:
                            pass
                await self._as_run_queued_part(item)
        except asyncio.CancelledError:
            logger.warning("Zalo: queue drain cancelled thread=%s", tid)
            raise
        finally:
            try:
                store.worker_done(tid)
            except Exception:
                pass
            try:
                leftover = store.queue_len(tid)
            except Exception:
                leftover = 0
            if leftover > 0 and not self._stop:
                self._as_queue_kick(tid)

    async def _as_run_queued_part(self, item: dict) -> None:
        tid = str(item.get("thread_id") or "")
        if not tid:
            return
        try:
            from .queue_history import record as history_record
        except ImportError:
            from queue_history import record as history_record  # type: ignore
        history_record(
            thread_id=tid,
            thread_type=str(item.get("thread_type") or "user"),
            message_id=str(item.get("message_id") or ""),
            event="processing",
            role="user",
            content=str(item.get("text") or ""),
            task_hint="normal",
        )
        deadline = asyncio.get_event_loop().time() + self._as_env_float(
            "ZALO_COMPOUND_PART_TIMEOUT_S", 35.0, 5.0, 120.0
        )
        while asyncio.get_event_loop().time() < deadline:
            if self._as_inflight_try(tid):
                break
            await asyncio.sleep(0.45)
        else:
            logger.warning("Zalo: queue part no answering slot thread=%s — requeue", tid)
            store = self._as_gate_store()
            try:
                from .inbound_queue import encode_item, queue_ttl_s
            except ImportError:
                from inbound_queue import encode_item, queue_ttl_s  # type: ignore
            if store is not None:
                try:
                    store.queue_push_front(tid, encode_item(item), queue_ttl_s())
                except Exception:
                    pass
            return
        chat_type = str(item.get("chat_type") or "dm")
        sender_id = str(item.get("sender_id") or "")
        sender_name = str(item.get("sender_name") or tid)
        source = self.build_source(
            chat_id=tid,
            chat_name=sender_name if chat_type == "dm" else tid,
            chat_type=chat_type,
            user_id=sender_id,
            user_name=sender_name,
        )
        mt_name = str(item.get("message_type") or "TEXT")
        mt = getattr(MessageType, mt_name, MessageType.TEXT)
        event = MessageEvent(
            text=str(item.get("text") or ""),
            message_type=mt,
            source=source,
            message_id=str(item.get("message_id") or ""),
            raw_message={},
            media_urls=list(item.get("media_urls") or []),
            media_types=list(item.get("media_types") or []),
            timestamp=datetime.now(),
        )
        parts_after = 0
        store = self._as_gate_store()
        if store is not None:
            try:
                parts_after = int(store.queue_len(tid) or 0)
            except Exception:
                parts_after = 0
        thread_type = str(item.get("thread_type") or "user")
        self._as_compound_set_after(tid, parts_after, thread_type)
        self._as_compound_begin(tid)
        turn_timeout = self._as_queue_turn_timeout_s()
        try:
            async def _run_turn() -> None:
                blocked, block_msg = await self._as_security_message_gate(
                    text=str(event.text or ""),
                    thread_id=tid,
                    user_id=sender_id,
                    correlation_id=str(event.message_id or ""),
                )
                if blocked:
                    if block_msg:
                        await self._as_gate_announce(tid, thread_type, block_msg)
                    return
                bare_q = str(event.text or "").strip()
                if bare_q and not list(event.media_urls or []):
                    if await self._as_run_host_media_shortcut(
                        user_text=bare_q,
                        thread_id=tid,
                        thread_type=thread_type,
                        bare_text=bare_q,
                    ):
                        return
                has_image = self._as_has_image_attachment(
                    list(event.media_urls or []),
                    media_types=list(event.media_types or []),
                    message_type=event.message_type,
                )
                if has_image and list(event.media_urls or []):
                    if await self._as_try_image_analyze_vision_reply(
                        text=str(event.text or ""),
                        thread_id=tid,
                        thread_type=thread_type,
                        media_urls=list(event.media_urls or []),
                        has_image_attachment=True,
                    ):
                        return
                await self.handle_message(event)
                await self._as_autosend_late_files(tid, thread_type)
                await self._as_compound_wait_part(tid)

            try:
                await asyncio.wait_for(_run_turn(), timeout=turn_timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "Zalo: queue turn timeout thread=%s after %.0fs — release for next message",
                    tid,
                    turn_timeout,
                )
                # Unblock compound waiters / outbound paths that key off delivery.
                try:
                    self._as_compound_mark_delivered(tid)
                except Exception:
                    pass
                msg = self._as_ux_line(
                    "ZALO_QUEUE_TURN_TIMEOUT_MSG",
                    ("queue", "turn_timeout"),
                    "Xin lỗi, tin trước xử lý quá lâu (hơn 15 phút) nên mình dừng lại. Bạn gửi tin tiếp theo nhé.",
                )
                try:
                    await self._as_gate_announce(tid, thread_type, msg)
                except Exception:
                    pass
        except Exception:
            logger.exception("Zalo: queued part failed thread=%s", tid)
        finally:
            # Always release answering + hold so the next FIFO item can run.
            self._as_compound_end(tid)
            self._as_compound_after.pop(tid, None)
            if parts_after <= 0:
                self._as_compound_seq_done(tid)
                await self._as_compound_maybe_final_ack(tid)

    async def _as_dispatch_event(self, event, text: str) -> None:
        """Fail-open path: split + sequential handle without Valkey queue."""
        try:
            from .multi_request import split_compound_requests, wrap_compound_part
        except ImportError:
            split_compound_requests = lambda t: [t]  # type: ignore[misc, assignment]
            wrap_compound_part = lambda i, n, b: b  # type: ignore[misc, assignment]
        parts = split_compound_requests(text)
        if len(parts) <= 1:
            await self.handle_message(event)
            return
        logger.info("Zalo: compound message split into %d parts", len(parts))
        logger.info(f"[zalo] compound split n={len(parts)} via dispatch")
        tid = str(getattr(getattr(event, "source", None), "chat_id", "") or "")
        tt = str(getattr(getattr(event, "source", None), "chat_type", None) or "dm")
        zalo_tt = "group" if tt == "group" else "user"
        self._as_compound_begin(tid)
        try:
            for idx, part in enumerate(parts):
                parts_after = len(parts) - idx - 1
                self._as_compound_set_after(tid, parts_after, zalo_tt)
                if idx > 0:
                    await self._as_compound_wait_part(tid)
                part_event = MessageEvent(
                    text=wrap_compound_part(idx + 1, len(parts), part),
                    message_type=event.message_type,
                    source=event.source,
                    message_id=str(event.message_id or "") + f":part{idx + 1}",
                    raw_message=event.raw_message,
                    media_urls=event.media_urls if idx == 0 else [],
                    media_types=event.media_types if idx == 0 else [],
                    timestamp=datetime.now(),
                )
                await self.handle_message(part_event)
                await self._as_autosend_late_files(tid, zalo_tt)
            await self._as_compound_wait_part(tid)
        finally:
            self._as_compound_after.pop(tid, None)
            self._as_compound_seq_done(tid)
            await self._as_compound_maybe_final_ack(tid)
            self._as_compound_end(tid)


    def _as_secret_probe_text(self, text: str) -> bool:  # ASSISTANT_SECRET_PROBE_v1
        try:
            from secret_probe import is_blocked
        except ImportError:
            from .secret_probe import is_blocked  # type: ignore
        return bool(is_blocked(text or "", direction="input"))

    def _as_is_zalo_admin(self, sender_id) -> bool:  # ASSISTANT_SECRET_PROBE_v1
        import os
        uid = str(sender_id or "").strip()
        if not uid:
            return False
        return uid in self._zalo_admin_uids()

    def _zalo_admin_uids(self) -> set:  # sole admin: file (1 uid) ∪ env bootstrap
        import os
        out = set()
        path = os.getenv("ZALO_ADMIN_USERS_FILE", "/opt/data/zalo_admin_users.txt")
        try:
            if path and os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    for line in fh:
                        t = line.strip()
                        if not t or t.startswith("#"):
                            continue
                        if "|" in t:
                            t = t.split("|", 1)[0].strip()
                        if t:
                            out.add(t)
                            break  # exactly one
        except Exception:
            pass
        if out:
            return out
        raw = os.getenv("ZALO_ADMIN_USERS") or ""
        for x in raw.split(","):
            if x.strip():
                out.add(x.strip())
                break
        return out

    def _as_secret_probe_alias(self, m, sender_id) -> str:  # ASSISTANT_SECRET_PROBE_v4
        """Display name from inbound payload, then zalo_allowed_users.txt (uid | name)."""
        import os
        from pathlib import Path
        name = ""
        lookup = getattr(self, "_zalo_admin_sender_name", None)
        if callable(lookup) and isinstance(m, dict):
            try:
                name = str(lookup(m) or "").strip()
            except Exception:
                name = ""
        if not name and isinstance(m, dict):
            for key in ("sender_name", "senderName", "dName", "displayName", "zaloName"):
                v = m.get(key)
                if isinstance(v, str) and v.strip():
                    name = v.strip()
                    break
            if not name:
                sender = m.get("sender") or m.get("from") or {}
                if isinstance(sender, dict):
                    for key in ("displayName", "dName", "zaloName", "name"):
                        v = sender.get(key)
                        if isinstance(v, str) and v.strip():
                            name = v.strip()
                            break
        sid = str(sender_id or "").strip()
        if not name and sid:
            paths = (
                Path(os.getenv("ZALO_ALLOWED_USERS_FILE") or "/opt/data/zalo_allowed_users.txt"),
                Path("/data/hermes/zalo_allowed_users.txt"),
            )
            for path in paths:
                try:
                    if not path.is_file():
                        continue
                    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                        raw = line.strip()
                        if not raw or raw.startswith("#"):
                            continue
                        uid, alias = (raw.split("|", 1) + [""])[:2]
                        if uid.strip() == sid:
                            name = alias.strip()
                            break
                    if name:
                        break
                except Exception:
                    continue
        return name

    def _as_secret_probe_envelope(self, m, text=None) -> str:
        """Outer text + inbound/quoted file titles for probe (tag/quote/file)."""
        parts: list[str] = []
        outer = "" if text is None else str(text)
        if isinstance(m, dict) and not str(outer).strip():
            outer = str(m.get("text") or m.get("content") or m.get("message") or m.get("msg") or "")
        if str(outer).strip():
            parts.append(str(outer).strip())
        if isinstance(m, dict):
            media = m.get("media") if isinstance(m.get("media"), dict) else None
            if media:
                for key in ("fileName", "filename", "name", "title"):
                    fn = str(media.get(key) or "").strip()
                    if fn:
                        parts.append(fn)
                        break
                cap = str(media.get("caption") or media.get("description") or "").strip()
                if cap:
                    parts.append(cap)
            raw_q = m.get("quoted") if isinstance(m.get("quoted"), dict) else m.get("quote")
            if isinstance(raw_q, dict):
                snip = quoted_context_snip(raw_q)
                if snip:
                    parts.append(snip)
                qmedia = extract_media_from_quote(raw_q)
                if isinstance(qmedia, dict):
                    fn = str(qmedia.get("fileName") or "").strip()
                    if fn:
                        parts.append(fn)
        # de-dupe while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for p in parts:
            key = p.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        return "\n".join(out)

    def _as_learn_skip_mark(self, thread_id, sender_id) -> None:
        """Remember this turn must not stage knowledge-learn (secret probe hit)."""
        if not hasattr(self, "_as_learn_skip"):
            self._as_learn_skip = {}
        tid = str(thread_id or "").strip()
        sid = str(sender_id or "").strip()
        if tid:
            self._as_learn_skip[f"{tid}:{sid}"] = __import__("time").time()

    def _as_learn_skip_hit(self, thread_id, sender_id) -> bool:
        store = getattr(self, "_as_learn_skip", None) or {}
        key = f"{str(thread_id or '').strip()}:{str(sender_id or '').strip()}"
        ts = float(store.get(key) or 0)
        if ts <= 0:
            return False
        # Same inbound burst (file pipeline is async after AV).
        if __import__("time").time() - ts > 180:
            try:
                del store[key]
            except Exception:
                pass
            return False
        return True

    def _as_classify_secret_refuse(self, blob: str) -> bool:
        """True when classify owns a secret/env refuse (no keyword dictionaries)."""
        return bool(self._as_classify_refuse_body(blob))

    def _as_classify_refuse_body(self, blob: str) -> str:
        """LLM refuse line from classify instructions (user language). Empty if not refuse."""
        text = str(blob or "").strip()
        if not text:
            return ""
        try:
            try:
                from .classify_client import classify_text, plan_is_host_direct_reply
            except ImportError:
                from classify_client import classify_text, plan_is_host_direct_reply  # type: ignore
            plan = classify_text(text)
            if not plan_is_host_direct_reply(plan):
                return ""
            body = str(plan.get("message") or "").strip()
            if not body:
                body = "\n".join(
                    str(x).strip()
                    for x in (plan.get("instructions") or [])
                    if str(x).strip()
                )
            return body
        except Exception:
            return ""

    def _as_secret_refuse_line(self, blob: str) -> str:
        """Prefer classify LLM refuse; ux.json locale map only as fallback."""
        llm = self._as_classify_refuse_body(blob)
        if llm:
            return llm
        return self._as_ux_line(
            "ZALO_SECRET_PROBE_REFUSE",
            ("secret_probe", "refuse"),
            "Cannot provide secrets or confidential documents.",
            user_text=blob,
        )

    def _as_classify_allows_knowledge_learn(
        self, user_text: str, file_name: str, excerpt: str
    ) -> bool:
        """True only when classify says knowledge-learn for this attachment turn.

        Bare/blank files and LLM-risk whitepapers must not open Knowledge pending.
        Soft secret/env asks are already refuse; this gate is for learn staging.
        """
        ask = self._as_user_secret_ask_blob(
            user_text, {"fileName": file_name, "caption": user_text}
        )
        if not ask:
            return False
        blob = ask
        body = self._as_short_secret_ask_body(excerpt or "")
        if body:
            blob = f"{ask}\n[Attachment excerpt — {file_name}]\n{body}"
        else:
            blob = f"{ask}\n[Attachment — {file_name}]"
        try:
            try:
                from .classify_client import classify_text, plan_is_host_direct_reply
            except ImportError:
                from classify_client import classify_text, plan_is_host_direct_reply  # type: ignore
            plan = classify_text(blob)
            if plan_is_host_direct_reply(plan):
                return False
            hint = str(plan.get("task_hint") or "").strip().lower()
            skill = str(plan.get("skill") or "").strip().lower()
            action = str(plan.get("skill_action") or "").strip().lower()
            if hint == "knowledge" or skill == "knowledge":
                return True
            if action in {"learn", "approve", "ingest", "knowledge_learn", "save_knowledge"}:
                return True
            return False
        except Exception:
            return False

    def _as_user_secret_ask_blob(self, user_text: str = "", media: dict | None = None) -> str:
        """User-facing secret-ask text only. Drop Zalo wire JSON and filename-only.

        Zalo often puts a fileExt JSON blob in message text for attachments. That is
        not a user ask — classifying it caused blank/docs to get secret refuse.
        """
        media = media if isinstance(media, dict) else {}
        file_name = str(media.get("fileName") or media.get("filename") or "").strip()
        office_ext = (
            ".xlsx",
            ".xls",
            ".docx",
            ".doc",
            ".pdf",
            ".txt",
            ".csv",
            ".md",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        )
        parts: list[str] = []
        for raw in (
            str(user_text or "").strip(),
            str(media.get("caption") or media.get("description") or "").strip(),
        ):
            if not raw:
                continue
            # Zalo attachment wire payload (not a caption / ask).
            if raw.startswith("{") and ("fileExt" in raw or "fileSize" in raw or "checksum" in raw):
                continue
            if file_name and raw == file_name:
                continue
            if file_name and raw.strip("`") == file_name:
                continue
            tokens = raw.split()
            if len(tokens) == 1 and tokens[0].lower().endswith(office_ext):
                continue
            parts.append(raw)
        # de-dupe
        seen: set[str] = set()
        out: list[str] = []
        for p in parts:
            k = p.casefold()
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
        return "\n".join(out)

    def _as_meaningful_learn_text(self, text: str) -> bool:
        """True when extract has real content worth knowledge-learn staging."""
        body = str(text or "").strip()
        if not body:
            return False
        # Whitespace-only / empty-looking extracts (blank docs) must not stage learn.
        compact = "".join(body.split())
        return bool(compact)

    def _as_short_secret_ask_body(self, text: str) -> str:
        """Only short extracted bodies can be user-style secret asks.

        Long security whitepapers (injection examples, LLM risk notes) are document
        content — not a human secret probe. Keep threshold well above 1.txt/2.txt.
        """
        body = str(text or "").strip()
        if not body:
            return ""
        if len(body) > 600:
            return ""
        return body

    async def _as_secret_probe_drop(self, m, sender_id, thread_id, thread_type, text=None) -> bool:  # ASSISTANT_SECRET_PROBE_v7
        """Optional literal marker gate. Soft secret/env intent is classify-owned.

        When policy is classify-owned (empty markers), this is a no-op and the
        host classify / learn-skip path handles refuse. Still marks learn-skip
        if a residual literal marker hits.
        """
        import json
        import os
        import urllib.request
        from datetime import datetime
        from zoneinfo import ZoneInfo

        orig = self._as_secret_probe_envelope(m, text)
        if not self._as_secret_probe_text(orig):
            return False
        self._as_learn_skip_mark(thread_id, sender_id)
        sid = str(sender_id or "").strip() or "unknown"
        alias = self._as_secret_probe_alias(m, sid)
        who = f"user_id: {sid} ({alias})" if alias else f"user_id: {sid}"
        tz = ZoneInfo(os.getenv("TZ") or "Asia/Ho_Chi_Minh")
        stamp = datetime.now(tz).strftime("%H:%M %d/%m/%Y")
        notify = (os.getenv("NOTIFY_URL") or "http://notify:8092").rstrip("/")
        refuse = self._as_secret_refuse_line(orig)
        try:
            nbody = json.dumps(
                {
                    "title": "Confidential probe",
                    "body": f"{stamp}\n{who}",
                    "severity": "warning",
                    "channels": ["zalo"],
                    "kind": "security",
                }
            ).encode("utf-8")
            nreq = urllib.request.Request(
                notify + "/v1/notify",
                data=nbody,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(nreq, timeout=4.0).read()
        except Exception:
            logger.warning("Zalo: secret-probe notify failed")
        try:
            await self.send(
                chat_id=str(thread_id),
                content=refuse,
                metadata={
                    "thread_type": "group" if thread_type == "group" else "user",
                },
            )
        except Exception:
            pass
        logger.warning("Zalo: secret-probe deny sender=%s thread=%s", sid, thread_id)
        logger.warning("[zalo] secret-probe deny sender=%s thread=%s", sid, thread_id)
        return True


































    def _as_is_knowledge_cite_ask(self, text: str, plan=None) -> bool:  # ASSISTANT_KNOWLEDGE_CITE_v7
        try:
            from .knowledge_cite import plan_is_knowledge
            from .classify_client import classify_text
        except ImportError:
            from knowledge_cite import plan_is_knowledge  # type: ignore
            from classify_client import classify_text  # type: ignore
        if not isinstance(plan, dict):
            plan = classify_text(text or "")
        return plan_is_knowledge(plan)

    def _as_cite_topic(self, text: str, plan=None) -> str:
        try:
            from .knowledge_cite import cite_query
            from .classify_client import classify_text
        except ImportError:
            from knowledge_cite import cite_query  # type: ignore
            from classify_client import classify_text  # type: ignore
        if not isinstance(plan, dict):
            plan = classify_text(text or "")
        return cite_query(plan)

    def _as_knowledge_trim(self, content: str) -> str:  # ASSISTANT_KNOWLEDGE_CITE_v7
        return content or ""

    async def _as_cite_send(self, thread_id, thread_type, msg: str) -> None:
        await self.send(
            chat_id=str(thread_id),
            content=msg,
            metadata={
                "thread_type": "group" if thread_type == "group" else "user",
                "as_skip_inflight": True,
                "as_skip_dest": True,
                "as_skip_autosend": True,
                "as_skip_quote": True,
            },
        )

    async def _as_knowledge_cite_reply(self, m, sender_id, thread_id, thread_type, plan=None) -> bool:  # ASSISTANT_KNOWLEDGE_CITE_v7
        """True = handled (catalog/cite from classify task_hint=knowledge)."""
        text = (m.get("text") if isinstance(m, dict) else "") or ""
        try:
            from .classify_client import classify_text
            from .knowledge_cite import cite_query, plan_is_knowledge
        except ImportError:
            from classify_client import classify_text  # type: ignore
            from knowledge_cite import cite_query, plan_is_knowledge  # type: ignore
        if not isinstance(plan, dict):
            plan = classify_text(text)
        if not plan_is_knowledge(plan):
            return False
        import json
        import os
        import urllib.parse
        import urllib.request
        url = (os.getenv("INGEST_URL") or "http://ingest:8099").rstrip("/")
        topic = cite_query(plan)
        limit = (os.getenv("LEARN_LIST_LIMIT") or "5").strip() or "5"
        qs = "limit=" + limit
        if topic:
            qs += "&q=" + urllib.parse.quote(topic, safe="")
        data = {}
        last_err = None
        try:
            import time as _time
            for _try in (1, 2, 3):
                try:
                    req = urllib.request.Request(url + "/v1/learn/list?" + qs)
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        data = json.loads(resp.read().decode("utf-8") or "{}")
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    _time.sleep(_try)
            if last_err is not None:
                raise last_err
        except Exception as exc:
            logger.warning("Zalo: knowledge cite list failed %s", exc)
            try:
                await self._as_cite_send(
                    thread_id,
                    thread_type,
                    "Không lấy được danh sách kiến thức. Thử lại sau.",
                )
            except Exception:
                pass
            return True
        docs = data.get("documents") or []
        total = int(data.get("total") or data.get("count") or len(docs))
        if not docs:
            msg = (
                ("Không thấy kiến thức khớp «" + topic + "».")
                if topic
                else "Chưa có kiến thức đã học."
            )
        else:
            shown = str(len(docs))
            tot = str(total)
            if topic:
                lines = ["Khớp «" + topic + "» — " + shown + "/" + tot + " file:"]
            else:
                lines = ["Kiến thức đã học — " + shown + "/" + tot + " file:"]
            for d in docs:
                if not isinstance(d, dict):
                    continue
                title = str(d.get("title") or "").strip()
                low = title.lower()
                if (
                    not title
                    or "inbound/" in low
                    or "/opt/" in low
                    or "/data/" in low
                    or title.startswith("/")
                    or "\\" in title
                    or low.endswith(".pdf")
                ):
                    title = "Tài liệu"
                lines.append("• " + title)
            extra = total - len(docs)
            lines.append("Còn " + str(max(0, extra)) + " file.")
            lines.append("Hỏi một mục cụ thể để xem đoạn.")
            msg = "\n".join(lines)[:800]
        logger.info("Zalo: knowledge cite intercept docs=%s thread=%s", len(docs), thread_id)
        try:
            await self._as_cite_send(thread_id, thread_type, msg)
        except Exception as exc:
            logger.warning("Zalo: knowledge cite send failed %s", exc)
        return True

    async def _on_inbound_message(self, m: Dict[str, Any]) -> None:
        if not isinstance(m, dict):
            logger.warning("Zalo: inbound message is not a dict (%s)", type(m).__name__)
            return
        if not self._message_handler:
            return
        if m.get("isSelf"):
            return

        thread_id = str(m.get("threadId") or "")
        thread_type = m.get("threadType") or "user"  # "user" | "group"
        sender_id = str(m.get("senderId") or "")
        sender_name = m.get("senderName") or ""
        text = m.get("text") or ""
        chat_type = "group" if thread_type == "group" else "dm"

        # Remember type for outbound routing.
        self._thread_types[thread_id] = "group" if thread_type == "group" else "user"
        # New user text must not flush a leftover image from a previous (stuck) turn.
        if not (m.get("scheduleFire") or m.get("schedule_fire")):
            try:
                self._as_cancel_late_autosend(str(thread_id))
            except Exception:
                pass
            try:
                # Prior media delivery must not mute later schedule ack/fire or chat.
                self._as_clear_job_file_sent(str(thread_id))
            except Exception:
                pass
        self._as_autosend_remember_turn(thread_id, thread_type)  # ASSISTANT_AUTOSEND_v3
        try:
            from .channels_client import remember_inbound
        except ImportError:
            from channels_client import remember_inbound  # type: ignore
        try:
            remember_inbound(
                thread_id=thread_id,
                thread_type=thread_type,
                sender_id=sender_id,
                sender_name=str(sender_name or ""),
            )
        except Exception:
            pass







        # In-Zalo admin (!zalo …) — before allowlist so new groups can !zalo allow.  (ASSISTANT_ZALO_ADMIN_v8)
        _admin_text = text or ""
        if chat_type == "group" and self.group_mode == "mention":
            _addr = self._is_addressed(m, text)
            if _addr is not None:
                _admin_text = _addr
        # Always consume '!zalo' — never let the LLM answer admin commands.
        if self._zalo_admin_extract_cmd(_admin_text) or self._zalo_admin_extract_cmd(text or ""):
            _cmd_src = self._zalo_admin_extract_cmd(_admin_text) or self._zalo_admin_extract_cmd(text or "")
            await self._try_zalo_admin_command(m, _cmd_src, sender_id, thread_id, thread_type)
            return

        # ── Access control (Telegram-style) ──────────────────────────────────
        # Optionally log ids so the operator can build allowlists.
        if self.log_ids:
            logger.info(
                "Zalo inbound: uid=%s name=%r threadId=%s type=%s",
                sender_id, sender_name, thread_id, chat_type,
            )















































































































        # ASSISTANT_ACCESS_v9 — DMs bypass thread allowlist; admins always; open ignores user env list
        _eff_threads = self._allowed_threads_effective()
        if thread_type == "group" and _eff_threads and thread_id not in _eff_threads:
            logger.debug("Zalo: ignoring message in non-allowed thread %s", thread_id)
            return
        _admins = self._zalo_admin_uids()
        if sender_id not in _admins:
            if self._users_strict_mode():
                _eff_users = self._allowed_users_effective()
                if _eff_users and sender_id not in _eff_users:
                    logger.debug("Zalo: ignoring non-approved user %s", sender_id)
                    return
            # open mode: no sender allowlist (group gate above is enough)

        # ASSISTANT_MENTION_GATE_v1 — MUST run before rate / already-answering / secret-probe.
        # Otherwise normal group chat (no @bot) gets "Bot đang trả lời…" / "gửi hơi nhanh".
        # Schedule fires inject into groups without @mention — must not be dropped here.
        schedule_fire = bool(m.get("scheduleFire") or m.get("schedule_fire"))
        media = m.get("media") if isinstance(m.get("media"), dict) else None
        # Quote-reply to photo/file: resolve media before mention gate so group
        # buffered-media and attachment paths see the quoted image URL.
        media, m = merge_inbound_quote_media(m, media)
        pending_key = f"{thread_id}:{sender_id}"
        if chat_type == "group" and not schedule_fire:
            if self.group_mode == "off":
                return
            if self.group_mode == "mention":
                addressed = self._is_addressed(m, text)
                if not addressed:
                    if media and media.get("url"):
                        self._pending_media[pending_key] = {
                            "media": media,
                            "text": text or "",
                            "ts": datetime.now().timestamp(),
                        }
                        logger.info(
                            "Zalo: buffered media for %s (%s)",
                            pending_key,
                            media.get("fileName") or media.get("kind"),
                        )
                    return
                text = addressed
                if not (media and media.get("url")):
                    pending = self._pending_media.pop(pending_key, None)
                    if pending and datetime.now().timestamp() - float(pending.get("ts") or 0) < 90:
                        media = pending.get("media")
                        m = dict(m)
                        m["media"] = media
                        hint = pending.get("text") or ""
                        if hint and hint not in (text or ""):
                            text = f"{text}\n{hint}".strip()
                        logger.info("Zalo: attached buffered media for %s", pending_key)
            # group_mode == "all" → respond to everything (subject to A+B above)
        elif schedule_fire and chat_type == "group":
            logger.warning(
                "Zalo: scheduleFire bypass mention-gate thread=%s",
                thread_id,
            )

        # Verbatim schedule delivery: send fire_text as-is (no Hermes paraphrase).
        if schedule_fire and await self._as_schedule_fire_verbatim(
            m, text=text, thread_id=str(thread_id), thread_type=str(thread_type)
        ):
            return

        # Host scenic/media shortcuts on bare text — before inflight drop and attachment pipeline.
        bare_early = (text or "").strip()
        if (
            bare_early
            and not schedule_fire
            and not (isinstance(media, dict) and media.get("url"))
            and "[Attachment text —" not in bare_early
            and "[Attached file:" not in bare_early
        ):
            if await self._as_run_host_media_shortcut(
                user_text=bare_early,
                thread_id=str(thread_id),
                thread_type=str(thread_type),
                bare_text=bare_early,
            ):
                return

        # ASSISTANT_RATE_LIMIT_v4 — Valkey 1 / 10s; queue overflow instead of drop when enabled
        rate_over, rate_notify = self._zalo_rate_check(sender_id, thread_id)
        queue_on = self._as_inbound_queue_enabled()
        if (not schedule_fire) and (not queue_on) and rate_over:
            logger.info(
                "Zalo: rate-limit drop sender=%s thread=%s type=%s via valkey",
                sender_id, thread_id, thread_type,
            )
            if rate_notify:
                msg = self._as_ux_line(
                    "ZALO_RATE_LIMIT_MSG",
                    ("queue", "rate_limited"),
                    "Bạn gửi hơi nhanh — tin này đã vào hàng chờ, mình trả lời lần lượt.",
                )
                try:
                    await self._as_gate_announce(thread_id, thread_type, msg)
                except Exception as e:
                    logger.warning("Zalo: rate-limit announce failed: %s", type(e).__name__)
            return
        # ASSISTANT_SECRET_PROBE_v5 — short refuse + notify admin; no LLM
        _sp = getattr(self, "_as_secret_probe_drop", None)
        if _sp and await _sp(m, sender_id, thread_id, thread_type, text):
            return

        # ASSISTANT_INFLIGHT_v6 — already answering; Valkey queue serializes when enabled
        # Schedule fires must not be dropped by thread lock (user may still be chatting).
        if (not schedule_fire) and (not queue_on) and await self._as_inflight_drop(sender_id, thread_id, thread_type):
            return

        if not (isinstance(media, dict) and media.get("url")):
            media, m = merge_inbound_quote_media(m, media)
            if isinstance(media, dict) and media.get("url"):
                logger.info(
                    "Zalo: media from quoted %s (%s)",
                    normalize_zalo_msg_type(
                        (m.get("quote") or m.get("quoted") or {}).get("msgType")
                        or (m.get("quote") or m.get("quoted") or {}).get("cliMsgType")
                    ),
                    media.get("fileName"),
                )

        # Cache inbound as SendMessageQuote so outbound replies quote the @mention.  (ASSISTANT_REPLY_QUOTE)
        if not hasattr(self, "_pending_reply_quote"):
            self._pending_reply_quote = {}
        q = m.get("quote") if isinstance(m.get("quote"), dict) else None
        if not q or not (q.get("msgId") is not None or q.get("cliMsgId") is not None):
            mid = m.get("messageId") or m.get("msgId")
            if mid:
                q = {
                    "content": m.get("text") or "",
                    "msgType": m.get("msgType") or "webchat",
                    "uidFrom": m.get("senderId") or "",
                    "msgId": mid,
                    "cliMsgId": m.get("cliMsgId") or mid,
                    "ts": m.get("ts") or "",
                }
        if isinstance(q, dict) and (q.get("msgId") is not None or q.get("cliMsgId") is not None):
            _qmt = str(q.get("msgType") or q.get("cliMsgType") or "")  # ASSISTANT_SEND_RETRY_v1
            if _qmt in {"46", "share.file", "31", "chat.voice", "44", "chat.video.msg"} or str(_qmt).startswith("share."):
                self._pending_reply_quote.pop(str(thread_id), None)
            else:
                self._pending_reply_quote[thread_id] = q

        source = self.build_source(
            chat_id=thread_id,
            chat_name=sender_name if chat_type == "dm" else thread_id,
            chat_type=chat_type,
            user_id=sender_id,
            user_name=sender_name,
        )

        # Download inbound media so the agent can see/hear it.
        media_urls: List[str] = []
        media_types: List[str] = []
        message_type = MessageType.TEXT
        if isinstance(media, dict) and media.get("url"):
            logger.info(  # ASSISTANT_FILE_PROMPT_v3
                "Zalo: inbound media %s url=%s",
                media.get("fileName") or media.get("kind") or "file",
                str(media.get("url") or "")[:96],
            )
            local_path, mtype = await self._download_media(media)
            if local_path:
                # Replica cache is invisible to OCR/ingest/dispatcher — stage onto
                # the shared media volume before workers run (see stage_shared_media).
                staged = stage_shared_media(
                    local_path,
                    str(media.get("fileName") or ""),
                    thread_id=str(thread_id or ""),
                )
                if staged:
                    self._as_flow(
                        "attach_staged",
                        file=media.get("fileName") or "",
                        from_path=str(local_path)[:120],
                        to_path=str(staged)[:120],
                    )
                    local_path = staged
                elif mtype == MessageType.PHOTO or str(media.get("kind") or "").lower() in {
                    "image",
                    "photo",
                    "gif",
                }:
                    self._as_flow(
                        "attach_stage_miss",
                        file=media.get("fileName") or "",
                        from_path=str(local_path)[:120],
                    )
                media_urls.append(local_path)
                media_types.append(media.get("mime") or "")
                message_type = mtype
        # ASSISTANT_FILE_PROMPT_v5 — read the attachment while AV scans it, then
        # hand the agent real text instead of asking the user to describe/paste.
        extract_task = None
        attach_name = ""
        attach_is_image = False
        attach_bare = False
        if isinstance(media, dict) and media_urls:
            attach_name = str(media.get("fileName") or "file")
            raw = (text or "").strip()
            tokens = raw.split()
            attach_bare = (
                (not raw)
                or raw == attach_name
                or raw.strip("`") == attach_name
                or (raw.startswith("{") and "fileExt" in raw)
                or (
                    len(tokens) == 1
                    and tokens[0].lower().endswith(
                        (
                            ".xlsx",
                            ".xls",
                            ".docx",
                            ".doc",
                            ".pdf",
                            ".txt",
                            ".csv",
                            ".zip",
                            ".7z",
                            ".rar",
                            ".tar",
                            ".tgz",
                        )
                    )
                )
            )
            kind_l = str(media.get("kind") or "").lower()
            mime_l = str(media.get("mime") or "").lower()
            attach_is_image = (
                message_type == MessageType.PHOTO
                or kind_l in {"image", "photo", "gif", "sticker"}
                or mime_l.startswith("image/")
                or attach_name.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
                )
            )
            # Captioned images: image-analyze host reply via OCR vision-ocr combo.
            # Bare images still run _as_attachment_text (same vision-ocr worker).
            if attach_is_image and not attach_bare:
                extract_task = None
            else:
                extract_task = asyncio.create_task(
                    self._as_attachment_text(
                        media_urls[0],
                        attach_name,
                        caption=str(text or ""),
                    )
                )
        elif isinstance(media, dict) and media.get("url") and not media_urls:
            logger.warning("Zalo: media download empty %s", media.get("fileName") or "file")
            try:
                await self.send(
                    chat_id=str(thread_id),
                    content="Không lấy được file — gửi lại giúp mình.",
                    metadata={
                        "thread_type": "group" if thread_type == "group" else "user",
                        "as_skip_inflight": True,
                    },
                )
            except Exception:
                pass
            return


        # ASSISTANT_FILE_PIPELINE_v6 — AV before Hermes
        if media_urls:
            _gate = getattr(self, "_as_av_gate", None)
            if _gate:
                _blocked = await _gate(
                    thread_id,
                    sender_id,
                    media_urls[0],
                    media if isinstance(media, dict) else {},
                    user_text=str(text or ""),
                )
                if _blocked:
                    if extract_task is not None:
                        extract_task.cancel()
                    return

        if extract_task is not None:
            try:
                excerpt = await extract_task
            except asyncio.CancelledError:
                excerpt = ""
            except Exception as e:
                logger.warning("Zalo: attachment read failed: %s", type(e).__name__)
                excerpt = ""
            attach_kind = attachment_kind(attach_name)
            if excerpt in {"__AS_ARCHIVE_PASSWORD__", "__AS_ARCHIVE_BAD_PASSWORD__"}:
                bad = excerpt == "__AS_ARCHIVE_BAD_PASSWORD__"
                ack = archive_password_ack_message(attach_name, bad=bad)
                self._as_flow(
                    "attach_archive_password",
                    file=attach_name,
                    thread_id=thread_id,
                    bad=bad,
                )
                try:
                    await self.send(
                        chat_id=str(thread_id),
                        content=ack,
                        metadata={
                            "thread_type": "group" if thread_type == "group" else "user",
                            "as_skip_autosend": True,
                            "as_skip_dest": True,
                            "skip_outbound_filter": True,
                        },
                    )
                except Exception as e:
                    logger.warning("Zalo: archive password ack failed: %s", type(e).__name__)
                try:
                    self._as_inflight_done(str(thread_id), {})
                except Exception:
                    pass
                try:
                    self._as_queue_kick(str(thread_id))
                except Exception:
                    pass
                return
            # Office/text/archive SoT is ingest/OCR workers — never pass binaries to Hermes
            # (local docx/terminal/zipfile forensics). Whitespace-only = blank.
            excerpt_meaningful = self._as_meaningful_learn_text(excerpt or "")
            if attach_is_image and excerpt_meaningful:
                cleaned = ocr_excerpt_for_ack(excerpt or "")
                if not cleaned:
                    excerpt_meaningful = False
                    excerpt_for_prompt = ""
                else:
                    excerpt_for_prompt = cleaned
            else:
                excerpt_for_prompt = excerpt if excerpt_meaningful else ""
            # vision is handled by the OCR worker (OCR_MODEL=vision-ocr),
            # so a second host-side image hop is redundant. Empty extract falls
            # through to the neutral attachment prompt for Hermes classify.
            if excerpt_meaningful:
                self._as_attachment_remember(str(thread_id), attach_name, excerpt)
            else:
                # Still remember the filename so follow-ups ("tìm lời bài hát")
                # can web-search without asking which song when the title is clear.
                self._as_attachment_remember(
                    str(thread_id),
                    attach_name,
                    f"[Attached file: {attach_name}]",
                )
            if attach_kind in {"office", "text", "archive"}:
                # Worker extract already ran; strip paths so Hermes cannot open the package
                # (local docx/terminal/pypdf forensics on pdf/images).
                media_urls = []
                media_types = []
                message_type = MessageType.TEXT
            elif attach_is_image and not (attach_bare and excerpt_meaningful):
                # Captioned images or bare images still empty after vision → classify/Hermes.
                pass
            elif attach_kind == "ocr" and not attach_is_image:
                media_urls = []
                media_types = []
                message_type = MessageType.TEXT
            if not excerpt_meaningful and attach_kind in {
                "office",
                "text",
                "archive",
                "ocr",
            }:
                # Blank / empty extract: never stage Knowledge pending.
                self._as_learn_skip_mark(thread_id, sender_id)
            if attach_bare:
                text = self._as_attachment_prompt(
                    attach_name,
                    excerpt_for_prompt,
                    is_image=attach_is_image,
                    local_path="",
                )
            elif excerpt_for_prompt:
                text = (
                    f"{text}\n\n[Attachment text — {attach_name}]\n"
                    f"{excerpt_for_prompt[:ATTACHMENT_PROMPT_CHARS]}"
                )
            logger.info(
                "Zalo: attachment prompt %s image=%s bare=%s chars=%s kind=%s",
                attach_name,
                attach_is_image,
                attach_bare,
                len(excerpt_for_prompt),
                attach_kind,
            )
            # Bare attachment OR blank office/text: deterministic worker extract ack.
            # Images: host-ack only when bare AND we have OCR/vision text; else classify path.
            # Images always continue to Hermes multimodal — never host-ack OCR noise as final reply.
            if attach_is_image:
                host_ack = False
            else:
                host_ack = attach_bare or attach_kind in {
                    "archive",
                    "office",
                    "text",
                    "ocr",
                }
            if host_ack:
                # Short standalone text/OCR body that is itself a secret/env ask → refuse.
                # Archives/office: NEVER classify member/sheet bodies as the user ask —
                # mixed packs and multi-sheet workbooks with an embedded soft probe must
                # still host-ack extract; cell/member text is untrusted DATA. Omni classify
                # under rate-limit also blocked the async loop and left turns silent.
                # Blank/empty extracts continue with the normal extract ack (no learn).
                if attach_kind not in {"archive", "office"}:
                    body = self._as_short_secret_ask_body(excerpt or "")
                    refuse_body = (
                        await asyncio.to_thread(self._as_classify_refuse_body, body)
                        if body
                        else ""
                    )
                    if body and (
                        self._as_secret_probe_text(body) or refuse_body
                    ):
                        self._as_learn_skip_mark(thread_id, sender_id)
                        self._as_flow(
                            "learn_skip",
                            reason="classify_secret_attachment_body",
                            thread_id=thread_id,
                            file=attach_name,
                        )
                        try:
                            refuse = refuse_body or self._as_secret_refuse_line(body[:500])
                            await self.send(
                                chat_id=str(thread_id),
                                content=refuse,
                                metadata={
                                    "thread_type": "group" if thread_type == "group" else "user",
                                    "as_skip_inflight": True,
                                    "skip_outbound_filter": True,
                                },
                            )
                        except Exception:
                            pass
                        try:
                            self._as_inflight_done(str(thread_id), {})
                        except Exception:
                            pass
                        try:
                            self._as_queue_kick(str(thread_id))
                        except Exception:
                            pass
                        return
                kind = attach_kind or attachment_kind(attach_name)
                ack = ""
                flow_stage = "attach_file_empty_ack"
                if attach_is_image:
                    ack = image_analyze_ack_message(excerpt_for_prompt or "")
                    if ack:
                        flow_stage = "attach_image_analyze_ack"
                    else:
                        host_ack = False
                else:
                    ack = file_extract_ack_message(
                        attach_name, excerpt_for_prompt or "", kind=kind
                    )
                    flow_stage = (
                        "attach_file_extract_ack"
                        if excerpt_meaningful
                        else "attach_file_empty_ack"
                    )
                if host_ack and ack:
                    self._as_flow(
                        flow_stage,
                        file=attach_name,
                        thread_id=thread_id,
                        kind=kind,
                        chars=len(excerpt_for_prompt or ""),
                    )
                    try:
                        await self.send(
                            chat_id=str(thread_id),
                            content=ack,
                            metadata={
                                "thread_type": "group" if thread_type == "group" else "user",
                                "as_skip_autosend": True,
                                "as_skip_dest": True,
                                "skip_outbound_filter": True,
                            },
                        )
                    except Exception as e:
                        logger.warning("Zalo: extract ack failed: %s", type(e).__name__)
                    try:
                        self._as_inflight_done(str(thread_id), {})
                    except Exception:
                        pass
                    try:
                        ev = self._as_part_delivered.get(str(thread_id))
                        if ev is not None:
                            ev.set()
                    except Exception:
                        pass
                    try:
                        self._as_queue_kick(str(thread_id))
                    except Exception:
                        pass
                    return
        user_text_before_attach = str(text or "").strip()
        if not media_urls and user_text_before_attach:
            text = self._as_attachment_followup(str(thread_id), text)

        # Quoted reply (DM + group): inject quoted text/title/media label so the
        # agent can read the old message the user replied to.
        try:
            raw_q = m.get("quoted") if isinstance(m.get("quoted"), dict) else None
            if not isinstance(raw_q, dict):
                raw_q = m.get("quote") if isinstance(m.get("quote"), dict) else {}
            qsnip = quoted_context_snip(raw_q)
            if isinstance(raw_q, dict) and raw_q and not qsnip:
                logger.info(
                    "Zalo: quote present but empty snip thread=%s keys=%s msgType=%s",
                    thread_id,
                    sorted(str(k) for k in raw_q.keys())[:12],
                    raw_q.get("msgType") or raw_q.get("cliMsgType") or "",
                )
            if qsnip and qsnip not in str(text or ""):
                base = str(text or "").strip()
                text = f"{base}\n\n[Quoted message]\n{qsnip}" if base else f"[Quoted message]\n{qsnip}"
                self._as_flow("quote_context", thread_id=thread_id, chars=len(qsnip))
        except Exception:
            pass

        # Office create only when classify says a single file job. Mixed image+file
        # and schedules must not be swallowed by Dispatcher phrase shortcuts.
        # Never treat prior attachment extracts as a create-file prompt.
        bare_text = str(text or "").strip()
        # Host-authored recall blocks are not create-file prompts — skip media shortcuts.
        has_recent_attach = "[Recent attachments" in bare_text

        # Workbook sheet follow-up: answer from remembered extract (no re-upload ask).
        if bare_text and not media_urls and has_recent_attach:
            try:
                fname, extract = self._as_attachment_recall(str(thread_id))
                if extract and (
                    "Workbook sheets:" in extract or "## Sheet" in extract
                ):
                    try:
                        from .classify_client import classify_text_async, plan_sheet_ref
                    except ImportError:
                        from classify_client import (  # type: ignore
                            classify_text_async,
                            plan_sheet_ref,
                        )
                    # Classify the user line only (not the injected extract) — save tokens.
                    sheet_plan = await classify_text_async(
                        user_text_before_attach or bare_text
                    )
                    ref = plan_sheet_ref(sheet_plan)
                    if not ref:
                        ins = sheet_plan.get("instructions") or []
                        blob = "\n".join(str(x) for x in ins) if isinstance(ins, list) else ""
                        ref = sheet_ref_from_text(blob)
                    if ref:
                        reply = workbook_sheet_reply(fname, extract, ref)
                        if reply:
                            self._as_flow(
                                "attach_sheet_followup",
                                thread_id=thread_id,
                                file=fname,
                                sheet_ref=ref,
                            )
                            try:
                                await self.send(
                                    chat_id=str(thread_id),
                                    content=reply,
                                    metadata={
                                        "thread_type": "group"
                                        if thread_type == "group"
                                        else "user",
                                        "as_skip_autosend": True,
                                        "as_skip_dest": True,
                                        "skip_outbound_filter": True,
                                    },
                                )
                            except Exception as e:
                                logger.warning(
                                    "Zalo: sheet followup send failed: %s",
                                    type(e).__name__,
                                )
                            else:
                                try:
                                    self._as_inflight_done(str(thread_id), {})
                                except Exception:
                                    pass
                                try:
                                    self._as_queue_kick(str(thread_id))
                                except Exception:
                                    pass
                                return
            except Exception as e:
                logger.warning("Zalo: sheet followup error: %s", type(e).__name__)

        # Media shortcuts classify the user's line only — attachment recall must not block scenic/weather paths.
        shortcut_user_text = (user_text_before_attach or bare_text).strip()
        if (
            shortcut_user_text
            and not media_urls
            and "[Attachment text —" not in bare_text
            and "[Attached file:" not in bare_text
        ):
            if await self._as_run_host_media_shortcut(
                user_text=shortcut_user_text,
                thread_id=str(thread_id),
                thread_type=str(thread_type),
                bare_text=bare_text,
            ):
                return

        # Valkey short-term memory (SESSION_URL) — survive Hermes recreate.
        try:
            from .session_memory import hydrate_user_text
        except ImportError:
            from session_memory import hydrate_user_text  # type: ignore
        try:
            if bare_text and not media_urls:
                self._as_last_user_text = getattr(self, "_as_last_user_text", {}) or {}
                self._as_last_user_text[str(thread_id)] = bare_text
                text = hydrate_user_text(str(thread_id), str(thread_type), bare_text)
        except Exception as e:
            logger.debug("Zalo: session hydrate skipped: %s", type(e).__name__)

        event = MessageEvent(
            text=text,
            message_type=message_type,
            source=source,
            message_id=str(m.get("messageId") or ""),
            raw_message=m,
            media_urls=media_urls,
            media_types=media_types,
            timestamp=datetime.now(),
        )
        # Before gateway turn: claim home so first-chat /sethome notice is skipped.
        self._maybe_auto_set_home(
            thread_id=str(thread_id),
            chat_type=str(chat_type),
            sender_id=str(sender_id or ""),
            sender_name=str(sender_name or ""),
        )
        if queue_on:
            mt_name = getattr(message_type, "name", None) or "TEXT"
            await self._as_enqueue_inbound(
                text=text,
                thread_id=str(thread_id),
                thread_type=str(thread_type),
                sender_id=str(sender_id or ""),
                sender_name=str(sender_name or ""),
                chat_type=str(chat_type),
                message_id=str(m.get("messageId") or ""),
                media_urls=media_urls,
                media_types=media_types,
                message_type=str(mt_name),
                rate_over=rate_over,
                rate_notify=rate_notify,
                event=event,
                schedule_fire=bool(m.get("scheduleFire") or m.get("schedule_fire")),
                has_image_attachment=bool(
                    media_urls
                    and (
                        message_type == MessageType.PHOTO
                        or attach_is_image
                    )
                ),
            )
            return
        await self._as_dispatch_event(event, text)


    async def _fetch_media_via_bridge(self, media: Dict[str, Any]) -> Optional[bytes]:  # ASSISTANT_MEDIA_PROXY_v1
        """Download Zalo CDN media through the host bridge (session cookies)."""
        import aiohttp

        url = (media or {}).get("url")
        if not url or not self.bridge_url:
            return None
        if not self._session or self._session.closed:  # ASSISTANT_FILE_PROMPT_v3
            logger.warning("Zalo: media-proxy session closed — reopening")
            try:
                import aiohttp as _aio
                self._session = _aio.ClientSession()
            except Exception as e:
                logger.warning("Zalo: media-proxy session reopen failed: %s", e)
                return None
        # Already a bridge proxy path/url — just GET bytes
        path = ""
        low = str(url)
        if "/media/" in low and (
            low.startswith(str(self.bridge_url).rstrip("/"))
            or low.startswith("/media/")
        ):
            path = low if low.startswith("/media/") else "/media/" + low.rsplit("/media/", 1)[-1]
        else:
            try:
                payload = {
                    "url": url,
                    "kind": media.get("kind") or "",
                    "fileName": media.get("fileName") or "",
                    "mime": media.get("mime") or "",
                    "key": media.get("key") or media.get("encryptKey") or "",
                }
                async with self._session.post(
                    f"{self.bridge_url.rstrip('/')}/media/fetch",
                    json=payload,
                    headers=self._headers(),
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.warning(
                            "Zalo: media-proxy fetch HTTP %s: %s",
                            resp.status,
                            (body or "")[:180],
                        )
                        return None
                    meta = await resp.json(content_type=None)
                mid = (meta or {}).get("id")
                path = (meta or {}).get("path") or (f"/media/{mid}" if mid else "")
                if not path:
                    return None
                if (meta or {}).get("magicOk") is False:
                    logger.warning(
                        "Zalo: media-proxy magicOk=false size=%s kind=%s",
                        (meta or {}).get("size"),
                        media.get("kind"),
                    )
            except Exception as e:
                logger.warning("Zalo: media-proxy fetch error: %s", e)
                return None
        try:
            async with self._session.get(
                f"{self.bridge_url.rstrip('/')}{path}",
                headers={k: v for k, v in self._headers().items() if k.lower() != "content-type"},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    logger.warning("Zalo: media-proxy GET %s → %s", path, resp.status)
                    return None
                data = await resp.read()
                logger.info(
                    "Zalo: media-proxy ok path=%s bytes=%d kind=%s",
                    path,
                    len(data),
                    media.get("kind"),
                )
                return data
        except Exception as e:
            logger.warning("Zalo: media-proxy GET error: %s", e)
            return None

    async def _download_media(self, media: Dict[str, Any]) -> tuple[Optional[str], "MessageType"]:
        """Download a media URL to the Hermes cache. Returns (path, MessageType)."""
        import aiohttp
        from pathlib import Path

        url = str(media.get("url") or media.get("localPath") or "").strip()
        kind = media.get("kind") or "other"
        ext = (media.get("ext") or "bin").lstrip(".")
        file_name = media.get("fileName") or f"zalo.{ext}"
        if not url:
            logger.warning("Zalo: media download skip — no url file=%s", file_name)
            return None, MessageType.TEXT
        if not url.startswith(("http://", "https://")):
            candidates = [url]
            if url.startswith("/data/assistant/"):
                candidates.append("/opt/data" + url[len("/data/assistant") :])
            if url.startswith("/opt/data/"):
                candidates.append("/data/assistant" + url[len("/opt/data") :])
            for candidate in candidates:
                path = Path(str(candidate))
                if not path.is_file():
                    continue
                if kind == "image":
                    return str(path), MessageType.PHOTO
                if kind == "voice":
                    return str(path), MessageType.VOICE
                if kind == "video":
                    return str(path), MessageType.VIDEO
                return str(path), MessageType.DOCUMENT
            logger.warning("Zalo: local media missing file=%s path=%s", file_name, url[:120])
            return None, MessageType.TEXT
        if not self._session or self._session.closed:  # ASSISTANT_FILE_PROMPT_v3
            logger.warning("Zalo: media session closed — reopening for %s", file_name)
            try:
                import aiohttp as _aio
                self._session = _aio.ClientSession()
            except Exception as e:
                logger.warning("Zalo: session reopen failed: %s", e)
                return None, MessageType.TEXT

        data = await self._fetch_media_via_bridge(media)
        if data is None:
            # Fallback: direct GET (works for non-Zalo URLs / already-local proxy)
            try:
                async with self._session.get(
                    url, timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status != 200:
                        logger.warning("Zalo: media download failed (%s) for %s", resp.status, kind)
                        return None, MessageType.TEXT
                    data = await resp.read()
            except Exception as e:
                logger.warning("Zalo: media download error for %s: %s", kind, e)
                return None, MessageType.TEXT

        try:
            if kind == "image":
                return cache_image_from_bytes(data, ext="." + ext), MessageType.PHOTO
            if kind == "voice":
                return cache_audio_from_bytes(data, ext="." + ext), MessageType.VOICE
            if kind == "video":
                return cache_document_from_bytes(data, file_name), MessageType.VIDEO
            return cache_document_from_bytes(data, file_name), MessageType.DOCUMENT
        except Exception as e:
            logger.warning("Zalo: failed to cache media (%s): %s", kind, e)
            return None, MessageType.TEXT

    def _is_addressed(self, m: Dict[str, Any], text: str) -> Optional[str]:
        """Return the (possibly stripped) text if the bot is addressed, else None.

        Detection priority (strongest → weakest):
        1. Real @mention: bridge forwards mentions[] (uids); if our ownId is in
           it, we're mentioned. Strip the leading bot-name token if present.
        2. Reply-to-bot: bridge forwards quotedOwnerId; if it equals ownId, the
           user replied to one of our messages.
        3. Text heuristic fallback: message starts with the bot name / a known
           trigger word (used when we don't have uid signals).
        """
        # 1) Real mention by uid.
        mentions = m.get("mentions") or []
        if self._own_id and str(self._own_id) in {str(x) for x in mentions}:
            return self._strip_leading_name(text) or text

        # 2) Reply to one of the bot's messages (ownerId or uidFrom from bridge).
        q_owner = str(m.get("quotedOwnerId") or "").strip()
        if not q_owner:
            q = m.get("quote") if isinstance(m.get("quote"), dict) else {}
            if isinstance(q, dict):
                q_owner = str(q.get("ownerId") or q.get("uidFrom") or "").strip()
        if self._own_id and q_owner and q_owner == str(self._own_id):
            return text or " "

        # 3) Text heuristic fallback (no reliable uid signal).
        return self._strip_leading_name(text)

    def _strip_leading_name(self, text: str) -> Optional[str]:
        """If text starts with the bot name / a trigger, strip it and return the
        remainder; else None."""
        t = (text or "").strip()
        if not t:
            return None
        candidates = []
        if self._own_name:
            candidates.append(self._own_name)
        candidates += ["hermes", "@hermes", "bot"]
        low = t.lower()
        for c in candidates:
            cl = c.lower()
            if low.startswith(cl):
                return t[len(c):].lstrip(" :,@").strip() or t
            if low.startswith("@" + cl):
                return t[len(c) + 1:].lstrip(" :,@").strip() or t
        return None

    # ── Outbound ──────────────────────────────────────────────────────────

    def _thread_type_for(self, source_or_meta) -> str:
        """Resolve thread type ('user'|'group') from a SessionSource."""
        chat_type = getattr(source_or_meta, "chat_type", None)
        if chat_type == "group":
            return "group"
        return "user"

    async def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        import aiohttp

        if not self.bridge_url:
            return {"error": "no bridge"}
        # Do not share the SSE ClientSession — concurrent GET /events + POST /send
        # yields aiohttp "Server disconnected".
        timeout = aiohttp.ClientTimeout(
            total=120 if path == "/send-attachment" else 60
        )
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.bridge_url}{path}",
                    data=json.dumps(body),
                    headers=self._headers(),
                ) as resp:
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        text = ""
                        try:
                            text = await resp.text()
                        except Exception:
                            text = ""
                        return {"error": f"http {resp.status}: {(text or '')[:180]}"}
                    if not isinstance(data, dict):
                        return {"error": f"http {resp.status}: {str(data)[:160]}"}
                    if resp.status >= 400:
                        err = str(data.get("error") or data.get("message") or f"http {resp.status}")
                        data["error"] = err
                    return data
        except Exception as e:
            return {"error": str(e)}

    def _thread_type_from_chat_id(self, chat_id: str, metadata: Optional[Dict[str, Any]]) -> str:
        if metadata and metadata.get("thread_type") in {"user", "group"}:
            return metadata["thread_type"]
        dest_id = self._as_zalo_api_chat_id(str(chat_id or ""))
        _d = getattr(self, "_as_autosend_turn_dest", None)
        if callable(_d):
            _dest = _d() or {}
            if dest_id == str(_dest.get("thread_id") or "") and _dest.get("thread_type") in {"user", "group"}:
                try:
                    self._thread_types[dest_id] = _dest["thread_type"]
                except Exception:
                    pass
                return _dest["thread_type"]  # ASSISTANT_AUTOSEND_v3
        remembered = self._thread_types.get(str(chat_id)) or self._thread_types.get(dest_id)
        if remembered in {"user", "group"}:
            return remembered
        return "user"

    def _sanitize_send_quote(self, quote):  # ASSISTANT_REPLY_QUOTE_v2 ASSISTANT_SEND_RETRY_v1
        """Keep SendMessageQuote fields. Never quote files/voice/video."""
        if not isinstance(quote, dict):
            return None
        msg_id = quote.get("msgId")
        if msg_id is None:
            msg_id = quote.get("globalMsgId") or quote.get("messageId")
        if msg_id is None:
            return None
        cli = quote.get("cliMsgId")
        if cli is None or str(cli) == "":
            cli = msg_id
        content = quote.get("content")
        if content is None:
            content = quote.get("msg") or quote.get("text") or ""
        if isinstance(content, dict):
            content = str(content.get("title") or content.get("description") or "")
        elif not isinstance(content, str):
            content = str(content or "")
        msg_type = quote.get("msgType")
        if msg_type is None:
            msg_type = quote.get("cliMsgType") or "webchat"
        mt = normalize_zalo_msg_type(msg_type)
        skip = {
            "share.file",
            "chat.voice",
            "chat.video.msg",
            "chat.recommended",
            "chat.sticker",
            "chat.location",
        }
        if mt in skip or mt.startswith("share."):
            return None
        out = {
            "content": content,
            "msgType": mt or "webchat",
            "uidFrom": str(quote.get("uidFrom") or quote.get("ownerId") or ""),
            "msgId": str(msg_id),
            "cliMsgId": str(cli),
            "ts": str(quote.get("ts") or ""),
            "ttl": quote.get("ttl") if quote.get("ttl") is not None else 0,
        }
        if quote.get("propertyExt") is not None:
            out["propertyExt"] = quote.get("propertyExt")
        return out

    def _as_send_retryable(self, err) -> bool:  # ASSISTANT_SEND_RETRY_v1
        try:
            from .autosend import looks_retryable_send
        except ImportError:
            from autosend import looks_retryable_send  # type: ignore
        return looks_retryable_send(str(err or ""))

    def _as_zalo_plain_chunk(self, text: str) -> str:  # ASSISTANT_SEND_RETRY_v1
        """Flatten markdown tables/fences — Zalo often returns unknown error."""
        import re as _re
        t = str(text or "")
        if not t.strip():
            return t
        t = _re.sub(r"```[\w+-]*\n?", "", t)
        lines = []
        for line in t.splitlines():
            s = line.strip()
            bare = s.replace(" ", "")
            if _re.match(r"^\|?:?-+:?\|", bare) or _re.match(r"^:?-{3,}:?$", bare):
                continue
            if s.startswith("|") and s.count("|") >= 2:
                cells = [c.strip() for c in s.strip("|").split("|")]
                lines.append(" · ".join(c for c in cells if c))
                continue
            lines.append(line)
        return "\n".join(lines)




    def _rewrite_gateway_user_notice(self, content: str) -> Optional[str]:  # ASSISTANT_QUIET_SEND_v6
        """Suppress approval / resume / process chatter on Zalo; apply outbound privacy clean."""
        t = (content or "").strip()
        if not t:
            return None
        try:
            from .gateway_noise import filter_outbound
        except ImportError:
            from gateway_noise import filter_outbound  # type: ignore
        action, cleaned = filter_outbound(t)
        if action == "drop":
            if "vars() argument must have __dict__" in t:
                return self._as_ux_line(
                    "ZALO_JOB_FAILED_MSG",
                    ("schedule", "job_failed"),
                    "Scheduled job failed. Please try again later.",
                    user_text=t,
                )
            return ""
        if cleaned != t:
            return cleaned
        return None

    def _is_gateway_noise(self, content: str) -> bool:  # ASSISTANT_QUIET_SEND_v6
        """Drop Hermes progress / PII / process-narration spam from chat."""
        t = (content or "").strip()
        if not t:
            return True
        try:
            from .gateway_noise import drop_outbound
        except ImportError:
            from gateway_noise import drop_outbound  # type: ignore
        return drop_outbound(t)

    def _as_session_http(self, method: str, path: str, payload=None):  # ASSISTANT_AUTOSEND_v3
        import json as _json
        import os
        import urllib.request
        base = (os.getenv("SESSION_URL") or "http://session:8107").rstrip("/")
        data = None if payload is None else _json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            base + path,
            data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return _json.loads(resp.read().decode("utf-8") or "{}")
        except Exception as e:
            logger.debug("Zalo session %s %s failed: %s", method, path, type(e).__name__)
            return {}


    def _as_autosend_roots(self):  # ASSISTANT_AUTOSEND_v4
        import os
        from pathlib import Path
        home = Path(os.getenv("HERMES_HOME") or "/opt/data")
        shared = Path(os.getenv("HERMES_SHARED_DATA") or "/opt/data")
        # Images land on shared /opt/data/media/out (not replica HERMES_HOME).
        return (
            shared / "media" / "out",
            home / "media" / "out",
            Path("/data/media/out"),
            home / "workspace",
        )

    def _as_autosend_ok_ext(self) -> tuple:  # ASSISTANT_AUTOSEND_v4
        return (
            ".txt", ".csv", ".md", ".pdf",
            ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
            ".rtf", ".odt", ".ods",
            ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp",
            ".mp4", ".webm", ".mov", ".m4v", ".mkv",
        )

    def _as_autosend_remember_turn(self, thread_id, thread_type=None) -> None:  # ASSISTANT_AUTOSEND_v3
        """Bind this turn's outbound (file + text) to the thread that asked."""
        try:
            from .turn_wait import real_thread_id
        except ImportError:
            from turn_wait import real_thread_id  # type: ignore
        tid = str(thread_id or "").strip()
        if not tid:
            return
        tt = "group" if str(thread_type or "").lower() in {"group", "g"} else "user"
        dest = {"thread_id": tid, "thread_type": tt}
        turns = getattr(self, "_as_turns", None)
        if not isinstance(turns, dict):
            turns = {}
            self._as_turns = turns
        turns[tid] = dest
        real = real_thread_id(tid)
        if real and real not in turns:
            turns[real] = {"thread_id": real, "thread_type": tt}
        self._as_turn = dest
        try:
            self._thread_types[tid] = tt
            if real:
                self._thread_types[real] = tt
        except Exception:
            pass
        http = getattr(self, "_as_session_http", None)
        if callable(http):
            http("POST", "/v1/turn/dest", {"thread_id": real or tid, "thread_type": tt})
            return
        try:
            import json as _json
            import os
            import urllib.request
            base = (os.getenv("SESSION_URL") or "http://session:8107").rstrip("/")
            req = urllib.request.Request(
                base + "/v1/turn/dest",
                data=_json.dumps({"thread_id": real or tid, "thread_type": tt}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2.0).read()
        except Exception:
            pass

    def _as_autosend_turn_dest(self, chat_id=None) -> dict:  # ASSISTANT_AUTOSEND_v3
        try:
            from .turn_wait import real_thread_id
        except ImportError:
            from turn_wait import real_thread_id  # type: ignore
        turns = getattr(self, "_as_turns", None)
        cid = str(chat_id or "").strip()
        if isinstance(turns, dict) and cid:
            hit = turns.get(cid) or turns.get(real_thread_id(cid))
            if isinstance(hit, dict) and hit.get("thread_id"):
                return hit
        local = getattr(self, "_as_turn", None)
        if isinstance(local, dict) and local.get("thread_id"):
            if not cid:
                return local
            try:
                from .turn_wait import same_dest_thread
            except ImportError:
                from turn_wait import same_dest_thread  # type: ignore
            if same_dest_thread(cid, str(local.get("thread_id") or "")):
                return local
        data = {}
        http = getattr(self, "_as_session_http", None)
        if callable(http):
            data = http("GET", "/v1/turn/dest") or {}
        else:
            try:
                import json as _json
                import os
                import urllib.request
                base = (os.getenv("SESSION_URL") or "http://session:8107").rstrip("/")
                with urllib.request.urlopen(base + "/v1/turn/dest", timeout=2.0) as resp:
                    data = _json.loads(resp.read().decode("utf-8") or "{}")
            except Exception:
                data = {}
        tid = str((data or {}).get("thread_id") or "").strip()
        if not tid:
            return {}
        tt = (data or {}).get("thread_type")
        if tt not in {"user", "group"}:
            tt = "user"
        dest = {"thread_id": tid, "thread_type": tt}
        self._as_turn = dest
        try:
            self._thread_types[tid] = tt
        except Exception:
            pass
        return dest

    def _as_autosend_wrong_thread(self, chat_id, metadata=None) -> bool:  # ASSISTANT_AUTOSEND_v3
        """True = this outbound is the sender DM / other chat, not the ask thread."""
        if isinstance(metadata, dict) and metadata.get("as_skip_dest"):
            return False
        try:
            from .turn_wait import is_isolated_session, real_thread_id
        except ImportError:
            from turn_wait import is_isolated_session, real_thread_id  # type: ignore
        if is_isolated_session(str(chat_id or "")):
            return False
        dest = self._as_autosend_turn_dest(chat_id)
        if not dest or not dest.get("thread_id"):
            return False
        return real_thread_id(str(chat_id or "")) != str(dest["thread_id"])

    def _as_autosend_file_fp(self, file_path) -> str:  # ASSISTANT_AUTOSEND_v5
        """Dedupe key: image stem so foo.png + foo.jpg count as one send."""
        from pathlib import Path

        p = Path(str(file_path or ""))
        stem = (p.stem or p.name or "").lower()
        try:
            from .autosend import VIDEO_EXTS, video_dedupe_stem
        except ImportError:
            from autosend import VIDEO_EXTS, video_dedupe_stem  # type: ignore
        try:
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
                return f"img:{stem}"
            if p.suffix.lower() in VIDEO_EXTS:
                return f"vid:{video_dedupe_stem(str(p))}"
            return f"{p.stat().st_size}:{p.name}"
        except OSError:
            return f"img:{stem}" if stem else (p.name or "")

    def _as_autosend_file_claim(self, file_path, thread_id) -> bool:  # ASSISTANT_AUTOSEND_v3
        """True = we may send this file. False = already sent this turn."""
        key = self._as_autosend_file_fp(file_path)
        if not key:
            return True
        seen = getattr(self, "_as_sent_fp", None)
        if not isinstance(seen, set):
            seen = set()
            self._as_sent_fp = seen
        if key in seen:
            return False
        data = {}
        http = getattr(self, "_as_session_http", None)
        if callable(http):
            data = http("POST", "/v1/files/claim", {"key": key, "thread_id": str(thread_id or "")}) or {}
        else:
            try:
                import json as _json
                import os
                import urllib.request
                base = (os.getenv("SESSION_URL") or "http://session:8107").rstrip("/")
                req = urllib.request.Request(
                    base + "/v1/files/claim",
                    data=_json.dumps({"key": key, "thread_id": str(thread_id or "")}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    data = _json.loads(resp.read().decode("utf-8") or "{}")
            except Exception:
                data = {"first": True}
        first = bool((data or {}).get("first", True))
        if first:
            seen.add(key)
        return first

    def _as_autosend_already_sent(self, file_path) -> bool:
        key = self._as_autosend_file_fp(file_path)
        if not key:
            return False
        seen = getattr(self, "_as_sent_fp", None)
        return isinstance(seen, set) and key in seen

    def _as_autosend_file_unclaim(self, file_path) -> None:
        key = self._as_autosend_file_fp(file_path)
        seen = getattr(self, "_as_sent_fp", None)
        if key and isinstance(seen, set):
            seen.discard(key)

    def _as_autosend_looks_like_ack(self, content: str) -> bool:  # ASSISTANT_AUTOSEND_v3
        low = (content or "").lower()
        needles = (
            "không thể gửi file",
            "khong the gui file",
            "cannot send file",
            "can't send file",
            "can not send file",
            "chỉ có thể gửi nội dung text",
            "chi co the gui noi dung text",
            "đã được tạo",
            "da duoc tao",
            "file của bạn",
            "đây là file của bạn",
            "here is your file",
            "đã xong",
            "done.",
        )
        return any(n in low for n in needles)

    async def _as_autosend_turn_files(self, chat_id, content, metadata=None):  # ASSISTANT_AUTOSEND_v5
        """Send at most one new file this turn; return result-only caption."""
        import os
        import shutil
        import time
        from pathlib import Path

        meta = metadata if isinstance(metadata, dict) else {}
        if meta.get("as_skip_autosend"):
            return content
        try:
            from .turn_wait import same_dest_thread
        except ImportError:
            from turn_wait import same_dest_thread  # type: ignore
        dest_turn = self._as_autosend_turn_dest(chat_id)
        cid = str(chat_id or "")
        dest_id = str((dest_turn or {}).get("thread_id") or "")
        if dest_id and cid and not meta.get("as_skip_dest") and not same_dest_thread(cid, dest_id):
            logger.info(
                "Zalo: skip autosend chat=%s (turn is %s)",
                chat_id,
                dest_turn.get("thread_id"),
            )
            return content
        tid = cid or dest_id
        if dest_turn.get("thread_type") in {"user", "group"}:
            meta = {**meta, "thread_type": dest_turn["thread_type"]}
        clock = (getattr(self, "_as_tclock", {}) or {}).get(tid) or {}
        t0 = float(clock.get("t0") or 0.0)
        if t0 <= 0:
            t0 = time.time() - 180
        seq_map = getattr(self, "_as_compound_seq_t0", None)
        seq_t0 = 0.0
        if isinstance(seq_map, dict):
            try:
                seq_t0 = float(seq_map.get(tid) or 0.0)
            except (TypeError, ValueError):
                seq_t0 = 0.0
        cap_map = getattr(self, "_as_file_ceiling", None)
        ceiling = 0.0
        if isinstance(cap_map, dict):
            try:
                ceiling = float(cap_map.get(tid) or 0.0)
            except (TypeError, ValueError):
                ceiling = 0.0
        try:
            from .autosend import (
                file_in_send_window,
                file_ready_for_send,
                prefer_remuxed_video,
                video_dedupe_stem,
            )
        except ImportError:
            from autosend import (  # type: ignore
                file_in_send_window,
                file_ready_for_send,
                prefer_remuxed_video,
                video_dedupe_stem,
            )
        grace = self._as_env_float("ZALO_AUTOSEND_GRACE_S", 8.0, 0.0, 60.0)
        ok_ext = self._as_autosend_ok_ext()
        found = []
        now = time.time()
        for root in self._as_autosend_roots():
            try:
                if not root.is_dir():
                    continue
                for p in root.iterdir():
                    if not p.is_file():
                        continue
                    if p.suffix.lower() not in ok_ext:
                        continue
                    if p.name.startswith("."):
                        continue
                    try:
                        mt = p.stat().st_mtime
                    except OSError:
                        continue
                    if not file_in_send_window(mt, t0, seq_t0, grace_s=grace, ceiling=ceiling):
                        continue
                    if not file_ready_for_send(mt, now):
                        continue
                    found.append(p)
            except OSError:
                continue
        if not found:
            return content
        img_ext = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
        video_ext = {".mp4", ".webm", ".mov", ".m4v", ".mkv"}
        still_names = {"clip-still.jpg", "clip-still.jpeg", "clip-still.png"}
        found.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        has_video = any(p.suffix.lower() in video_ext for p in found)
        if has_video:
            found = [p for p in found if p.name.lower() not in still_names]
        if found and found[0].suffix.lower() in video_ext:
            found = [p for p in found if p.suffix.lower() in video_ext]
        deduped = []
        seen_vid = set()
        for p in found:
            if p.suffix.lower() in video_ext:
                key = video_dedupe_stem(str(p))
                if key in seen_vid:
                    continue
                seen_vid.add(key)
                preferred = Path(prefer_remuxed_video(str(p)))
                deduped.append(preferred if preferred.is_file() else p)
            else:
                deduped.append(p)
        found = deduped
        sent = 0
        blocked_n = 0
        out_dir = self._as_autosend_roots()[0]
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        caption = ""
        seen_stem = set()
        for src in found:
            if src.suffix.lower() in img_ext:
                stem = src.stem.lower()
                if stem in seen_stem:
                    continue
                seen_stem.add(stem)
            dest = src
            try:
                if src.parent.resolve() != out_dir.resolve():
                    dest = out_dir / src.name
                    shutil.copy2(src, dest)
            except OSError:
                dest = src
            if self._as_autosend_already_sent(dest):
                logger.info("Zalo: autosend skip already-claimed %s", dest.name)
                continue
            try:
                dest_send = dest
                try:
                    from .autosend import existing_media_path
                except ImportError:
                    from autosend import existing_media_path  # type: ignore
                resolved = existing_media_path(str(dest))
                if resolved:
                    dest_send = Path(resolved)
                if not self._as_autosend_file_claim(dest_send, tid):
                    logger.info("Zalo: autosend skip already-claimed %s", dest_send.name)
                    continue
                meta_send = {
                    **meta,
                    "as_skip_autosend": True,
                    "as_claimed": True,
                }
                kind = dest_send.suffix.lower()
                if kind in img_ext:
                    res = await self.send_image_file(
                        tid,
                        str(dest_send),
                        caption="",
                        metadata=meta_send,
                    )
                elif kind in video_ext:
                    dest_send = Path(prefer_remuxed_video(str(dest_send)))
                    if not dest_send.name.endswith(".zalo.mp4"):
                        remuxed = self._as_remux_zalo_video(str(dest_send))
                        if remuxed:
                            dest_send = Path(remuxed)
                    res = await self.send_video(
                        tid,
                        str(dest_send),
                        caption="",
                        metadata=meta_send,
                    )
                else:
                    res = await self.send_document(
                        tid,
                        str(dest_send),
                        caption="",
                        file_name=dest_send.name,
                        metadata=meta_send,
                    )
                err = ""
                if isinstance(res, dict):
                    err = str(res.get("error") or "")
                    ok = not err
                else:
                    err = str(getattr(res, "error", "") or "")
                    ok = bool(getattr(res, "success", False) if res is not None else False)
                if err == "av_blocked":
                    blocked_n += 1
                    self._as_autosend_file_unclaim(dest_send)
                    continue
                if ok:
                    sent += 1
                    self._as_mark_job_file_sent(tid)
                    flow = getattr(self, "_as_flow", None)
                    if callable(flow):
                        flow("zalo_send_file", thread_id=tid, file=dest_send.name, path=str(dest_send)[:160])
                    else:
                        logger.debug(f"[flow] stage=zalo_send_file thread_id={tid} file={dest_send.name}")
                    break
                self._as_autosend_file_unclaim(dest_send)
            except Exception as e:
                try:
                    self._as_autosend_file_unclaim(dest_send)
                except Exception:
                    pass
                logger.warning("Zalo autosend failed %s: %s", src.name, e)
        if sent <= 0:
            if blocked_n:
                return "File contains risks so it cannot be sent."
            if self._as_autosend_looks_like_ack(content) or not (content or "").strip():
                if self._as_compound_has_more_after(tid):
                    return ""
                return caption
            return content
        if self._as_compound_has_more_after(tid):
            self._as_compound_defer_ack.add(tid)
            return ""
        return caption


    def _as_redact_internal(self, content: str) -> str:  # ASSISTANT_PATH_REDACT_v1
        """Strip server paths / secrets / Hermes cron wrappers from outbound chat."""
        import re as _re
        t = content or ""
        if not t.strip():
            return t
        try:
            from .gateway_noise import strip_cron_delivery
        except ImportError:
            from gateway_noise import strip_cron_delivery  # type: ignore
        t = strip_cron_delivery(t)

        def _path_sub(m):
            raw = m.group(0).strip("`'")
            base = raw.rstrip("/").rsplit("/", 1)[-1]
            if base and "." in base and len(base) < 80:
                return base
            return ""

        t = _re.sub(
            r"`?(?:/opt/data|/data/hermes|/opt/assistant|/home/[^\s/`'\"]+)(?:/[^\s`'\"]+)*`?",
            _path_sub,
            t,
        )
        t = _re.sub(
            r"(?i)(api[_-]?key|access[_-]?token|password|secret|openbao)\s*[:=]\s*\S+",
            r"\1=…",
            t,
        )
        # Chat/thread/DM/folder meta scrubbing is owned by classify + outbound LLM
        # prompts (no host phrase regex / no locale hardcoding).
        while "  " in t:
            t = t.replace("  ", " ")
        while "\n\n\n" in t:
            t = t.replace("\n\n\n", "\n\n")
        return t.strip() if t.strip() else content


    def _as_flow(self, stage: str, **fields) -> None:  # ASSISTANT_FILE_PIPELINE_v6
        parts = [f"[flow] stage={stage}"]
        for k, v in fields.items():
            if v is None:
                continue
            s = str(v).replace("\n", " ").replace('"', "'")
            if " " in s:
                s = f'"{s}"'
            parts.append(f"{k}={s}")
        line = " ".join(parts)
        logger.debug(line)
        logger.info("%s", line)

    def _as_file_pipeline_enabled(self) -> bool:  # ASSISTANT_FILE_PIPELINE_v6
        import os
        v = (os.getenv("ZALO_FILE_PIPELINE") or "1").strip().lower()
        return v in {"1", "true", "yes", "on"}

    async def _as_worker_text(self, url: str, payload: dict, *, timeout_s: float) -> str:
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=timeout_s)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    body = await resp.text()
                    if resp.status >= 300:
                        self._as_flow(
                            "attach_worker_fail",
                            url=url,
                            status=resp.status,
                        )
                        # Sentinel so callers can distinguish 404 from empty OCR.
                        if resp.status == 404:
                            return "__AS_WORKER_404__"
                        return ""
            data = json.loads(body or "{}")
        except Exception as e:
            self._as_flow("attach_worker_error", url=url, error=type(e).__name__)
            return ""
        if not isinstance(data, dict):
            return ""
        return str(data.get("text") or data.get("markdown") or data.get("transcript") or "").strip()

    def _as_archive_password_from_caption(self, text: str) -> str:
        """Optional archive password from caption prefixes (not intent regex)."""
        raw = str(text or "").strip()
        if not raw:
            return ""
        low = raw.casefold()
        for prefix in (
            "password:",
            "password :",
            "pw:",
            "pwd:",
            "mật khẩu:",
            "mat khau:",
            "matkhau:",
        ):
            if low.startswith(prefix):
                return raw[len(prefix) :].strip()
        return ""

    async def _as_archive_worker_text(
        self, url: str, payload: dict, *, timeout_s: float
    ) -> str:
        """Like _as_worker_text but maps archive password/errors to sentinels."""
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=timeout_s)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    body = await resp.text()
                    if resp.status >= 300:
                        self._as_flow(
                            "attach_worker_fail",
                            url=url,
                            status=resp.status,
                        )
                        if resp.status == 404:
                            return "__AS_WORKER_404__"
                        return ""
            data = json.loads(body or "{}")
        except Exception as e:
            self._as_flow("attach_worker_error", url=url, error=type(e).__name__)
            return ""
        if not isinstance(data, dict):
            return ""
        reason = str(data.get("reason") or "").strip()
        if reason == "password_required":
            return "__AS_ARCHIVE_PASSWORD__"
        if reason == "bad_password":
            return "__AS_ARCHIVE_BAD_PASSWORD__"
        if reason in {"unsupported", "bad_archive"} and not data.get("ok"):
            return ""
        return str(data.get("text") or data.get("markdown") or data.get("transcript") or "").strip()

    async def _as_attachment_text(
        self, local_path: str, file_name: str = "", *, caption: str = ""
    ) -> str:
        """Readable text for one inbound file, routed to the worker that owns it.

        text  → read locally · vision → vision-ocr combo · office → Ingest worker
        archive → Ingest `/v1/extract-archive` (media members only; optional password)
        av    → Media worker `/v1/media/text` (transcript + keyframe vision read)
        """
        import asyncio
        import os
        from pathlib import Path

        try:
            from .vision_ocr import DEFAULT_PROMPT, vision_read, vision_read_path
        except ImportError:
            from vision_ocr import DEFAULT_PROMPT, vision_read, vision_read_path  # type: ignore

        src = Path(str(local_path or ""))
        if not src.is_file():
            return ""
        name = file_name or src.name
        kind = attachment_kind(name)
        worker_path = worker_media_path(str(src))
        match kind:
            case "text":
                try:
                    text = src.read_text(encoding="utf-8", errors="replace")[:ATTACHMENT_TEXT_CHARS]
                except OSError:
                    text = ""
            case "ocr":
                prompt = DEFAULT_PROMPT
                low_name = name.lower()
                if low_name.endswith(".pdf"):
                    ingest_url = (os.getenv("INGEST_URL") or "http://ingest:8099").rstrip("/")
                    text = await self._as_worker_text(
                        f"{ingest_url}/v1/extract-text",
                        {"path": worker_path, "max_chars": ATTACHMENT_TEXT_CHARS},
                        timeout_s=max(ATTACHMENT_OFFICE_TIMEOUT_S, 120.0),
                    )
                    if text == "__AS_WORKER_404__":
                        text = ""
                    if not text:
                        text = await asyncio.to_thread(vision_read_path, str(src), prompt)
                else:
                    text = await asyncio.to_thread(vision_read_path, str(src), prompt)
                    if not text:
                        import base64

                        b64 = vision_image_b64_for_describe(str(src)) or base64.b64encode(
                            src.read_bytes()
                        ).decode("ascii")
                        out = await asyncio.to_thread(
                            vision_read, image_b64=b64, prompt=prompt
                        )
                        text = str((out or {}).get("text") or "")
                self._as_flow(
                    "attach_vision_read",
                    file=name,
                    chars=len(text),
                    path=worker_path[:160],
                )

            case "office":
                ingest_url = (os.getenv("INGEST_URL") or "http://ingest:8099").rstrip("/")
                text = await self._as_worker_text(
                    f"{ingest_url}/v1/extract-text",
                    {"path": worker_path, "max_chars": ATTACHMENT_TEXT_CHARS},
                    timeout_s=ATTACHMENT_OFFICE_TIMEOUT_S,
                )
            case "archive":
                # Zip/7z/rar/tar → media members only. Never Hermes terminal unzip.
                ingest_url = (os.getenv("INGEST_URL") or "http://ingest:8099").rstrip("/")
                payload: dict = {"path": worker_path, "max_chars": ATTACHMENT_TEXT_CHARS}
                pwd = self._as_archive_password_from_caption(caption)
                if pwd:
                    payload["password"] = pwd
                text = await self._as_archive_worker_text(
                    f"{ingest_url}/v1/extract-archive",
                    payload,
                    timeout_s=max(ATTACHMENT_ARCHIVE_TIMEOUT_S, 90.0),
                )
            case "av":
                media_url = (
                    os.getenv("DISPATCHER_URL") or "http://dispatcher:8090"
                ).rstrip("/")
                text = await self._as_worker_text(
                    f"{media_url}/v1/media/text",
                    {"path": worker_path},
                    timeout_s=ATTACHMENT_AV_TIMEOUT_S,
                )
            case _:
                text = ""
        self._as_flow(
            "attach_text",
            file=name,
            kind=kind,
            chars=len(text),
            path=worker_path[:160],
        )
        return text

    def _as_attachment_ttl_s(self) -> int:
        import os

        try:
            return max(
                60,
                int(
                    os.getenv("ZALO_ATTACHMENT_CONTEXT_TTL_S")
                    or str(ATTACHMENT_CONTEXT_TTL_S_DEFAULT)
                ),
            )
        except ValueError:
            return ATTACHMENT_CONTEXT_TTL_S_DEFAULT

    def _as_attachment_remember(self, thread_id: str, file_name: str, text: str) -> None:
        """Keep recent attachment text so follow-up turns need no re-upload.

        A mixed media pack arrives as one event per file, so several files are
        kept — see ``attachment.context_merge``.
        """
        try:
            from .turn_wait import real_thread_id
        except ImportError:
            from turn_wait import real_thread_id  # type: ignore

        tid = real_thread_id(str(thread_id or "").strip())
        if not tid or not (text or "").strip():
            return
        store = self._as_gate_store()
        if store is None or not hasattr(store, "attachment_put"):
            return
        items = context_merge(self._as_attachment_items(tid), file_name, text)
        try:
            store.attachment_put(
                tid, context_encode(items), self._as_attachment_ttl_s()
            )
            self._as_flow(
                "attach_remember",
                thread_id=tid,
                file=file_name,
                chars=len(text),
                items=len(items),
            )
        except Exception as e:
            logger.debug("Zalo attachment remember failed: %s", type(e).__name__)

    def _as_attachment_items(self, thread_id: str) -> list[dict]:
        """Recent attachments for this thread, oldest first."""
        try:
            from .turn_wait import real_thread_id
        except ImportError:
            from turn_wait import real_thread_id  # type: ignore

        tid = real_thread_id(str(thread_id or "").strip())
        if not tid:
            return []
        store = self._as_gate_store()
        if store is None or not hasattr(store, "attachment_get"):
            return []
        try:
            return context_decode(store.attachment_get(tid))
        except Exception:
            return []

    def _as_attachment_prompt(
        self,
        file_name: str,
        excerpt: str,
        *,
        is_image: bool,
        local_path: str = "",
    ) -> str:
        """Bare-attachment prompt. Extracted text wins; never ask the user to paste it."""
        kind = attachment_kind(file_name)
        body = (excerpt or "").strip()
        if body:
            head = (
                f"[Attached {kind} file: {file_name}]\n"
                "Tóm tắt 3–6 ý chính (bullet ngắn) từ nội dung dưới đây ngay trong tin trả lời này. "
                "Nếu hệ thống có gửi hỏi duyệt học knowledge, vẫn phải gửi tóm tắt trước. "
                "Cấm trích dài, cấm liệt kê từng section, cấm hỏi user dán lại nội dung."
            )
            if is_image:
                head = (
                    f"[Attached image: {file_name}]\n"
                    "Tóm tắt nội dung ảnh (bullet ngắn) từ phần dưới. "
                    "Không hỏi user mô tả ảnh."
                )
            return f"{head}\n\n[Extracted text — summarize from this]\n{body[:ATTACHMENT_PROMPT_CHARS]}"
        if is_image:
            return (
                f"[Attached image: {file_name}]\n"
                "OCR worker did not extract readable text. Use the attached image "
                "(multimodal) to describe the scene and any visible text in a short "
                "Vietnamese summary. Do not ask the user to resend or describe the image."
            )
        if kind == "av":
            return (
                f"[Attached media: {file_name}]\n"
                "Không lấy được transcript/khung hình có chữ từ file này. "
                "Nói thẳng một dòng là chưa đọc được nội dung media và hỏi user muốn xử lý gì "
                "(tóm tắt khi bật transcript, tách âm thanh, lấy khung hình). "
                "Cấm nói đã tóm tắt, cấm hỏi user dán nội dung."
            )
        if kind == "archive":
            return (
                f"[Tin kèm archive: {file_name}]\n"
                "Archive không có media để đọc (chỉ xử lý ảnh/pdf/office/text/av; bỏ file khác "
                "và archive lồng nhau). Nói ngắn và hỏi user gửi lại đúng media. "
                "Cấm terminal/unzip/zipfile forensics."
            )
        return (
            f"[Tin kèm file: {file_name}]\n"
            "Chưa đọc được nội dung file (OCR/đọc trống). Nói thẳng một dòng là chưa đọc được, "
            "hỏi user gửi lại hoặc đổi định dạng. Cấm hỏi user dán nội dung, cấm bịa tóm tắt."
        )

    def _as_attachment_followup(self, thread_id: str, text: str) -> str:
        """Text-only turn: re-attach recent file text so nothing is re-uploaded."""
        items = self._as_attachment_items(thread_id)
        if not items:
            return text
        blocks = context_blocks(items, budget=ATTACHMENT_PROMPT_CHARS)
        if not blocks:
            return text
        self._as_flow("attach_followup", thread_id=thread_id, files=len(blocks))
        joined = "\n\n".join(reversed(blocks))
        return (
            f"{text}\n\n[Recent attachments in this chat — use them if the request refers to "
            f"those files, otherwise ignore]\n{joined}"
        )

    def _as_attachment_recall(self, thread_id: str) -> tuple[str, str]:
        """(file_name, text) of the newest remembered attachment in this thread."""
        return context_newest(self._as_attachment_items(thread_id))

    def _as_env_flag_on(self, *names: str, default: str = "inactive") -> bool:
        """Feature toggles: active|inactive only."""
        import os

        for name in names:
            raw = os.getenv(name)
            if raw is None:
                continue
            v = str(raw).strip().lower()
            if v == "active":
                return True
            if v == "inactive":
                return False
        return (default or "inactive").strip().lower() == "active"

    def _as_av_activated(self) -> bool:  # ASSISTANT_FILE_PIPELINE_v6
        """True when antivirus is on and the gateway+clamd are reachable."""
        import os
        import urllib.request

        if not self._as_env_flag_on("AV_SCAN", "ENABLE_ANTIVIRUS", default="inactive"):
            return False
        url = (os.getenv("AV_GATEWAY_URL") or "http://av-gateway:8098").rstrip("/")
        try:
            with urllib.request.urlopen(url + "/health", timeout=2.0) as resp:
                import json as _json

                data = _json.loads(resp.read().decode("utf-8") or "{}")
            return bool(data.get("ok")) and bool(data.get("clamd"))
        except Exception:
            return False

    def _as_av_required(self) -> bool:
        """Hard-refuse only when AV_REQUIRED is explicitly on.

        ENABLE_ANTIVIRUS alone must not block OCR/vision when the gateway is
        temporarily down — fall through to security-manager / pipeline instead.
        """
        import os

        raw = (os.getenv("AV_REQUIRED") or "").strip().lower()
        return raw == "active"

    def _as_security_worker_active(self) -> bool:
        """True when Security Worker is intentionally enabled for this stack."""
        return self._as_env_flag_on(
            "ENABLE_SECURITY", "WORKER_SECURITY", default="inactive"
        )

    async def _as_security_file_allow(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        correlation_id: str = "",
    ) -> tuple[bool, str]:
        """Optional isolation via security-manager when AV gateway is down.

        Returns (blocked, user_message). Allow when security worker inactive or
        unreachable (unless fail-closed).
        """
        import os
        import uuid

        if not file_bytes or not self._as_security_worker_active():
            return False, ""
        base = (
            os.getenv("SECURITY_MANAGER_URL")
            or os.getenv("SECURITY_URL")
            or "http://security-manager:8093"
        ).rstrip("/")
        fail_open = _env_flag("SECURITY_FAIL_OPEN", default=False)
        corr = (correlation_id or "").strip() or f"zalo_file_{uuid.uuid4().hex[:12]}"
        try:
            import aiohttp

            timeout = aiohttp.ClientTimeout(total=90)
            form = aiohttp.FormData()
            form.add_field("session_id", corr)
            form.add_field(
                "file",
                file_bytes,
                filename=filename or "upload.bin",
                content_type="application/octet-stream",
            )
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{base}/v1/scan", data=form) as resp:
                    if resp.status >= 300:
                        if fail_open:
                            return False, ""
                        return True, self._as_ux_line(
                            "ZALO_AV_UNAVAILABLE_MSG",
                            ("security", "av_unavailable"),
                            "Antivirus is not ready. File was not accepted — try again later.",
                        )
                    data = await resp.json(content_type=None)
            verdict = str((data or {}).get("verdict") or "").strip().upper()
            if verdict in {"RISK", "BLOCK", "BLOCKED", "INFECTED"}:
                msg = str((data or {}).get("user_message") or "").strip() or (
                    "File contains risks so it cannot be extracted to inspect information inside."
                )
                return True, msg
            return False, ""
        except Exception:
            if fail_open:
                return False, ""
            # Prefer continue to OCR over silent drop when isolation is optional.
            return False, ""

    async def _as_security_message_gate(
        self,
        *,
        text: str,
        thread_id: str,
        user_id: str,
        correlation_id: str = "",
    ) -> tuple[bool, str]:
        """Check inbound Zalo text with Security Worker before Hermes.

        Returns (blocked, user_message). When Security Worker is inactive → allow.
        When active but unreachable → fail closed (configurable via SECURITY_FAIL_OPEN=1).
        """
        import os
        import uuid

        if not self._as_security_worker_active():
            return False, ""
        body = (text or "").strip()
        if not body:
            return False, ""
        base = (
            os.getenv("SECURITY_MANAGER_URL")
            or os.getenv("SECURITY_URL")
            or "http://security-manager:8093"
        ).rstrip("/")
        corr = (correlation_id or "").strip() or f"zalo_{uuid.uuid4().hex[:12]}"
        fail_open = _env_flag("SECURITY_FAIL_OPEN", default=False)
        try:
            import asyncio
            import json as _json
            import urllib.request

            def _post() -> dict:
                req = urllib.request.Request(
                    base + "/v1/message-check",
                    data=_json.dumps(
                        {
                            "text": body,
                            "thread_id": str(thread_id or ""),
                            "user_id": str(user_id or ""),
                            "correlation_id": corr,
                            "source": "zalo",
                        }
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    return _json.loads(resp.read().decode("utf-8") or "{}")

            data = await asyncio.to_thread(_post)
            if data.get("allowed") is False or str(data.get("action") or "") == "block":
                msg = str(
                    data.get("user_message")
                    or self._as_ux_line(
                        "ZALO_SECURITY_BLOCK_MSG",
                        ("security", "blocked"),
                        "Tin nhắn bị chặn bởi bảo mật.",
                    )
                )
                self._as_flow(
                    "security_message_blocked",
                    thread_id=thread_id,
                    user_id=user_id,
                    correlation_id=corr,
                )
                return True, msg
            return False, ""
        except Exception as exc:
            self._as_flow(
                "security_message_unavailable",
                thread_id=thread_id,
                error=type(exc).__name__,
                fail_open=fail_open,
                correlation_id=corr,
            )
            if fail_open:
                return False, ""
            msg = self._as_ux_line(
                "ZALO_SECURITY_UNAVAILABLE_MSG",
                ("security", "unavailable"),
                "Bảo mật tạm thời không sẵn sàng. Thử lại sau.",
            )
            return True, msg

    async def _as_av_gate(  # ASSISTANT_FILE_PIPELINE_v6
        self, thread_id, sender_id, local_path: str, media: dict, user_text: str = ""
    ) -> bool:
        """Scan before LLM via AV gateway / Security Worker. True = abort turn."""
        import asyncio
        import os
        import time
        from pathlib import Path

        if not local_path:
            return False
        # Secret refuse only on an explicit user ask. Ignore Zalo fileExt wire JSON
        # and filename-alone (blank/docs false positives). Prior learn-skip does not abort.
        ask_blob = self._as_user_secret_ask_blob(user_text, media if isinstance(media, dict) else {})
        refuse_body = (
            await asyncio.to_thread(self._as_classify_refuse_body, ask_blob)
            if ask_blob
            else ""
        )
        if ask_blob and (
            self._as_secret_probe_text(ask_blob) or refuse_body
        ):
            self._as_learn_skip_mark(thread_id, sender_id)
            self._as_flow(
                "learn_skip",
                reason="classify_secret_av_gate",
                thread_id=thread_id,
                file=(media or {}).get("fileName"),
            )
            try:
                refuse = refuse_body or self._as_secret_refuse_line(ask_blob)
                await self.send(
                    chat_id=str(thread_id),
                    content=refuse,
                    metadata={
                        "thread_type": "user",
                        "as_skip_inflight": True,
                    },
                )
            except Exception:
                pass
            return True
        fn = str((media or {}).get("fileName") or Path(local_path).name or "file")
        kind = str((media or {}).get("kind") or "file")
        if kind in {"voice", "sticker", "gif"}:
            return False
        self._as_flow(
            "media_ready",
            thread_id=thread_id,
            sender_id=sender_id,
            file=fn,
            kind=kind,
            path=str(local_path)[:160],
        )

        src = Path(local_path)
        if not src.is_file():
            alt = Path("/opt/data") / "cache" / src.name
            src = alt if alt.is_file() else src
        file_bytes = b""
        try:
            if src.is_file():
                file_bytes = await asyncio.to_thread(src.read_bytes)
        except OSError:
            file_bytes = b""

        if not self._as_file_pipeline_enabled():
            self._as_flow("av_skip", reason="pipeline_off", file=fn, thread_id=thread_id)
            return False
        if not self._as_av_activated():
            self._as_flow("av_skip", reason="unavailable", file=fn, thread_id=thread_id)
            required = self._as_av_required()
            # AV intended on but gateway/clamd down: try security-manager isolation
            # before hard-refuse. OCR/vision must not die solely because ClamAV is restarting.
            if self._as_env_flag_on("AV_SCAN", "ENABLE_ANTIVIRUS", default="inactive"):
                blocked, msg = await self._as_security_file_allow(
                    file_bytes=file_bytes,
                    filename=fn,
                    correlation_id=f"zalo-{thread_id}",
                )
                if blocked:
                    try:
                        await self.send(
                            chat_id=str(thread_id),
                            content=msg
                            or "File contains risks so it cannot be extracted to inspect information inside.",
                            metadata={
                                "thread_type": "user",
                                "as_skip_inflight": True,
                            },
                        )
                    except Exception:
                        pass
                    return True
                self._as_flow(
                    "av_skip",
                    reason="security_fallback",
                    file=fn,
                    thread_id=thread_id,
                )
                self._as_enqueue_file_pipeline(
                    thread_id, sender_id, local_path, media, user_text=user_text
                )
                return False
            if required:
                try:
                    msg = self._as_ux_line(
                        "ZALO_AV_UNAVAILABLE_MSG",
                        ("security", "av_unavailable"),
                        "Chưa quét được file (antivirus chưa sẵn sàng). Gửi lại sau nhé.",
                    )
                    await self.send(
                        chat_id=str(thread_id),
                        content=msg,
                        metadata={
                            "thread_type": "user",
                            "as_skip_inflight": True,
                        },
                    )
                except Exception:
                    pass
                return True
            self._as_enqueue_file_pipeline(
                thread_id, sender_id, local_path, media, user_text=user_text
            )
            return False

        av_url = (os.getenv("AV_GATEWAY_URL") or "http://av-gateway:8098").rstrip("/")
        session_id = f"zalo-{thread_id}"
        t0 = time.monotonic()
        try:
            data = file_bytes
            if not data and src.is_file():
                data = await asyncio.to_thread(src.read_bytes)
            if not data:
                self._as_flow("av_skip", reason="empty_bytes", file=fn, thread_id=thread_id)
                return False
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                form = aiohttp.FormData()
                form.add_field("session_id", session_id)
                form.add_field(
                    "file",
                    data,
                    filename=fn,
                    content_type=(media or {}).get("mime") or "application/octet-stream",
                )
                self._as_flow("av_scan", thread_id=thread_id, file=fn, bytes=len(data), session_id=session_id)
                async with session.post(f"{av_url}/v1/scan", data=form) as resp:
                    if resp.status >= 300:
                        body = await resp.text()
                        self._as_flow("av_fail", thread_id=thread_id, status=resp.status, error=(body or "")[:120])
                        if self._as_av_required():
                            try:
                                msg = self._as_ux_line(
                                    "ZALO_AV_UNAVAILABLE_MSG",
                                    ("security", "av_unavailable"),
                                    "Chưa quét được file (antivirus chưa sẵn sàng). Gửi lại sau nhé.",
                                )
                                await self.send(
                                    chat_id=str(thread_id),
                                    content=msg,
                                    metadata={
                                        "thread_type": "user",
                                        "as_skip_inflight": True,
                                    },
                                )
                            except Exception:
                                pass
                            return True
                        self._as_enqueue_file_pipeline(
                            thread_id, sender_id, local_path, media, user_text=user_text
                        )
                        return False
                ready = False
                blocked = False
                # Small files are usually clean within one tick — poll fast first,
                # then back off so a slow scan still gets the full budget.
                delay = AV_POLL_MIN_S
                waited = 0.0
                while waited < AV_POLL_BUDGET_S:
                    async with session.get(f"{av_url}/v1/sessions/{session_id}/ready") as r2:
                        if r2.status == 404:
                            break
                        if r2.status < 300:
                            st = await r2.json(content_type=None)
                            if st.get("blocked"):
                                blocked = True
                                break
                            if st.get("ready"):
                                ready = True
                                break
                    await asyncio.sleep(delay)
                    waited += delay
                    delay = min(AV_POLL_MAX_S, delay * 2)
            elapsed = time.monotonic() - t0
            if blocked:
                self._as_flow("av_blocked", thread_id=thread_id, file=fn, session_id=session_id, seconds=f"{elapsed:.2f}")
                try:
                    await self.send(
                        chat_id=str(thread_id),
                        content="File contains risks so it cannot be extracted to inspect information inside.",
                        metadata={
                            "thread_type": "user",
                            "as_skip_inflight": True,
                        },
                    )
                except Exception:
                    pass
                return True
            if ready:
                self._as_flow("av_clean", thread_id=thread_id, file=fn, session_id=session_id, seconds=f"{elapsed:.2f}")
            else:
                self._as_flow("av_timeout", thread_id=thread_id, file=fn, session_id=session_id, seconds=f"{elapsed:.2f}")
            self._as_enqueue_file_pipeline(
                thread_id, sender_id, local_path, media, user_text=user_text
            )
            return False
        except Exception as e:
            self._as_flow("av_error", thread_id=thread_id, file=fn, error=type(e).__name__)
            self._as_enqueue_file_pipeline(
                thread_id, sender_id, local_path, media, user_text=user_text
            )
            return False

    def _as_enqueue_file_pipeline(  # ASSISTANT_FILE_PIPELINE_v6
        self,
        thread_id,
        sender_id,
        local_path: str,
        media: dict,
        user_text: str = "",
    ) -> None:
        import asyncio

        if not self._as_file_pipeline_enabled():
            return
        if self._as_learn_skip_hit(thread_id, sender_id):
            self._as_flow(
                "learn_skip",
                reason="classify_secret",
                thread_id=thread_id,
                file=(media or {}).get("fileName"),
            )
            return
        kind = (media or {}).get("kind") or "file"
        if kind in {"voice", "image", "gif", "sticker"}:
            return
        try:
            asyncio.create_task(
                self._as_file_pipeline_task(
                    str(thread_id or ""),
                    str(sender_id or ""),
                    local_path,
                    media or {},
                    str(user_text or ""),
                )
            )
        except Exception as e:
            logger.debug("Zalo file-pipeline enqueue failed: %s", type(e).__name__)

    async def _as_file_pipeline_task(  # ASSISTANT_FILE_PIPELINE_v6
        self,
        thread_id: str,
        sender_id: str,
        local_path: str,
        media: dict,
        user_text: str = "",
    ) -> None:
        import asyncio
        import json
        import os
        import shutil
        import uuid
        from pathlib import Path

        if not thread_id or not local_path:
            return
        if self._as_learn_skip_hit(thread_id, sender_id):
            self._as_flow(
                "learn_skip",
                reason="secret_probe",
                thread_id=thread_id,
                file=(media or {}).get("fileName"),
            )
            return
        file_name = (media or {}).get("fileName") or Path(local_path).name or "document.bin"
        kind = (media or {}).get("kind") or "file"
        ingest_url = (os.getenv("INGEST_URL") or "http://ingest:8099").rstrip("/")
        inbound_root = Path(os.getenv("ASSISTANT_MEDIA_INBOUND", "/opt/data/media/inbound"))
        try:
            from .vision_ocr import vision_read_path
        except ImportError:
            from vision_ocr import vision_read_path  # type: ignore

        def _resolve_src() -> Path | None:
            p = Path(local_path)
            if not p.is_absolute():
                p = Path("/opt/data") / local_path.lstrip("/")
            if p.is_file():
                return p
            alt = Path("/opt/data") / "cache" / Path(local_path).name
            if alt.is_file():
                return alt
            return None

        def _safe_name(name: str) -> str:
            out = []
            for ch in str(name or ""):
                o = ord(ch)
                if ch.isalnum() or ch in "._-() " or o > 127:
                    out.append(ch)
                else:
                    out.append("_")
            return ("".join(out).strip() or "document.bin")[:120]

        try:
            src = await asyncio.to_thread(_resolve_src)
            if src is None:
                self._as_flow("ingest_skip", reason="missing_source", path=local_path, thread_id=thread_id)
                return
            safe = _safe_name(file_name)
            dest_dir = inbound_root / thread_id
            dest_name = f"{uuid.uuid4().hex[:8]}_{safe}"
            dest = dest_dir / dest_name
            ingest_rel = f"inbound/{thread_id}/{dest_name}"
            await asyncio.to_thread(lambda: dest_dir.mkdir(parents=True, exist_ok=True))
            await asyncio.to_thread(shutil.copy2, src, dest)

            import aiohttp
            timeout = aiohttp.ClientTimeout(total=180)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                low = file_name.lower()
                ocr_text = ""
                if low.endswith((".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".txt", ".md", ".csv")):
                    # Prefer plain-text read for small text files (no OCR hop).
                    if low.endswith((".txt", ".md", ".csv")):
                        try:
                            raw = await asyncio.to_thread(dest.read_text, encoding="utf-8", errors="replace")
                            ocr_text = (raw or "").strip()
                        except Exception:
                            ocr_text = ""
                    elif low.endswith((".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")):
                        self._as_flow("vision_read_start", thread_id=thread_id, file=file_name, path=ingest_rel)
                        try:
                            ocr_text = await asyncio.to_thread(vision_read_path, str(dest))
                            self._as_flow(
                                "vision_read_done",
                                thread_id=thread_id,
                                file=file_name,
                                chars=len(ocr_text or ""),
                            )
                        except Exception as e:
                            ocr_text = ""
                            self._as_flow(
                                "vision_read_fail",
                                thread_id=thread_id,
                                file=file_name,
                                error=type(e).__name__,
                            )
                elif low.endswith((".docx", ".xlsx", ".xlsm", ".xls", ".pptx")):
                    # Office → ingest extract (same worker path as bare-attachment read).
                    try:
                        async with session.post(
                            f"{ingest_url}/v1/extract-text",
                            json={"path": f"/data/media/{ingest_rel}", "max_chars": 500000},
                        ) as ex_resp:
                            ex_body = await ex_resp.text()
                            try:
                                ex_json = json.loads(ex_body or "")
                                if isinstance(ex_json, dict):
                                    ocr_text = str(
                                        ex_json.get("text") or ex_json.get("markdown") or ""
                                    ).strip()
                            except Exception:
                                ocr_text = ""
                            self._as_flow(
                                "office_extract",
                                thread_id=thread_id,
                                file=file_name,
                                status=ex_resp.status,
                                chars=len(ocr_text or ""),
                            )
                    except Exception as e:
                        self._as_flow(
                            "office_extract_fail",
                            thread_id=thread_id,
                            file=file_name,
                            error=type(e).__name__,
                        )

                # Learn-skip from a prior secret turn: skip staging only (no refuse).
                if self._as_learn_skip_hit(thread_id, sender_id):
                    self._as_flow(
                        "learn_skip",
                        reason="prior_secret_turn",
                        thread_id=thread_id,
                        file=file_name,
                    )
                    try:
                        await asyncio.to_thread(dest.unlink)
                    except Exception:
                        pass
                    return
                # Content gate: user ask and/or SHORT extracted body that is a secret ask.
                # Long security docs (injection examples) are not short secret asks.
                # Office workbook cell text is DATA (same as archive members) — caption only.
                ask_blob = self._as_user_secret_ask_blob(
                    user_text, media if isinstance(media, dict) else {}
                )
                body_ask = ""
                if attachment_kind(file_name) not in {"archive", "office"}:
                    body_ask = self._as_short_secret_ask_body(ocr_text or "")
                gate_blob = "\n".join(x for x in (ask_blob, body_ask) if x)
                if gate_blob and (
                    self._as_secret_probe_text(gate_blob)
                    or self._as_classify_secret_refuse(gate_blob)
                ):
                    self._as_learn_skip_mark(thread_id, sender_id)
                    self._as_flow(
                        "learn_skip",
                        reason="classify_secret_content",
                        thread_id=thread_id,
                        file=file_name,
                    )
                    try:
                        await asyncio.to_thread(dest.unlink)
                    except Exception:
                        pass
                    return

                # Blank / whitespace-only extracts must never open Knowledge pending.
                if not self._as_meaningful_learn_text(ocr_text or ""):
                    self._as_flow(
                        "learn_skip",
                        reason="empty_extract",
                        thread_id=thread_id,
                        file=file_name,
                    )
                    try:
                        await asyncio.to_thread(dest.unlink)
                    except Exception:
                        pass
                    return

                # Archives are media-member reads only — never Knowledge pending.
                if attachment_kind(file_name) == "archive":
                    self._as_flow(
                        "learn_skip",
                        reason="archive_media_only",
                        thread_id=thread_id,
                        file=file_name,
                    )
                    try:
                        await asyncio.to_thread(dest.unlink)
                    except Exception:
                        pass
                    return

                # Classify owns learn eligibility: blank/risk whitepapers and bare
                # attachments without an explicit learn ask must not stage pending.
                if not self._as_classify_allows_knowledge_learn(
                    str(user_text or ""), file_name, ocr_text or ""
                ):
                    self._as_flow(
                        "learn_skip",
                        reason="classify_not_knowledge",
                        thread_id=thread_id,
                        file=file_name,
                    )
                    try:
                        await asyncio.to_thread(dest.unlink)
                    except Exception:
                        pass
                    return

                payload = {
                    "path": ingest_rel,
                    "document_name": file_name,
                    "thread_id": thread_id,
                    "source": "zalo",
                    "sender_id": sender_id,
                }
                alias_fn = getattr(self, "_as_secret_probe_alias", None)
                sender_name = ""
                if callable(alias_fn):
                    try:
                        sender_name = str(alias_fn({}, sender_id) or "").strip()
                    except Exception:
                        sender_name = ""
                if not sender_name:
                    for key in ("sender_name", "senderName", "dName", "displayName", "zaloName"):
                        v = (media or {}).get(key)
                        if isinstance(v, str) and v.strip():
                            sender_name = v.strip()
                            break
                if sender_name:
                    payload["sender_name"] = sender_name
                if ocr_text:
                    payload["text"] = ocr_text[:500000]
                if str(user_text or "").strip():
                    payload["caption"] = str(user_text).strip()[:4000]
                self._as_flow("learn_submit", thread_id=thread_id, file=file_name, path=ingest_rel)
                async with session.post(
                    f"{ingest_url}/v1/learn/submit",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as r3:
                    body = await r3.text()
                    if r3.status >= 300:
                        self._as_flow(
                            "learn_fail",
                            thread_id=thread_id,
                            status=r3.status,
                            error=(body or "")[:120],
                        )
                        return
                    try:
                        meta = json.loads(body or "{}")
                    except Exception:
                        meta = {}
                    if meta.get("blocked") or meta.get("status") == "blocked":
                        self._as_flow(
                            "learn_skip",
                            reason="ingest_secret_probe",
                            thread_id=thread_id,
                            file=file_name,
                        )
                        return
                    self._as_flow(
                        "learn_pending",
                        thread_id=thread_id,
                        file=file_name,
                        pending_id=meta.get("pending_id"),
                        notified=meta.get("notified"),
                        path=ingest_rel,
                    )
                    if meta.get("pending_id") and not meta.get("notified"):
                        logger.error(
                            "Zalo learn pending id=%s file=%s but admin notify failed "
                            "(check notify worker / ZALO_BRIDGE_URL / zalo_admin_users.txt)",
                            meta.get("pending_id"),
                            file_name,
                        )
        except Exception as e:
            logger.warning("Zalo file-pipeline error for %s: %s", file_name, e)
            self._as_flow("ingest_error", thread_id=thread_id, file=file_name, error=type(e).__name__)

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if getattr(self, "_as_autosend_wrong_thread", lambda *_: False)(chat_id, metadata):
            logger.info("Zalo: drop send to %s (not the requesting thread)", chat_id)
            return SendResult(success=True)  # ASSISTANT_AUTOSEND_v3
        if not (isinstance(metadata, dict) and metadata.get("as_skip_autosend")):
            content = await self._as_autosend_turn_files(chat_id, content, metadata)  # ASSISTANT_AUTOSEND_v5
            self._as_kick_late_autosend(chat_id, metadata)
        _red = getattr(self, "_as_redact_internal", None)
        if callable(_red):
            content = _red(content)  # ASSISTANT_PATH_REDACT_v1
        try:
            from secret_probe import is_blocked as _out_blocked
        except ImportError:
            from .secret_probe import is_blocked as _out_blocked  # type: ignore
        if _out_blocked(content or "", direction="output"):
            content = self._as_secret_refuse_line(content or "")
        _trim = getattr(self, "_as_knowledge_trim", None)
        if callable(_trim):
            content = _trim(content)  # ASSISTANT_KNOWLEDGE_CITE_v7
        skip_noise = isinstance(metadata, dict) and (
            metadata.get("zalo_admin_reply") or metadata.get("skip_outbound_filter")
        )
        if not skip_noise:
            notice = self._rewrite_gateway_user_notice(content)  # ASSISTANT_QUIET_SEND_v6
            if notice is not None:
                if notice == "":
                    logger.info("Zalo: drop approval/resume chatter")
                    return SendResult(success=True, message_id=None)
                content = notice
        if not skip_noise and self._is_gateway_noise(content):  # ASSISTANT_QUIET_SEND_v6
            logger.info("Zalo: drop gateway noise: %s", (content or "")[:100].replace("\n", " "))
            return SendResult(success=True, message_id=None)
        if self._as_is_media_ack_only(content):
            logger.info("Zalo: drop media ack line")
            return SendResult(success=True, message_id=None)
        # Same-turn mute after a media file was already delivered — never mute
        # schedule fire bodies, gate announces, or other skip_outbound_filter sends.
        meta = metadata if isinstance(metadata, dict) else {}
        allow_after_media = bool(
            meta.get("schedule_fire")
            or meta.get("scheduleFire")
            or meta.get("skip_outbound_filter")
            or meta.get("as_skip_autosend")
        )
        if (
            self._as_job_already_sent_file(chat_id)
            and (content or "").strip()
            and not allow_after_media
        ):
            low = (content or "").strip().lower()
            if not low.startswith("hiện chưa tạo") and "couldn't create" not in low and "couldn’t create" not in low:
                logger.info("Zalo: drop text after media result")
                return SendResult(success=True, message_id=None)
        # Re-check after autosend caption swap
        if not skip_noise and self._is_gateway_noise(content):
            return SendResult(success=True, message_id=None)
        if not (content or "").strip():
            return SendResult(success=True, message_id=None)
        # Persist turn to Valkey session SoT (not replica sessions.json).
        try:
            from .session_memory import append_turn
            from .turn_wait import real_thread_id
        except ImportError:
            from session_memory import append_turn  # type: ignore
            from turn_wait import real_thread_id  # type: ignore
        try:
            tid = real_thread_id(str(chat_id or ""))
            last_map = getattr(self, "_as_last_user_text", None) or {}
            user_prev = str(last_map.get(tid) or last_map.get(str(chat_id)) or "")
            tt = "group" if str(self._thread_types.get(tid) or "").lower() in {"group", "g"} else "user"
            append_turn(tid, tt, user_prev, str(content or ""))
        except Exception:
            pass
        if str(chat_id) not in self._as_hold_inflight:
            self._as_inflight_done(chat_id, metadata)  # ASSISTANT_INFLIGHT_v5
        dest_id = self._as_zalo_api_chat_id(chat_id)
        thread_type = self._thread_type_from_chat_id(chat_id, metadata)
        # Split long messages.
        _cap = 1800  # ASSISTANT_SEND_RETRY_v2
        try:
            _cap = int((__import__("os").environ.get("ZALO_SEND_MAX_CHARS") or "1800").strip() or "1800")
        except Exception:
            _cap = 1800
        _cap = max(400, min(_cap, 2000))
        chunks = self.truncate_message(content, max_length=_cap)
        last = None
        quote = None
        if isinstance(metadata, dict) and isinstance(metadata.get("quote"), dict):
            quote = metadata.get("quote")
        elif hasattr(self, "_pending_reply_quote"):
            quote = self._pending_reply_quote.pop(str(chat_id), None)
        quote = self._sanitize_send_quote(quote) if quote else None
        first = True
        for chunk in chunks:
            if not chunk.strip():
                continue
            if hasattr(self, "_as_zalo_plain_chunk"):
                chunk = self._as_zalo_plain_chunk(chunk)
            if not chunk.strip():
                continue
            body = {"threadId": dest_id, "threadType": thread_type, "text": chunk}
            used_quote = False
            if first and quote and len(chunk) <= 1400:  # ASSISTANT_SEND_RETRY_v2
                body["quote"] = quote  # ASSISTANT_REPLY_QUOTE
                used_quote = True
                logger.info("Zalo: reply-quote msgId=%s type=%s thread=%s", quote.get("msgId"), quote.get("msgType"), chat_id)
            first = False
            res = await self._as_with_dest_send_lock(dest_id, lambda b=body: self._post("/send", b))
            if res.get("error") and used_quote:
                err = str(res.get("error") or "")
                logger.warning("Zalo: reply-quote send failed (%s) — retry plain", err[:120])
                body.pop("quote", None)
                await asyncio.sleep(1.2)
                res = await self._as_with_dest_send_lock(dest_id, lambda b=body: self._post("/send", b))
            if res.get("error"):
                err = str(res.get("error") or "")
                retryable = True
                fn = getattr(self, "_as_send_retryable", None)
                if callable(fn):
                    retryable = bool(fn(err))
                if retryable:
                    logger.warning("Zalo: send failed (%s) — backoff retry", err[:120])
                    body.pop("quote", None)
                    await asyncio.sleep(1.5)
                    res = await self._as_with_dest_send_lock(dest_id, lambda b=body: self._post("/send", b))
            if res.get("error"):
                return SendResult(success=False, error=res["error"])
            last = res
            logger.info("Zalo: send ok thread=%s chars=%s", dest_id, len(chunk))
            await asyncio.sleep(0.2)
        msg_id = None
        if isinstance(last, dict):
            result = last.get("result")
            if isinstance(result, dict):
                # zca-js returns { message: { msgId }, attachment: [...] }
                msg = result.get("message")
                if isinstance(msg, dict) and msg.get("msgId") is not None:
                    msg_id = str(msg.get("msgId"))
                elif result.get("msgId") is not None:
                    msg_id = str(result.get("msgId"))
        self._as_compound_mark_delivered(chat_id)
        return SendResult(success=True, message_id=msg_id)

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        thread_type = self._thread_type_from_chat_id(chat_id, metadata)
        await self._post(
            "/typing",
            {"threadId": self._as_zalo_api_chat_id(chat_id), "threadType": thread_type},
        )


    def _bridge_shared_root(self) -> str:
        """Shared data root inside the container (/opt/data), not per-replica HERMES_HOME."""
        import os

        return (
            os.getenv("HERMES_SHARED_DATA")
            or "/opt/data"
        ).rstrip("/")

    def _bridge_local_path(self, path: str) -> str:  # ASSISTANT_HOST_PATH_v3
        """Map container paths → host paths; chmod so host bridge can read."""
        import os
        import shutil

        p = str(path or "")
        if not p or p.startswith(("http://", "https://")):
            return p
        host_root = (
            os.getenv("ZALO_HOST_DATA_DIR")
            or os.getenv("HERMES_HOST_DATA_DIR")
            or "/data/assistant"
        ).rstrip("/")
        # Prefer shared volume root — media/out lives on /opt/data, not replica home.
        cont_root = self._bridge_shared_root()
        try:
            out_dir = os.path.join(cont_root, "media", "out")
            os.makedirs(out_dir, mode=0o755, exist_ok=True)
            try:
                os.chmod(out_dir, 0o755)
                os.chmod(os.path.join(cont_root, "media"), 0o755)
            except Exception:
                pass
            if os.path.isfile(p) and not (p == cont_root or p.startswith(cont_root + "/")):
                dest = os.path.join(out_dir, os.path.basename(p) or "out.bin")
                shutil.copy2(p, dest)
                logger.info("Zalo: copied %s → %s for bridge send", p, dest)
                p = dest
            if os.path.isfile(p):
                try:
                    os.chmod(p, 0o644)
                except OSError:
                    dest = os.path.join(out_dir, "send-" + (os.path.basename(p) or "out.bin"))
                    shutil.copy2(p, dest)
                    os.chmod(dest, 0o644)
                    logger.info("Zalo: copied root-owned media to %s", dest)
                    p = dest
        except Exception as e:
            logger.warning("Zalo: could not stage/chmod file for bridge: %s", e)
        if p == cont_root or p.startswith(cont_root + "/"):
            mapped = host_root + p[len(cont_root) :]
            logger.info("Zalo: bridge path %s → %s", path, mapped)
            return mapped
        return p

    def _bridge_attachment_payload(self, chat_id, thread_type, file_path, caption=""):  # ASSISTANT_PATH_SEND_v4
        """hermes-zalo-plugin requires local host paths (not base64)."""
        import os
        import shutil

        payload = {
            "threadId": self._as_zalo_api_chat_id(chat_id),
            "threadType": thread_type,
            **caption_payload(caption),
        }
        p = str(file_path or "")
        try:
            from .autosend import existing_media_path
        except ImportError:
            from autosend import existing_media_path  # type: ignore
        resolved = existing_media_path(p)
        if resolved:
            p = resolved
        cont_root = self._bridge_shared_root()
        out_dir = os.path.join(cont_root, "media", "out")
        # Resolve missing/relative paths under workspace → stage into media/out
        if p and not os.path.isfile(p):
            candidates = [
                p,
                os.path.join(cont_root, "workspace", os.path.basename(p)),
                os.path.join(out_dir, os.path.basename(p)),
            ]
            for c in candidates:
                if c and os.path.isfile(c):
                    p = c
                    break
        if p and os.path.isfile(p):
            try:
                os.makedirs(out_dir, mode=0o755, exist_ok=True)
                if not p.startswith(out_dir + os.sep) and not p.startswith(out_dir + "/"):
                    staged = os.path.join(out_dir, os.path.basename(p) or "attach.bin")
                    shutil.copy2(p, staged)
                    p = staged
            except Exception as e:
                logger.warning("Zalo: stage to media/out failed: %s", e)
            host_path = self._bridge_local_path(p)
            payload["paths"] = [host_path]
            payload["path"] = host_path
            payload["fileName"] = os.path.basename(p) or "attach.bin"
            return payload
        logger.error("Zalo: local file missing for send: %s", file_path)
        payload["_missing"] = True
        payload["path"] = self._bridge_local_path(file_path)
        return payload

    def _as_attach_caption(self, caption) -> str:
        try:
            from .autosend import ATTACH_CAPTION_FALLBACK
        except ImportError:
            from autosend import ATTACH_CAPTION_FALLBACK  # type: ignore
        t = str(caption or "")
        return t if t.strip() else ATTACH_CAPTION_FALLBACK

    def _as_bridge_ok(self, res) -> bool:
        try:
            from .autosend import bridge_response_ok
        except ImportError:
            from autosend import bridge_response_ok  # type: ignore
        return bridge_response_ok(res)

    async def send_image(self, chat_id, image_url, caption=None, reply_to=None, metadata=None):
        return await self.send_image_file(chat_id, image_url, caption, reply_to, metadata)

    async def send_image_file(self, chat_id, image_path, caption=None, reply_to=None, metadata=None, **kwargs):
        try:
            from .autosend import VIDEO_EXTS
        except ImportError:
            from autosend import VIDEO_EXTS  # type: ignore
        raw = str(image_path or "")
        if any(raw.lower().endswith(ext) for ext in VIDEO_EXTS):
            return await self.send_video(chat_id, image_path, caption, reply_to, metadata, **kwargs)
        thread_type = self._thread_type_from_chat_id(chat_id, metadata)
        meta = metadata if isinstance(metadata, dict) else {}
        if not meta.get("as_claimed"):
            _claim = getattr(self, "_as_autosend_file_claim", None)
            if callable(_claim) and not _claim(image_path, chat_id):
                logger.info("Zalo: skip duplicate image %s", image_path)
                return SendResult(success=True)  # ASSISTANT_AUTOSEND_v5
        dest_id = self._as_zalo_api_chat_id(chat_id)
        payload = self._bridge_attachment_payload(
            dest_id, thread_type, image_path, self._as_attach_caption(caption)
        )
        quote = None
        if isinstance(metadata, dict) and isinstance(metadata.get("quote"), dict):
            quote = metadata.get("quote")
        elif hasattr(self, "_pending_reply_quote"):
            pq = getattr(self, "_pending_reply_quote", None)
            if isinstance(pq, dict):
                quote = pq.pop(str(chat_id), None)
        quote = self._sanitize_send_quote(quote) if quote else None
        if quote:
            payload["quote"] = quote
        if payload.pop("_missing", False):
            return SendResult(
                success=False,
                error=f"local file missing: {image_path} — write /opt/data/media/out via Omni /images/generations model image-gen",
            )
        res = await self._as_with_dest_send_lock(
            dest_id, lambda p=payload: self._post("/send-attachment", p)
        )
        if not self._as_bridge_ok(res):
            err = str((res or {}).get("error") or "send-attachment rejected")
            logger.info(f"[zalo] send-attachment fail {err[:160]}")
            logger.warning("Zalo: send-attachment fail dest=%s %s", dest_id, err[:200])
            return SendResult(success=False, error=err)
        host_path = str(payload.get("path") or "")
        logger.info(f"[zalo] send-attachment path {host_path}")
        logger.info("Zalo: send-attachment path %s", host_path)
        self._as_compound_mark_delivered(chat_id)
        return SendResult(success=True)


    async def send_document(self, chat_id, file_path, caption=None, file_name=None, reply_to=None, metadata=None, **kwargs):
        try:
            from .autosend import VIDEO_EXTS, looks_invalid_param
        except ImportError:
            from autosend import VIDEO_EXTS, looks_invalid_param  # type: ignore
        raw_path = str(file_path or "")
        if any(raw_path.lower().endswith(ext) for ext in VIDEO_EXTS):
            remuxed = self._as_remux_zalo_video(raw_path) or raw_path
            file_path = remuxed
            if not file_name:
                file_name = Path(str(remuxed)).name
        thread_type = self._thread_type_from_chat_id(chat_id, metadata)
        dest_id = self._as_zalo_api_chat_id(chat_id)
        payload = self._bridge_attachment_payload(
            dest_id, thread_type, file_path, self._as_attach_caption(caption)
        )
        if payload.pop("_missing", False):
            return SendResult(
                success=False,
                error=f"local file missing: {file_path} — write under /opt/data/media/out first",
            )
        if file_name and ("paths" in payload or "path" in payload):
            payload["fileName"] = file_name
        payload["threadId"] = dest_id
        meta = metadata if isinstance(metadata, dict) else {}
        if not meta.get("as_claimed"):
            _claim = getattr(self, "_as_autosend_file_claim", None)
            if callable(_claim) and not _claim(file_path, chat_id):
                logger.info("Zalo: skip duplicate file %s", file_name or file_path)
                return SendResult(success=True)
        if not meta.get("as_skip_outbound_av"):
            _scan = getattr(self, "_as_outbound_scan", None)
            if _scan:
                _verdict = await _scan(file_path, dest_id, file_name or payload.get("fileName"))
                if _verdict == "blocked":
                    return SendResult(success=False, error="av_blocked")
        res = await self._as_with_dest_send_lock(
            dest_id, lambda p=payload: self._post("/send-attachment", p)
        )
        if not self._as_bridge_ok(res):
            err = str((res or {}).get("error") or "send-attachment rejected")
            logger.info(f"[zalo] send-attachment fail {err[:160]}")
            logger.warning("Zalo: send-attachment fail dest=%s %s", dest_id, err[:200])
            if looks_invalid_param(err) and any(str(file_path).lower().endswith(ext) for ext in VIDEO_EXTS):
                retry_path = self._as_remux_zalo_video(str(file_path))
                if retry_path:
                    payload2 = self._bridge_attachment_payload(
                        dest_id, thread_type, retry_path, self._as_attach_caption(caption)
                    )
                    payload2.pop("_missing", None)
                    res2 = await self._as_with_dest_send_lock(
                        dest_id, lambda p=payload2: self._post("/send-attachment", p)
                    )
                    if self._as_bridge_ok(res2):
                        host_path = str(payload2.get("path") or retry_path)
                        logger.info(f"[zalo] send-attachment path {host_path}")
                        logger.info("Zalo: send-attachment path %s", host_path)
                        self._as_compound_mark_delivered(chat_id)
                        return SendResult(success=True)
            # Plain text attachments are often rejected by Zalo ("Tham số không hợp lệ").
            text_exts = (".txt", ".md", ".csv", ".log", ".json")
            if looks_invalid_param(err) and any(str(file_path).lower().endswith(ext) for ext in text_exts):
                from pathlib import Path as _Path
                try:
                    raw = _Path(str(file_path)).read_text(encoding="utf-8", errors="replace")
                except Exception:
                    raw = ""
                name = file_name or _Path(str(file_path)).name or "file.txt"
                body = (raw or "").strip()
                if len(body) > 3500:
                    body = body[:3500] + "\n…"
                msg = f"{name}\n\n{body}" if body else f"{name} (empty file)"
                logger.warning(
                    "Zalo: text attachment rejected — sending body as message name=%s",
                    name,
                )
                return await self.send(
                    chat_id,
                    msg,
                    metadata={**(meta or {}), "as_skip_autosend": True},
                )
            return SendResult(success=False, error=err)
        host_path = str(payload.get("path") or "")
        logger.info(f"[zalo] send-attachment path {host_path}")
        logger.info("Zalo: send-attachment path %s", host_path)
        self._as_compound_mark_delivered(chat_id)
        return SendResult(success=True)


    def _as_upload_item(self, data) -> dict:
        if not isinstance(data, dict):
            return {}
        r = data.get("result")
        if isinstance(r, list) and r:
            r = r[0]
        if isinstance(r, dict) and isinstance(r.get("result"), (list, dict)):
            r = r.get("result")
            if isinstance(r, list) and r:
                r = r[0]
        return r if isinstance(r, dict) else {}

    def _as_video_thumb(self, video_path: str) -> str:
        import shutil
        import subprocess
        from pathlib import Path

        src = Path(str(video_path or ""))
        parent = src.parent
        for name in ("clip-still.jpg", "clip-still.jpeg", "clip-still.png"):
            cand = parent / name
            try:
                if cand.is_file() and cand.stat().st_size > 100:
                    return str(cand)
            except OSError:
                continue
        dest = src.with_name((src.stem.replace(".zalo", "") or src.stem) + ".thumb.jpg")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return ""
        try:
            subprocess.run(
                [ffmpeg, "-y", "-i", str(src), "-frames:v", "1", "-q:v", "4", str(dest)],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except Exception:
            return ""
        try:
            if dest.is_file() and dest.stat().st_size > 100:
                return str(dest)
        except OSError:
            return ""
        return ""

    async def send_video(self, chat_id, video_path, caption=None, reply_to=None, metadata=None, **kwargs):
        staged = self._as_remux_zalo_video(str(video_path or "")) or video_path
        thread_type = self._thread_type_from_chat_id(chat_id, metadata)
        dest_id = self._as_zalo_api_chat_id(chat_id)
        payload = self._bridge_attachment_payload(
            dest_id, thread_type, staged, self._as_attach_caption(caption)
        )
        host_mp4 = str(payload.get("path") or "")
        thumb = self._as_video_thumb(str(staged))
        if thumb:
            tpay = self._bridge_attachment_payload(
                dest_id, thread_type, thumb, self._as_attach_caption(caption)
            )
            host_thumb = str(tpay.get("path") or "")
        else:
            host_thumb = ""
        if host_mp4 and host_thumb:
            up_v = await self._post(
                "/api/uploadAttachment",
                {"args": [[host_mp4], dest_id, thread_type]},
            )
            up_t = await self._post(
                "/api/uploadAttachment",
                {"args": [[host_thumb], dest_id, thread_type]},
            )
            item_v = self._as_upload_item(up_v)
            item_t = self._as_upload_item(up_t)
            video_url = str(
                item_v.get("fileUrl")
                or item_v.get("normalUrl")
                or item_v.get("videoUrl")
                or ""
            )
            thumb_url = str(
                item_t.get("thumbUrl")
                or item_t.get("normalUrl")
                or item_t.get("hdUrl")
                or item_t.get("fileUrl")
                or ""
            )
            width = int(item_v.get("width") or item_t.get("width") or 768)
            height = int(item_v.get("height") or item_t.get("height") or 512)
            duration = int(item_v.get("duration") or 4000)
            if duration and duration < 100:
                duration = duration * 1000
            if duration <= 0:
                duration = 4000
            if video_url and thumb_url:
                sent = await self._post(
                    "/api/sendVideo",
                    {
                        "args": [
                            {
                                "videoUrl": video_url,
                                "thumbnailUrl": thumb_url,
                                "duration": duration,
                                "width": width,
                                "height": height,
                                "msg": self._as_attach_caption(caption),
                            },
                            dest_id,
                            thread_type,
                        ]
                    },
                )
                if self._as_bridge_ok(sent):
                    logger.info(f"[zalo] send-attachment path {host_mp4}")
                    logger.info("Zalo: send-attachment path %s", host_mp4)
                    self._as_compound_mark_delivered(chat_id)
                    return SendResult(success=True)
                err = str((sent or {}).get("error") or "sendVideo rejected")
                logger.info(f"[zalo] send-attachment fail {err[:160]}")
                logger.warning("Zalo: sendVideo fail dest=%s %s", dest_id, err[:200])
        return await self.send_document(chat_id, staged, caption=caption, metadata=metadata)

    async def send_voice(self, chat_id, audio_path, caption=None, reply_to=None, metadata=None, **kwargs):
        thread_type = self._thread_type_from_chat_id(chat_id, metadata)
        if str(audio_path).startswith(("http://", "https://")):
            # A public m4a URL → real voice bubble via zca-js sendVoice.
            res = await self._post(
                "/send-voice",
                {"threadId": chat_id, "threadType": thread_type, "voiceUrl": audio_path},
            )
            if not res.get("error"):
                return SendResult(success=True)
        # Local audio file (or voiceUrl failed) → send as a playable file
        # attachment. zca-js sendVoice can't reliably HEAD the upload URL, so
        # we don't force a voice bubble for local files.
        res2 = await self._post(
            "/send-attachment",
            {"threadId": chat_id, "threadType": thread_type, "path": audio_path},
        )
        if res2.get("error"):
            return SendResult(success=False, error=res2["error"])
        return SendResult(success=True)

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        return {"name": str(chat_id), "type": "dm", "chat_id": str(chat_id)}

    # ── Extended Zalo actions (for agent tools / direct use) ────────────────

    async def react(self, chat_id, msg_id, icon="HEART", cli_msg_id=None, thread_type=None):
        """React to a message. icon = HEART/LIKE/HAHA/WOW/CRY/ANGRY/… or raw."""
        tt = thread_type or self._thread_types.get(str(chat_id), "user")
        return await self._post("/react", {
            "threadId": chat_id, "threadType": tt,
            "msgId": str(msg_id), "cliMsgId": str(cli_msg_id or msg_id), "icon": icon,
        })

    async def undo(self, chat_id, msg_id, cli_msg_id=None, thread_type=None):
        """Recall/undo one of our own messages."""
        tt = thread_type or self._thread_types.get(str(chat_id), "user")
        return await self._post("/undo", {
            "threadId": chat_id, "threadType": tt,
            "msgId": str(msg_id), "cliMsgId": str(cli_msg_id or msg_id),
        })

    async def reply(self, chat_id, text, quote, thread_type=None):
        """Send a text reply quoting a prior message (quote = SendMessageQuote)."""
        tt = thread_type or self._thread_types.get(str(chat_id), "user")
        return await self._post("/send", {
            "threadId": chat_id, "threadType": tt, "text": text, "quote": quote,
        })

    async def mention(self, chat_id, text, mentions, thread_type="group"):
        """Send a group message with @mentions = [{pos, uid, len}, …]."""
        return await self._post("/send", {
            "threadId": chat_id, "threadType": thread_type, "text": text, "mentions": mentions,
        })

    async def send_card(self, chat_id, user_id, phone_number=None, thread_type=None):
        tt = thread_type or self._thread_types.get(str(chat_id), "user")
        body = {"threadId": chat_id, "threadType": tt, "userId": str(user_id)}
        if phone_number:
            body["phoneNumber"] = str(phone_number)
        return await self._post("/send-card", body)

    # Friends
    async def friend_request(self, user_id, msg=None):
        return await self._post("/friend/request", {"userId": str(user_id), "msg": msg or "Xin chào"})

    async def friend_accept(self, user_id):
        return await self._post("/friend/accept", {"userId": str(user_id)})

    async def friend_reject(self, user_id):
        return await self._post("/friend/reject", {"userId": str(user_id)})

    async def list_friends(self):
        return await self._get("/friends")

    async def find_user(self, phone):
        return await self._get("/find-user", params={"phone": str(phone)})

    # Groups
    async def list_groups(self):
        return await self._get("/groups")

    async def group_create(self, name, members):
        return await self._post("/group/create", {"name": name, "members": [str(x) for x in members]})

    async def group_add(self, group_id, members):
        return await self._post("/group/add", {"groupId": str(group_id), "members": [str(x) for x in members]})

    async def group_remove(self, group_id, members):
        return await self._post("/group/remove", {"groupId": str(group_id), "members": [str(x) for x in members]})

    async def group_rename(self, group_id, name):
        return await self._post("/group/rename", {"groupId": str(group_id), "name": str(name)})

    async def group_deputy(self, group_id, members):
        return await self._post("/group/deputy", {"groupId": str(group_id), "members": [str(x) for x in members]})

    async def group_leave(self, group_id, silent=False):
        return await self._post("/group/leave", {"groupId": str(group_id), "silent": bool(silent)})

    # Poll
    async def poll_create(self, group_id, question, options, **extra):
        body = {"groupId": str(group_id), "question": str(question), "options": [str(o) for o in options]}
        body.update(extra)
        return await self._post("/poll/create", body)

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import aiohttp
        if not self._session or self._session.closed:
            return {"error": "no session"}
        try:
            async with self._session.get(
                f"{self.bridge_url}{path}",
                params=params or {},
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def call(self, method: str, *args) -> Dict[str, Any]:
        """Call ANY zca-js API method through the bridge passthrough.

        Covers the full zca-js surface beyond the first-class helpers above —
        forwardMessage, deleteMessage, sendVideo, sendLink, getGroupMembersInfo,
        getGroupChatHistory, createReminder, setMute, setPinnedConversations,
        block/unblock, votePoll, profile/settings, business catalog, etc.

        Pass args positionally exactly as zca-js documents them. Where a method
        takes a ThreadType, pass the string "user" or "group" (auto-converted).

        Example:
            await adapter.call("deleteMessage", {"data": {...}, "threadId": tid, "type": "user"})
            await adapter.call("getGroupMembersInfo", ["<uid1>", "<uid2>"])
            await adapter.call("setMute", {}, chat_id, "user")
        """
        return await self._post(f"/api/{method}", {"args": list(args)})


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def check_requirements() -> bool:
    """Zalo needs a bridge URL and aiohttp."""
    try:
        import aiohttp  # noqa
    except ImportError:
        return False
    if not _is_zalo_owner_replica():
        return False
    return bool((os.getenv("ZALO_PLUGIN_URL") or "").strip())


def validate_config(config) -> bool:
    extra = getattr(config, "extra", {}) or {}
    if not _is_zalo_owner_replica():
        return False
    if "ZALO_PLUGIN_URL" in os.environ:
        return bool((os.environ.get("ZALO_PLUGIN_URL") or "").strip())
    return bool(extra.get("bridge_url"))


def _env_enablement() -> Optional[dict]:
    """Seed PlatformConfig.extra from env so env-only setups show in status."""
    bridge_url = os.getenv("ZALO_PLUGIN_URL")
    if not bridge_url:
        return None
    extra = {
        "bridge_url": bridge_url.rstrip("/"),
        "bridge_token": os.getenv("ZALO_PLUGIN_TOKEN", ""),
    }
    result: Dict[str, Any] = {"extra": extra}
    home = os.getenv("ZALO_HOME_CHANNEL")
    if home:
        chat_id, thread_type = _parse_home_channel(home)
        if chat_id:
            result["home_channel"] = {"chat_id": chat_id, "chat_type": "group" if thread_type == "group" else "dm"}
    return result


def _probe_health(bridge_url: str, token: str) -> Optional[Dict[str, Any]]:
    """GET /health → {loggedIn, sessionDead, ...} or None if unreachable.

    Distinguishes the two failure modes the user must act on differently:
      - None            → bridge process is DOWN (service stopped / never started)
      - {loggedIn:False}→ bridge is UP but the Zalo session is logged out/expired
    """
    try:
        import urllib.request
        import json as _json
        req = urllib.request.Request(f"{bridge_url}/health")
        if token:
            req.add_header("x-bridge-token", token)
        with urllib.request.urlopen(req, timeout=5) as r:
            return _json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _bridge_cli_hint() -> str:
    """Best-effort name of the bridge CLI for copy-paste hints."""
    import shutil
    if shutil.which("hermes-zalo-plugin"):
        return "hermes-zalo-plugin"
    return "npx hermes-zalo-plugin"  # works without a global install


def _run_bridge_login() -> bool:
    """Run the bridge's QR login interactively (blocks until scanned/failed).

    Returns True on success. Uses the installed CLI if present, else npx.
    """
    import subprocess
    import shutil
    cli = "hermes-zalo-plugin" if shutil.which("hermes-zalo-plugin") else None
    cmd = [cli, "login"] if cli else ["npx", "hermes-zalo-plugin", "login"]
    try:
        # Inherit stdio so the ASCII QR renders and the user can scan it.
        return subprocess.run(cmd).returncode == 0
    except Exception as e:
        logger.warning("Zalo: could not launch bridge login: %s", e)
        return False


def _fetch_contacts(bridge_url: str, token: str) -> Optional[Dict[str, Any]]:
    """GET /contacts from the bridge → {groups:[{id,name}], friends:[{id,name}]}.
    Returns None if the bridge is unreachable or not logged in."""
    try:
        import urllib.request
        import json as _json
        req = urllib.request.Request(f"{bridge_url}/contacts")
        if token:
            req.add_header("x-bridge-token", token)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read().decode("utf-8"))
        if not data.get("success"):
            return None
        return {"groups": data.get("groups") or [], "friends": data.get("friends") or []}
    except Exception:
        return None


def _norm_text(s: str) -> str:
    """Lowercase + strip Vietnamese diacritics for forgiving name search."""
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D").lower().strip()


def _pick_ids(items: List[Dict[str, Any]], label: str, prompt_fn, print_fn) -> str:
    """Interactive picker over a possibly long {id,name} list.

    Commands at the prompt:
      <text>   search names (diacritic-insensitive); shows numbered matches
      <n,n,..> pick by number from the LAST shown list (accumulates)
      all      list everything (careful with long lists)
      done     show current picks
      <blank>  finish and return selected ids
    Raw ids can be pasted directly too.
    """
    print_fn(label)
    print_fn(f"   {len(items)} item(s). Type a name to search, numbers to pick, 'all' to list, blank to finish.")
    selected: Dict[str, str] = {}  # id -> name
    shown = items[: min(20, len(items))]  # default: first 20

    def _render(lst):
        if not lst:
            print_fn("   (no matches)")
            return
        for i, it in enumerate(lst, 1):
            mark = "✓" if str(it.get("id", "")) in selected else " "
            print_fn(f"   [{mark}] {i}. {it.get('name','?')}  ({it.get('id','')})")

    _render(shown)
    while True:
        raw = prompt_fn("search / numbers / 'all' / blank=done", default="")
        if raw is None:
            break
        raw = raw.strip()
        if not raw:
            break
        if raw.lower() == "all":
            shown = items
            _render(shown)
            continue
        if raw.lower() == "done":
            if selected:
                print_fn("   Selected: " + ", ".join(selected.values()))
            else:
                print_fn("   (nothing selected yet)")
            continue
        # If it looks like raw id(s) pasted directly (long digit strings) → add.
        toks = [t for t in raw.replace(" ", "").split(",") if t]
        if toks and all(t.isdigit() and len(t) >= 8 for t in toks):
            for t in toks:
                selected[t] = t
            print_fn("   Selected: " + ", ".join(selected.values()))
            continue
        # Pure short number / number-list → pick from current `shown`.
        if toks and all(t.isdigit() for t in toks):
            for t in toks:
                idx = int(t) - 1
                if 0 <= idx < len(shown):
                    it = shown[idx]
                    selected[str(it.get("id", ""))] = it.get("name", it.get("id", ""))
            print_fn("   Selected: " + (", ".join(selected.values()) or "(none)"))
            continue
        # Otherwise treat as a search query over names.
        q = _norm_text(raw)
        shown = [it for it in items if q in _norm_text(it.get("name", ""))]
        print_fn(f"   {len(shown)} match(es) for '{raw}':")
        _render(shown)
    return ",".join([i for i in selected.keys() if i])


def interactive_setup() -> None:
    """Interactive `hermes gateway setup` flow for Zalo."""
    from hermes_cli.setup import (
        prompt,
        prompt_yes_no,
        save_env_value,
        get_env_value,
        print_header,
        print_info,
        print_warning,
    )

    print_header("Zalo")
    print_info("Connect Hermes to a personal Zalo account via the zca-js bridge.")
    print_warning("zca-js is an UNOFFICIAL API. Use a secondary account; Zalo may lock automated accounts.")
    print_info("You must run the companion hermes-zalo-plugin Node service and log in via QR first.")
    print()

    existing = get_env_value("ZALO_PLUGIN_URL")
    bridge_url = prompt(
        "Bridge URL (e.g. http://127.0.0.1:8787)",
        default=existing or "http://127.0.0.1:8787",
    )
    if not bridge_url:
        print_warning("Bridge URL is required — skipping Zalo setup")
        return
    save_env_value("ZALO_PLUGIN_URL", bridge_url.strip().rstrip("/"))

    if prompt_yes_no("Set a bridge token (shared secret)?", False):
        token = prompt("Bridge token", password=True)
        if token:
            save_env_value("ZALO_PLUGIN_TOKEN", token)

    print()
    print_info("Access control: WHO may talk to the bot (Telegram-style)")
    print_info("Leave selections EMPTY to allow everyone / everywhere.")

    # Probe the bridge first so we can give a precise, actionable diagnosis
    # instead of a vague "offline/not logged in". Three states matter:
    #   1) DOWN          → service stopped: offer to start it (safe, no QR)
    #   2) LOGGED OUT    → session expired: offer to QR-login right now
    #   3) OK            → auto-list contacts for number-pick
    bridge = bridge_url.strip().rstrip("/")
    token = os.getenv("ZALO_PLUGIN_TOKEN", "")
    cli = _bridge_cli_hint()
    health = _probe_health(bridge, token)

    if health is None:
        # State 1: bridge process not reachable.
        print()
        print_warning(f"Bridge không phản hồi tại {bridge} (service đang tắt hoặc chưa khởi động).")
        print_info("Phiên đăng nhập (credentials) vẫn được giữ — chỉ cần bật lại service, KHÔNG cần quét QR lại.")
        if prompt_yes_no("Bật lại background service ngay bây giờ?", True):
            import subprocess, shutil
            svc_cli = "hermes-zalo-plugin" if shutil.which("hermes-zalo-plugin") else None
            svc_cmd = [svc_cli, "setup", "--service-only"] if svc_cli else ["npx", "hermes-zalo-plugin", "setup", "--service-only"]
            try:
                subprocess.run(svc_cmd)
            except Exception as e:
                print_warning(f"Không tự bật được service: {e}")
            # Re-probe after the attempt.
            import time as _t
            _t.sleep(2)
            health = _probe_health(bridge, token)
            if health is None:
                print_warning("Bridge vẫn chưa lên. Bật thủ công rồi chạy lại `hermes gateway setup`:")
                print_info(f"   {cli} setup --service-only        # nếu cài qua npm")
                print_info("   npm start                         # nếu chạy từ source")
        else:
            print_info("Bỏ qua. Khi nào muốn bật: " + f"{cli} setup --service-only  (hoặc `npm start`)")

    if health is not None and (not health.get("loggedIn") or health.get("sessionDead")):
        # State 2: bridge is up but the Zalo session is dead/logged out.
        print()
        print_warning("Bridge đang chạy nhưng phiên Zalo đã ĐĂNG XUẤT / hết hạn.")
        print_info("Cần đăng nhập lại bằng cách quét mã QR trong app Zalo (Zalo → + → Quét mã QR).")
        if prompt_yes_no("Quét QR đăng nhập lại ngay bây giờ?", True):
            if _run_bridge_login():
                print_info("✓ Đăng nhập lại thành công.")
                import time as _t
                _t.sleep(2)
                health = _probe_health(bridge, token)
            else:
                print_warning(f"Đăng nhập chưa xong. Chạy lại sau bằng:  {cli} login")
        else:
            print_info(f"Khi nào muốn đăng nhập lại:  {cli} login   (rồi chạy lại `hermes gateway setup`)")

    # Try to fetch a friendly id+name list from the bridge so the user can pick
    # by number instead of hunting for raw IDs. Falls back to manual entry.
    contacts = _fetch_contacts(bridge, token) if (health and health.get("loggedIn") and not health.get("sessionDead")) else None

    # A) Allowed senders (users).
    friends = (contacts or {}).get("friends") or []
    if friends:
        users_csv = _pick_ids(
            friends,
            "Restrict to specific USERS? Enter numbers (e.g. 1,3) or blank for everyone",
            prompt, print_info,
        )
    else:
        users_csv = prompt(
            "Allowed user IDs (comma-separated uidFrom, blank = everyone)",
            default=get_env_value("ZALO_ALLOWED_USERS") or "",
        )
    save_env_value("ZALO_ALLOWED_USERS", (users_csv or "").strip())

    # B) Allowed threads (groups + DMs).
    groups = (contacts or {}).get("groups") or []
    if groups:
        threads_csv = _pick_ids(
            groups,
            "Restrict to specific GROUPS/threads? Enter numbers or blank for everywhere",
            prompt, print_info,
        )
    else:
        threads_csv = prompt(
            "Allowed thread/group IDs (comma-separated, blank = everywhere)",
            default=get_env_value("ZALO_ALLOWED_THREADS") or "",
        )
    save_env_value("ZALO_ALLOWED_THREADS", (threads_csv or "").strip())

    # C) Group response mode. Only ask when the user picked specific groups.
    # If they left the group picker blank, that means "no groups" → set group
    # mode to "off" so the bot never replies in any group, even when @mentioned
    # (groups opt-in). DMs / 1-1 chats still work.
    if (threads_csv or "").strip():
        print_info("In GROUPS, when should the bot respond?")
        _gm_opts = [
            ("mention", "Chỉ khi được @nhắc tên hoặc trả lời tin của bot (khuyên dùng)"),
            ("all", "Mọi tin nhắn trong các nhóm được phép"),
            ("off", "Không bao giờ trong nhóm (chỉ chat riêng/DM)"),
        ]
        for i, (val, desc) in enumerate(_gm_opts, 1):
            print_info(f"   {i}. {val:<8} — {desc}")
        _cur_mode = get_env_value("ZALO_GROUP_MODE") or "mention"
        _cur_idx = next((str(i) for i, (v, _) in enumerate(_gm_opts, 1) if v == _cur_mode), "1")
        _pick = prompt("Chọn (1/2/3)", default=_cur_idx)
        try:
            mode = _gm_opts[int(str(_pick).strip()) - 1][0]
        except (ValueError, IndexError):
            # Fall back to accepting the literal word, else default.
            mode = (str(_pick) or "").strip().lower()
            if mode not in {"mention", "all", "off"}:
                mode = "mention"
        save_env_value("ZALO_GROUP_MODE", mode)
        print_info(f"   → {mode}")
    else:
        # No groups chosen → bot stays out of every group (DMs still work).
        save_env_value("ZALO_GROUP_MODE", "off")
        print_info("   → Không chọn nhóm nào → bot sẽ KHÔNG trả lời trong nhóm (kể cả khi @nhắc). Chat 1-1 (DM) vẫn hoạt động.")

    # Discoverability helper: log inbound ids so the user can add more later.
    if prompt_yes_no("Log sender/thread IDs of incoming messages (to find IDs later)?", False):
        save_env_value("ZALO_LOG_IDS", "true")
    else:
        save_env_value("ZALO_LOG_IDS", "false")

    retention = prompt(
        "Undo-cache retention in days — how long to keep the msgId→cliMsgId map "
        "on disk so message recall (thu hồi) works across bridge restarts "
        "(default 30, 0 to disable persistence)",
        default=get_env_value("ZALO_CLIMSG_RETENTION_DAYS") or "30",
    )
    if retention is not None and str(retention).strip() != "":
        try:
            save_env_value("ZALO_CLIMSG_RETENTION_DAYS", str(int(retention)))
        except ValueError:
            print_warning("Invalid number — keeping default 30 days")

    print()
    print_info("🔐 Access control — bot được phép làm những NHÓM hành động nào?")
    print_info("   Mức độ nguy hiểm tăng dần: read < send < interact < manage < destructive")
    _ag_opts = [
        ("read", "Xem — đọc tin, danh bạ, thông tin nhóm/bạn"),
        ("send", "Gửi — nhắn tin, ảnh, file, sticker, voice"),
        ("interact", "Tương tác — react, reply, vote/poll, gõ '...'"),
        ("manage", "Quản lý — thêm/xoá thành viên, đổi tên nhóm, kết bạn"),
        ("destructive", "NGUY HIỂM — giải tán nhóm, xoá tin, block, rời nhóm, đổi profile"),
    ]
    for i, (val, desc) in enumerate(_ag_opts, 1):
        print_info(f"   {i}. {val:<12} — {desc}")
    print_info("   6. custom       — Tự chọn TỪNG action cụ thể (chỉ những cái chọn mới chạy, còn lại CHẶN hết)")
    # Default to the currently-saved set, else the safe preset read,send,interact (1,2,3).
    _raw_groups = (get_env_value("ZALO_ALLOWED_ACTION_GROUPS") or "").strip()
    _raw_allowed = (get_env_value("ZALO_ALLOWED_ACTIONS") or "").strip()
    # Whitelist mode = an explicit allowlist exists AND no groups are enabled.
    _cur_custom = bool(_raw_allowed) and not _raw_groups
    _cur = _raw_groups or "read,send,interact"
    if _cur_custom:
        _cur_nums = "6"
    elif _cur.lower() == "all":
        _cur_nums = "1,2,3,4,5"
    else:
        _cur_set = {s.strip() for s in _cur.split(",") if s.strip()}
        _cur_nums = ",".join(str(i) for i, (v, _) in enumerate(_ag_opts, 1) if v in _cur_set) or "1,2,3"
    print_info("   Nhập số cách nhau bởi dấu phẩy (vd: 1,2,3), 'all' cho tất cả, hoặc 6 để tự chọn từng action.")
    _pick = prompt("Chọn nhóm hành động", default=_cur_nums)
    _pick = (str(_pick) or "").strip()

    _pick_nums = {t.strip() for t in _pick.split(",")}
    if "6" in _pick_nums or _pick.lower() == "custom":
        # ── Custom mode: whitelist-only. Pick specific actions; everything else
        #    is denied. We clear ZALO_ALLOWED_ACTION_GROUPS so no group passes by
        #    default, and put the picks in ZALO_ALLOWED_ACTIONS.
        print()
        print_info("Chế độ CUSTOM (whitelist) — chỉ những action được chọn mới chạy, tất cả còn lại bị chặn.")
        action_items = [
            {"id": name, "name": f"{name}  [{grp}]"}
            for name, grp in sorted(_ACTION_GROUP.items())
        ]
        # Seed the picker default selection from any currently-saved allowlist.
        _picked_csv = _pick_ids(
            action_items,
            f"Chọn action cho phép (trong {len(action_items)} API). "
            "Gõ tên để tìm (vd: send, group, poll), số để tick, 'all' để liệt kê, blank=xong",
            prompt, print_info,
        )
        allowed = [a.strip() for a in (_picked_csv or "").split(",") if a.strip()]
        save_env_value("ZALO_ALLOWED_ACTIONS", ",".join(allowed))
        save_env_value("ZALO_ALLOWED_ACTION_GROUPS", "")  # whitelist-only
        save_env_value("ZALO_DENIED_ACTIONS", "")          # not needed in whitelist mode
        # If any picked action is destructive, the bridge still needs the opt-in.
        has_destructive = any(_ACTION_GROUP.get(a) == "destructive" for a in allowed)
        if has_destructive:
            print_warning(
                "⚠️  Một số action đã chọn thuộc nhóm NGUY HIỂM (destructive). "
                "Bridge cần bật cờ riêng mới chạy được chúng."
            )
            allow_destructive = prompt_yes_no("Cho phép các action NGUY HIỂM đã chọn?", False)
            save_env_value("ZALO_ALLOW_DESTRUCTIVE", "true" if allow_destructive else "false")
        else:
            save_env_value("ZALO_ALLOW_DESTRUCTIVE", "false")
        print_info(f"   → custom allowlist ({len(allowed)} action): {', '.join(allowed) or '(trống — bot sẽ không làm gì)'}")
    else:
        if _pick.lower() == "all":
            groups_val = "all"
        else:
            chosen = []
            for tok in _pick.split(","):
                tok = tok.strip()
                if not tok or tok == "6":
                    continue
                try:
                    chosen.append(_ag_opts[int(tok) - 1][0])
                except (ValueError, IndexError):
                    if tok.lower() in {v for v, _ in _ag_opts}:
                        chosen.append(tok.lower())  # accept literal names too
            groups_val = ",".join(dict.fromkeys(chosen)) or "read,send,interact"
        save_env_value("ZALO_ALLOWED_ACTION_GROUPS", groups_val)
        save_env_value("ZALO_ALLOWED_ACTIONS", "")  # clear any leftover custom allowlist
        print_info(f"   → {groups_val}")

        # Destructive opt-in only matters when not in whitelist mode.
        _has_destructive_group = groups_val == "all" or "destructive" in groups_val
        if _has_destructive_group:
            print_warning(
                "⚠️  DESTRUCTIVE actions (giải tán nhóm, xoá tin, block, đổi profile) là "
                "KHÔNG THỂ HOÀN TÁC. Bất kỳ ai bot nghe đều có thể kích hoạt. Chỉ bật nếu "
                "bạn hoàn toàn tin tưởng mọi người được phép."
            )
            allow_destructive = prompt_yes_no("Cho phép các action NGUY HIỂM (destructive)?", False)
            save_env_value("ZALO_ALLOW_DESTRUCTIVE", "true" if allow_destructive else "false")
        else:
            save_env_value("ZALO_ALLOW_DESTRUCTIVE", "false")

    home = prompt(
        "Home thread for cron delivery (threadId or group:threadId, optional)",
        default=get_env_value("ZALO_HOME_CHANNEL") or "",
    )
    if home:
        save_env_value("ZALO_HOME_CHANNEL", home.strip())

    # ── Next steps: make sure the user always knows how to get a working bot ──
    print()
    print_info("─────────────────────────────────────────────")
    if health and health.get("loggedIn") and not health.get("sessionDead"):
        print_info("✓ Zalo đã sẵn sàng: bridge đang chạy và đã đăng nhập.")
        print_info("  Chạy:  hermes gateway   → bắt đầu nhận/gửi tin Zalo.")
    else:
        print_warning("⚠ Cấu hình Zalo đã lưu, NHƯNG bridge chưa sẵn sàng — bot sẽ chưa hoạt động.")
        print_info("  Bridge (Node service) phải ĐANG CHẠY và đã đăng nhập thì bot mới chạy được.")
        print_info(f"  • Kiểm tra:        curl {bridge}/health")
        print_info(f"  • Bật service:     {cli} setup --service-only   (đã login thì không cần QR)")
        print_info(f"  • Đăng nhập QR:    {cli} login                  (nếu bị đăng xuất)")
        print_info("  Xong rồi chạy:  hermes gateway")
    print_info("─────────────────────────────────────────────")


def is_connected() -> bool:
    """Lightweight check used by `hermes gateway status` (env-only)."""
    return bool(os.getenv("ZALO_PLUGIN_URL"))


def register(ctx):
    """Plugin entry point: called by the Hermes plugin system."""
    ctx.register_platform(
        name="zalo",
        label="Zalo",
        adapter_factory=lambda cfg: ZaloAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        required_env=["ZALO_PLUGIN_URL"],
        install_hint="Run the hermes-zalo-plugin Node service and `pip install aiohttp`",
        setup_fn=interactive_setup,
        env_enablement_fn=_env_enablement,
        cron_deliver_env_var="ZALO_HOME_CHANNEL",
        allowed_users_env="ZALO_ALLOWED_USERS",
        allow_all_env="ZALO_ALLOW_ALL_USERS",
        max_message_length=4000,
        emoji="",
        pii_safe=False,
        allow_update_command=True,
        platform_hint=(
            "You are chatting via Zalo (a Vietnamese messaging app). Zalo does "
            "not render markdown — use plain text only. The user likely writes "
            "in Vietnamese; reply in Vietnamese unless they switch. Keep replies "
            "concise and conversational. You can send images, files, stickers, "
            "and voice. Messages over ~4000 chars are auto-split."
        ),
    )
