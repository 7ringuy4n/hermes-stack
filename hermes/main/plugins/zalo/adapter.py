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
from datetime import datetime
from typing import Any, Dict, List, Optional

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


def _truthy(v) -> bool:
    return str(v if v is not None else "").strip().lower() in {"1", "true", "yes", "on"}


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

        self.bridge_url = (
            os.getenv("ZALO_PLUGIN_URL") or extra.get("bridge_url", "http://127.0.0.1:8787")
        ).rstrip("/")
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

    @property
    def name(self) -> str:
        return "Zalo"

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.bridge_token:
            h["x-bridge-token"] = self.bridge_token
        return h

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
        await self._close_session()

    async def _close_session(self) -> None:
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass
        self._session = None

    # ── Inbound: SSE loop ─────────────────────────────────────────────────

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

                headers = {}
                if self.bridge_token:
                    headers["x-bridge-token"] = self.bridge_token
                if self._last_event_id:
                    headers["Last-Event-ID"] = str(self._last_event_id)

                timeout = aiohttp.ClientTimeout(total=None, sock_read=None)
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
            await self._on_inbound_message(data)
            return
        # Reaction / undo / friend / group events: surface as a synthetic
        # context line for the agent (no media). These don't trigger a turn by
        # default unless a handler wants them; we log + optionally dispatch.
        if event_type in ("reaction", "undo", "friend_event", "group_event"):
            logger.info("Zalo: %s event %s", event_type, data)
            return

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
        admin_url = (os.getenv("ADMIN_API_URL") or "http://admin-api:8100").rstrip("/")
        token = (os.getenv("ADMIN_API_TOKEN") or "").strip()
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
                logger.warning("Zalo admin API rejected !zalo: %s", detail)
                reply = f"admin: {detail}"
            else:
                reply = (data.get("reply") or "").strip()
                reply_dm = bool(data.get("reply_dm"))
                group_ack = (data.get("group_ack") or "").strip()
        except Exception as e:
            logger.warning("Zalo admin command failed: %s: %s", type(e).__name__, e)
            reply = "admin API unavailable"
        # Group !zalo who → DM admin; other cmds stay in-thread unless API asks for DM.
        if reply_dm and sender_id:
            try:
                await self.send(
                    chat_id=str(sender_id),
                    content=reply or "(empty)",
                    metadata={"thread_type": "user"},
                )
                logger.info("Zalo admin: DM → %s (%s)", sender_id, raw.split()[:3])
            except Exception as e:
                logger.warning("Zalo admin DM failed: %s", type(e).__name__)
            if group_ack and thread_type == "group":
                try:
                    await self.send(
                        chat_id=str(thread_id),
                        content=group_ack,
                        metadata={"thread_type": "group"},
                    )
                except Exception as e:
                    logger.warning("Zalo admin group_ack failed: %s", type(e).__name__)
        elif reply:
            try:
                meta = {"thread_type": "group" if thread_type == "group" else "user"}
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
                "as_skip_timing": True,
                "as_skip_dest": True,
                "as_skip_autosend": True,
                "as_skip_inflight": True,
                "as_skip_quote": True,
            },
        )

    async def _zalo_rate_limit_drop(self, sender_id, thread_id, thread_type) -> bool:  # ASSISTANT_RATE_LIMIT_v4
        """True = drop inbound (too many messages). Announce at most once per window."""
        import os

        n, window = self._zalo_rate_limit_cfg()
        if n <= 0:
            return False
        sid = str(sender_id or "")
        tid = str(thread_id or "")
        if not sid or not tid:
            return False
        store = self._as_gate_store()
        if store is None:
            return False
        try:
            over, notify = store.rate_take(sid, tid, n, window)
        except Exception:
            return False
        if not over:
            return False
        logger.info(
            "Zalo: rate-limit drop sender=%s thread=%s type=%s via valkey",
            sid, tid, thread_type,
        )
        if notify:
            msg = (os.getenv("ZALO_RATE_LIMIT_MSG") or "").strip() or (
                "Bạn gửi hơi nhanh — mình trả lời lần lượt nhé. Đợi vài giây rồi gửi tiếp ạ."
            )
            try:
                await self._as_gate_announce(tid, thread_type, msg)
            except Exception as e:
                logger.warning("Zalo: rate-limit announce failed: %s", type(e).__name__)
        return True


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
            return bool(store.answering_try(str(thread_id or ""), cap, 45))
        except Exception:
            return True

    def _as_inflight_done(self, thread_id, metadata=None) -> None:  # ASSISTANT_INFLIGHT_v6
        meta = metadata if isinstance(metadata, dict) else {}
        if meta.get("as_skip_timing") or meta.get("as_skip_inflight"):
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
        print(f"[zalo] already answering wait thread={thread_id}", flush=True)
        try:
            announce = getattr(self, "_as_gate_announce", None)
            msg = "Bot đang trả lời tin này. Đợi xong rồi gửi tiếp nhé."
            if callable(announce):
                await announce(thread_id, thread_type, msg)
            else:
                await self.send(
                    chat_id=str(thread_id),
                    content=msg,
                    metadata={
                        "thread_type": "group" if thread_type == "group" else "user",
                        "as_skip_timing": True,
                        "as_skip_inflight": True,
                        "as_skip_dest": True,
                        "as_skip_autosend": True,
                        "as_skip_quote": True,
                    },
                )
        except Exception:
            pass
        return True


    def _as_secret_probe_text(self, text: str) -> bool:  # ASSISTANT_SECRET_PROBE_v1
        import re as _re
        t = (text or "").lower()
        if not t.strip():
            return False
        return bool(_re.search(
            r"secret|confidential|m[aậ]t\s*kh[aẩ]u|m[aậ]t\s*m[aã]|"
            r"openbao|vault token|\.env\b|api[_ ]?key|private[_ ]?key|"
            r"/opt/assistant|/data/hermes|n[oộ]i\s*b[oộ]\s*(server|m[aá]y)|"
            r"t[aà]i\s*li[eệ]u\s*m[aậ]t|h[oồ] s[oơ]\s*m[aậ]t|classified",
            t,
        ))

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

    async def _as_secret_probe_drop(self, m, sender_id, thread_id, thread_type, text=None) -> bool:  # ASSISTANT_SECRET_PROBE_v4
        """Hit = short refuse + notify admin. No LLM. No admin/authz bypass."""
        import json
        import os
        import urllib.request
        from datetime import datetime
        from zoneinfo import ZoneInfo

        orig = "" if text is None else str(text)
        if isinstance(m, dict) and not str(orig).strip():
            orig = str(m.get("text") or m.get("content") or m.get("message") or m.get("msg") or "")
        if not self._as_secret_probe_text(orig):
            return False
        sid = str(sender_id or "").strip() or "unknown"
        alias = self._as_secret_probe_alias(m, sid)
        who = f"user_id: {sid} ({alias})" if alias else f"user_id: {sid}"
        tz = ZoneInfo(os.getenv("TZ") or "Asia/Ho_Chi_Minh")
        stamp = datetime.now(tz).strftime("%H:%M %d/%m/%Y")
        words = " ".join((orig or "").split())[:240]
        notify = (os.getenv("NOTIFY_URL") or "http://notify:8092").rstrip("/")
        try:
            nbody = json.dumps(
                {
                    "title": "Confidential probe",
                    "body": f"{stamp}\n{who}\n{words}",
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
                content="Không cung cấp secret / tài liệu mật.",
                metadata={
                    "thread_type": "group" if thread_type == "group" else "user",
                    "as_skip_timing": True,
                },
            )
        except Exception:
            pass
        logger.info("Zalo: secret-probe deny sender=%s thread=%s", sid, thread_id)
        print(f"[zalo] secret-probe deny sender={sid} thread={thread_id}", flush=True)
        return True


































    def _as_is_knowledge_cite_ask(self, text: str) -> bool:  # ASSISTANT_KNOWLEDGE_CITE_v7
        t = (text or "").strip().lower()
        if not t or t.startswith("!zalo"):
            return False
        if "trích dẫn" in t or "trich dan" in t:
            return True
        if t == "cite" or t.startswith("cite ") or " cite " in t:
            return True
        if "tìm tài liệu" in t or "tim tai lieu" in t or "tìm tai lieu" in t:
            return True
        if "find doc" in t or t.startswith("find ") or t == "find":
            return True
        needles = ("tài liệu", "tai lieu", "tại liệu", "kiến thức", "kien thuc")
        tails = ("đang có", "dang co", "đã học", "da hoc")
        if any(n in t for n in needles) and any(x in t for x in tails):
            return True
        return False

    def _as_cite_topic(self, text: str) -> str:
        t = (text or "").lower()
        for d in (
            "trích dẫn", "trich dan", "tài liệu", "tai lieu", "tại liệu",
            "kiến thức", "kien thuc", "đang có", "dang co", "đã học", "da hoc",
            "cite", "theo", "tìm", "tim", "find", "docs", "documents", "document",
        ):
            t = t.replace(d, " ")
        return " ".join(t.split())

    def _as_knowledge_trim(self, content: str) -> str:  # ASSISTANT_KNOWLEDGE_CITE_v7
        """Block Hermes citation dumps (APA / 80 quotes / SKILL.md)."""
        t = content or ""
        low = t.lower()
        dump = False
        if len(t) > 700 and (
            "trích dẫn" in low or "trich dan" in low or "section" in low or "apa" in low
        ):
            dump = True
        if "apa citation" in low or "tổng ·" in low or ".bib" in low:
            dump = True
        if "skill.md" in low and ("trích" in low or "shimadzu" in low):
            dump = True
        if not dump:
            return t
        return (
            "Chỉ liệt kê tối đa 5 tài liệu đã học (không dump section/APA). "
            "Gõ !zalo learn list hoặc hỏi một từ khóa."
        )

    async def _as_cite_send(self, thread_id, thread_type, msg: str) -> None:
        await self.send(
            chat_id=str(thread_id),
            content=msg,
            metadata={
                "thread_type": "group" if thread_type == "group" else "user",
                "as_skip_timing": True,
                "as_skip_inflight": True,
                "as_skip_dest": True,
                "as_skip_autosend": True,
                "as_skip_quote": True,
            },
        )

    async def _as_knowledge_cite_reply(self, m, sender_id, thread_id, thread_type) -> bool:  # ASSISTANT_KNOWLEDGE_CITE_v7
        """True = handled (always skip Hermes on cite/list/find)."""
        text = (m.get("text") if isinstance(m, dict) else "") or ""
        if not self._as_is_knowledge_cite_ask(text):
            return False
        import json
        import os
        import urllib.parse
        import urllib.request
        url = (os.getenv("INGEST_URL") or "http://ingest:8099").rstrip("/")
        topic = self._as_cite_topic(text)
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
        self._as_mark_recv(thread_id)  # ASSISTANT_TIMING_FOOTER_v6
        self._as_autosend_remember_turn(thread_id, thread_type)  # ASSISTANT_AUTOSEND_v3







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
        media = m.get("media") if isinstance(m.get("media"), dict) else None
        pending_key = f"{thread_id}:{sender_id}"
        if chat_type == "group":
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

        # ASSISTANT_RATE_LIMIT_v4 — Valkey 1 / 10s; only after message is for the bot
        if await self._zalo_rate_limit_drop(sender_id, thread_id, thread_type):
            return
        # ASSISTANT_SECRET_PROBE_v5 — short refuse + notify admin; no LLM
        _sp = getattr(self, "_as_secret_probe_drop", None)
        if _sp and await _sp(m, sender_id, thread_id, thread_type, text):
            return

        # ASSISTANT_INFLIGHT_v6 — already answering (Valkey max 3 per chat); never block other chats
        if await self._as_inflight_drop(sender_id, thread_id, thread_type):
            return

        # ASSISTANT_KNOWLEDGE_CITE_v7 — short content titles, never paths/filenames
        if await self._as_knowledge_cite_reply(m, sender_id, thread_id, thread_type):
            return

        self._as_turn_handoff(thread_id)  # ASSISTANT_TIMING_FOOTER_v6

        if not (isinstance(media, dict) and media.get("url")):
            raw_q = m.get("quoted")
            if not isinstance(raw_q, dict):
                raw_q = m.get("quote")
            quote = raw_q if isinstance(raw_q, dict) else {}
            qc = quote.get("content")
            qtype = str(quote.get("msgType") or "")
            if isinstance(qc, dict) and (qc.get("href") or qtype.startswith("share.") or qtype.startswith("chat.photo")):
                params = qc.get("params") or {}
                if isinstance(params, str):
                    try:
                        params = json.loads(params)
                    except Exception:
                        params = {}
                ext = (params.get("fileExt") if isinstance(params, dict) else None) or (
                    (qc.get("title") or "bin").rsplit(".", 1)[-1]
                )
                kind = "image" if "photo" in qtype or "gif" in qtype else "file"
                media = {
                    "kind": kind,
                    "url": qc.get("href") or "",
                    "fileName": qc.get("title") or f"file.{ext}",
                    "ext": ext,
                    "mime": "image/jpeg" if kind == "image" else "application/octet-stream",
                    "size": (params.get("fileSize") if isinstance(params, dict) else 0) or 0,
                }
                m = dict(m)
                m["media"] = media
                logger.info("Zalo: media from quoted %s (%s)", qtype, media.get("fileName"))

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
                media_urls.append(local_path)
                media_types.append(media.get("mime") or "")
                message_type = mtype
        # ASSISTANT_FILE_PROMPT_v4 — filename-only / empty caption still reaches the agent
        if isinstance(media, dict) and media_urls:
            fn = str(media.get("fileName") or "file")
            raw = (text or "").strip()
            low = raw.lower()
            bare = (
                (not raw)
                or raw == fn
                or raw.strip("`") == fn
                or (raw.startswith("{") and "fileExt" in raw)
                or (
                    len(raw) < 96
                    and low.endswith((".xlsx", ".xls", ".docx", ".doc", ".pdf", ".txt", ".csv"))
                    and "tạo" not in low
                    and "xuất" not in low
                    and "tom tat" not in low
                    and "tóm tắt" not in low
                )
            )
            if bare:
                text = (
                    f"[Tin kèm file: {fn}]\n"
                    "Sau OCR/đọc: tóm tắt 3–6 ý chính (bullet ngắn). "
                    "Hỏi user muốn tìm thông tin gì trong tài liệu. "
                    "Cấm trích dài, cấm liệt kê từng section, cấm APA/MLA, cấm SKILL.md."
                )
                logger.info("Zalo: file-only prompt %s", fn)
        elif isinstance(media, dict) and media.get("url") and not media_urls:
            logger.warning("Zalo: media download empty %s", media.get("fileName") or "file")
            try:
                await self.send(
                    chat_id=str(thread_id),
                    content="Không lấy được file — gửi lại giúp mình.",
                    metadata={
                        "thread_type": "group" if thread_type == "group" else "user",
                        "as_skip_timing": True,
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
                    thread_id, sender_id, media_urls[0], media if isinstance(media, dict) else {}
                )
                if _blocked:
                    return

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
        await self.handle_message(event)


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

        url = media.get("url")
        kind = media.get("kind") or "other"
        ext = (media.get("ext") or "bin").lstrip(".")
        file_name = media.get("fileName") or f"zalo.{ext}"
        if not url:
            logger.warning("Zalo: media download skip — no url file=%s", file_name)
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

        # 2) Reply to one of the bot's messages.
        if self._own_id and str(m.get("quotedOwnerId") or "") == str(self._own_id):
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

        if not self._session or self._session.closed:
            return {"error": "no session"}
        try:
            async with self._session.post(
                f"{self.bridge_url}{path}",
                data=json.dumps(body),
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"error": str(e)}

    def _thread_type_from_chat_id(self, chat_id: str, metadata: Optional[Dict[str, Any]]) -> str:
        if metadata and metadata.get("thread_type") in {"user", "group"}:
            return metadata["thread_type"]
        _d = getattr(self, "_as_autosend_turn_dest", None)
        if callable(_d):
            _dest = _d() or {}
            if str(chat_id) == str(_dest.get("thread_id") or "") and _dest.get("thread_type") in {"user", "group"}:
                try:
                    self._thread_types[str(chat_id)] = _dest["thread_type"]
                except Exception:
                    pass
                return _dest["thread_type"]  # ASSISTANT_AUTOSEND_v3
        # Use the type remembered from inbound messages for this chat.
        remembered = self._thread_types.get(str(chat_id))
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
        num_map = {
            "1": "webchat",
            "32": "chat.photo",
            "31": "chat.voice",
            "44": "chat.video.msg",
            "46": "share.file",
            "49": "chat.gif",
        }
        mt = str(msg_type)
        if mt in num_map:
            mt = num_map[mt]
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
        t = str(err or "").lower()
        return any(
            x in t
            for x in (
                "lỗi không xác định",
                "loi khong xac dinh",
                "unknown",
                "too many",
                "try again",
                "timeout",
                "econnreset",
                "socket hang",
            )
        )

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




    def _is_gateway_noise(self, content: str) -> bool:  # ASSISTANT_QUIET_SEND_v3
        """Drop Hermes progress / approval / execute_code spam from chat."""
        t = (content or "").strip()
        if not t:
            return False
        low = t.lower()
        needles = (
            "⏳ working",
            "still working",
            "waiting on hermes",
            "⏳ waiting on",
            "gateway shutting down",
            "cannot connect to provider",
            "your current task will be interrupted",
            "auto-reconnect at",
            "provider may be slow",
            "provider may be overloaded",
            "the agent is back",
            "send any message after restart",
            "dangerous command",
            "requires approval",
            "execute_code",
            "eexecute_code",
            "script execution",
            "approval is required",
            "spawn subprocesses",
            "mutate files",
            "terminal command approval",
            '"title":',
        )
        if any(n in low for n in needles):
            return True
        if "approval" in low and ("command" in low or "execute" in low):
            return True
        if "⚠️" in t and ("approval" in low or "execute" in low):
            return True
        if t.startswith("{") and ("approval" in low or "execute_code" in low):
            return True
        if "base64" in low and ("placeholder" in low or "png" in low or "jpeg" in low):
            if len(t) > 400:
                return True
        return False


    def _as_timing_enabled(self) -> bool:  # ASSISTANT_TIMING_FOOTER_v6
        import os
        v = (os.getenv("ZALO_TIMING_FOOTER") or "0").strip().lower()
        return v in {"1", "true", "yes", "on"}

    def _as_timing_http(self, method: str, path: str, payload=None):  # ASSISTANT_TIMING_FOOTER_v6
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
            logger.debug("Zalo timing %s %s failed: %s", method, path, type(e).__name__)
            return {}

    def _as_clock(self, thread_id) -> dict:  # ASSISTANT_TIMING_FOOTER_v6
        tid = str(thread_id or "")
        if not hasattr(self, "_as_tclock"):
            self._as_tclock = {}
        st = self._as_tclock.get(tid)
        if not isinstance(st, dict):
            st = {}
            if tid:
                self._as_tclock[tid] = st
        return st

    def _as_mark_recv(self, thread_id) -> None:  # ASSISTANT_TIMING_FOOTER_v6
        import time
        tid = str(thread_id or "")
        if not tid:
            return
        t0 = time.time()
        st = self._as_clock(tid)
        st["t0"] = t0
        st["t_lookup"] = t0
        st["t_handoff"] = t0
        st["lookup_s"] = 0.0
        if not self._as_timing_enabled():
            return
        self._as_timing_http(
            "POST",
            "/v1/timing/start",
            {"thread_id": tid, "t0": t0, "t_handoff": t0, "recv_s": 0.0},
        )

    def _as_mark_lookup_start(self, thread_id) -> None:  # ASSISTANT_TIMING_FOOTER_v6
        import time
        st = self._as_clock(thread_id)
        if st and "t0" in st:
            st["t_lookup"] = time.time()

    def _as_mark_lookup_done(self, thread_id, seconds=None) -> None:  # ASSISTANT_TIMING_FOOTER_v6
        import time
        st = self._as_clock(thread_id)
        if not st:
            return
        now = time.time()
        if seconds is None:
            t_l = float(st.get("t_lookup") or st.get("t0") or now)
            seconds = max(0.0, now - t_l)
        st["lookup_s"] = max(0.0, float(seconds or 0.0))
        if self._as_timing_enabled() and st["lookup_s"] >= 0.001:
            self._as_timing_http(
                "POST",
                "/v1/timing/add",
                {"field": "workflow_s", "seconds": st["lookup_s"], "thread_id": str(thread_id or "")},
            )

    def _as_turn_handoff(self, thread_id) -> None:  # ASSISTANT_TIMING_FOOTER_v6
        import time
        tid = str(thread_id or "")
        if not tid:
            return
        now = time.time()
        st = self._as_clock(tid)
        t0 = float(st.get("t0") or now)
        st["t_handoff"] = now
        recv_s = max(0.0, float(st.get("t_lookup") or now) - t0)
        if not self._as_timing_enabled():
            return
        self._as_timing_http(
            "POST",
            "/v1/timing/start",
            {"thread_id": tid, "t0": t0, "t_handoff": now, "recv_s": recv_s},
        )

    def _as_fmt_s(self, x) -> str:
        try:
            v = max(0.0, float(x))
        except (TypeError, ValueError):
            v = 0.0
        return f"{v:.1f}"

    def _as_strip_fake_footers(self, content: str) -> str:
        import re as _re
        t = content or ""
        lines = t.rstrip().splitlines()
        dt = _re.compile(
            r"^_+\s*\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}(?:\s*[A-Za-z/_+\-0-9]+)?\s*_+$"
        )
        ict = _re.compile(r"^_+\s*.{0,40}\bICT\b.{0,20}\s*_+$", _re.I)
        clock = _re.compile(r"^⏱\b")
        while lines:
            last = lines[-1].strip()
            if not last:
                lines.pop()
                continue
            if dt.match(last) or ict.match(last) or clock.match(last):
                lines.pop()
                continue
            break
        return "\n".join(lines).rstrip()

    def _apply_timing_footer(self, content: str, chat_id, metadata=None) -> str:  # ASSISTANT_TIMING_FOOTER_v6
        """Strip invented footers. Append measured phases only if ZALO_TIMING_FOOTER is on.

          tiếp nhận     = Zalo → Hermes ready (local t_lookup - t0)
          tra cứu       = AV/OCR/tools before LLM (lookup_s + session workflow_s)
          LLM           = model time (session llm_s, else wall after handoff)
          tổng hợp+gửi  = sum of the three (never leftover dump)
        """
        import time
        t = self._as_strip_fake_footers(content)
        if not t.strip():
            return t
        meta = metadata if isinstance(metadata, dict) else {}
        if meta.get("as_skip_timing") or not self._as_timing_enabled():
            return t
        tid = str(chat_id or "")
        now = time.time()
        st = self._as_clock(tid) if tid else {}
        t0 = float(st.get("t0") or 0.0)
        t_lookup = float(st.get("t_lookup") or t0 or now)
        t_handoff = float(st.get("t_handoff") or t_lookup or now)
        recv = max(0.0, t_lookup - t0) if t0 else 0.0
        lookup_s = max(0.0, float(st.get("lookup_s") or 0.0))
        data = {}
        if tid:
            fin = self._as_timing_http("POST", f"/v1/timing/{tid}/finish", {})
            data = (fin or {}).get("timing") or {}
        if recv < 0.001:
            recv = max(0.0, float(data.get("recv_s") or 0.0))
        wf = max(lookup_s, float(data.get("workflow_s") or 0.0))
        llm = max(0.0, float(data.get("llm_s") or 0.0))
        after = max(0.0, now - t_handoff) if t_handoff > 0 else 0.0
        if llm < 0.05 and after > 0.2:
            llm = max(0.0, after - wf) if after > wf else after
        total = recv + wf + llm
        if total <= 0.0 and after > 0.0:
            llm = after
            total = recv + wf + llm
        if total <= 0.0:
            return t
        line = (
            f"⏱ {self._as_fmt_s(total)}s — tiếp nhận {self._as_fmt_s(recv)}s"
            f" · tra cứu {self._as_fmt_s(wf)}s · LLM {self._as_fmt_s(llm)}s"
            f" · tổng hợp+gửi {self._as_fmt_s(total)}s"
        )
        if tid and hasattr(self, "_as_tclock"):
            self._as_tclock.pop(tid, None)
        return t + "\n" + line


    def _as_autosend_roots(self):  # ASSISTANT_AUTOSEND_v3
        import os
        from pathlib import Path
        home = Path(os.getenv("HERMES_HOME") or "/opt/data")
        return (
            home / "media" / "out",
            home / "workspace",
        )

    def _as_autosend_ok_ext(self) -> tuple:  # ASSISTANT_AUTOSEND_v3
        return (
            ".txt", ".csv", ".md", ".pdf",
            ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
            ".rtf", ".odt", ".ods",
        )

    def _as_autosend_remember_turn(self, thread_id, thread_type=None) -> None:  # ASSISTANT_AUTOSEND_v3
        """Bind this turn's outbound (file + text) to the thread that asked."""
        tid = str(thread_id or "").strip()
        if not tid:
            return
        tt = "group" if str(thread_type or "").lower() in {"group", "g"} else "user"
        self._as_turn = {"thread_id": tid, "thread_type": tt}
        try:
            self._thread_types[tid] = tt
        except Exception:
            pass
        http = getattr(self, "_as_timing_http", None)
        if callable(http):
            http("POST", "/v1/turn/dest", {"thread_id": tid, "thread_type": tt})
            return
        try:
            import json as _json
            import os
            import urllib.request
            base = (os.getenv("SESSION_URL") or "http://session:8107").rstrip("/")
            req = urllib.request.Request(
                base + "/v1/turn/dest",
                data=_json.dumps({"thread_id": tid, "thread_type": tt}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2.0).read()
        except Exception:
            pass

    def _as_autosend_turn_dest(self) -> dict:  # ASSISTANT_AUTOSEND_v3
        local = getattr(self, "_as_turn", None)
        if isinstance(local, dict) and local.get("thread_id"):
            return local
        data = {}
        http = getattr(self, "_as_timing_http", None)
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
        dest = self._as_autosend_turn_dest()
        if not dest or not dest.get("thread_id"):
            return False
        return str(chat_id or "") != str(dest["thread_id"])

    def _as_autosend_file_fp(self, file_path) -> str:  # ASSISTANT_AUTOSEND_v3
        from pathlib import Path
        p = Path(str(file_path or ""))
        try:
            return f"{p.stat().st_size}:{p.name}"
        except OSError:
            return p.name or ""

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
        http = getattr(self, "_as_timing_http", None)
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
            "here is your file",
        )
        return any(n in low for n in needles)

    async def _as_autosend_turn_files(self, chat_id, content, metadata=None):  # ASSISTANT_AUTOSEND_v3
        """Send new office files from this turn; return caption to use for text."""
        import os
        import shutil
        import time
        from pathlib import Path

        meta = metadata if isinstance(metadata, dict) else {}
        if meta.get("as_skip_autosend"):
            return content
        dest_turn = self._as_autosend_turn_dest()
        tid = str((dest_turn or {}).get("thread_id") or chat_id or "")
        if dest_turn and dest_turn.get("thread_id") and str(chat_id or "") != dest_turn["thread_id"]:
            logger.info(
                "Zalo: skip autosend chat=%s (turn is %s)",
                chat_id,
                dest_turn.get("thread_id"),
            )
            return content
        if dest_turn.get("thread_type") in {"user", "group"}:
            meta = {**meta, "thread_type": dest_turn["thread_type"]}
        clock = (getattr(self, "_as_tclock", {}) or {}).get(tid) or {}
        t0 = float(clock.get("t0") or 0.0)
        if t0 <= 0:
            t0 = time.time() - 180
        ok_ext = self._as_autosend_ok_ext()
        found = []
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
                        if p.stat().st_mtime + 1 < t0:
                            continue
                    except OSError:
                        continue
                    found.append(p)
            except OSError:
                continue
        if not found:
            return content
        found.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        sent = 0
        blocked_n = 0
        out_dir = self._as_autosend_roots()[0]
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        caption = (os.getenv("ZALO_FILE_CAPTION") or "").strip() or "Đây là file của bạn."
        for src in found[:3]:
            dest = src
            try:
                if src.parent.resolve() != out_dir.resolve():
                    dest = out_dir / src.name
                    shutil.copy2(src, dest)
            except OSError:
                dest = src
            try:
                res = await self.send_document(
                    tid,
                    str(dest),
                    caption="",
                    file_name=dest.name,
                    metadata={
                        **meta,
                        "as_skip_autosend": True,
                        "as_skip_timing": True,
                    },
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
                    continue
                if ok:
                    sent += 1
                    flow = getattr(self, "_as_flow", None)
                    if callable(flow):
                        flow("zalo_send_file", thread_id=tid, file=dest.name, path=str(dest)[:160])
                    else:
                        print(f"[flow] stage=zalo_send_file thread_id={tid} file={dest.name}", flush=True)
            except Exception as e:
                logger.warning("Zalo autosend failed %s: %s", src.name, e)
        if sent <= 0:
            if blocked_n:
                return "File contains risks so it cannot be sent."
            return content
        return caption


    def _as_redact_internal(self, content: str) -> str:  # ASSISTANT_PATH_REDACT_v1
        """Strip server paths / secrets from outbound chat. Always on."""
        import re as _re
        t = content or ""
        if not t.strip():
            return t

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
        t = _re.sub(r"(?i)\s*trong\s+thư\s+mục\s*[`'\"]?\s*[`'\"]?", " ", t)
        t = _re.sub(r"[ \t]{2,}", " ", t)
        t = _re.sub(r"\n{3,}", "\n\n", t)
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
        print(line, flush=True)
        logger.info("%s", line)

    def _as_file_pipeline_enabled(self) -> bool:  # ASSISTANT_FILE_PIPELINE_v6
        import os
        v = (os.getenv("ZALO_FILE_PIPELINE") or "1").strip().lower()
        return v in {"1", "true", "yes", "on"}

    def _as_av_activated(self) -> bool:  # ASSISTANT_FILE_PIPELINE_v6
        """True when antivirus is on and reachable (ENABLE_ANTIVIRUS / AV_SCAN)."""
        import os
        import urllib.request
        flag = (os.getenv("AV_SCAN") or os.getenv("ENABLE_ANTIVIRUS") or "1").strip().lower()
        if flag in {"0", "false", "no", "off"}:
            return False
        url = (os.getenv("AV_GATEWAY_URL") or "http://av-gateway:8098").rstrip("/")
        try:
            with urllib.request.urlopen(url + "/health", timeout=2.0) as resp:
                import json as _json
                data = _json.loads(resp.read().decode("utf-8") or "{}")
            return bool(data.get("ok")) and bool(data.get("clamd"))
        except Exception:
            return False

    async def _as_av_gate(  # ASSISTANT_FILE_PIPELINE_v6
        self, thread_id, sender_id, local_path: str, media: dict
    ) -> bool:
        """Scan before LLM. True = abort turn (infected / required-and-failed)."""
        import asyncio
        import os
        import time
        from pathlib import Path

        if not local_path:
            return False
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
        mark = getattr(self, "_as_mark_lookup_start", None)
        if callable(mark):
            mark(thread_id)
        if not self._as_file_pipeline_enabled():
            self._as_flow("av_skip", reason="pipeline_off", file=fn, thread_id=thread_id)
            done = getattr(self, "_as_mark_lookup_done", None)
            if callable(done):
                done(thread_id)
            return False
        if not self._as_av_activated():
            self._as_flow("av_skip", reason="unavailable", file=fn, thread_id=thread_id)
            required = (os.getenv("AV_REQUIRED") or "0").strip().lower() in {"1", "true", "yes", "on"}
            done = getattr(self, "_as_mark_lookup_done", None)
            if callable(done):
                done(thread_id)
            if required:
                try:
                    await self.send(
                        chat_id=str(thread_id),
                        content="Chưa quét được file (antivirus chưa sẵn sàng). Gửi lại sau nhé.",
                        metadata={
                            "thread_type": "user",
                            "as_skip_timing": True,
                            "as_skip_inflight": True,
                        },
                    )
                except Exception:
                    pass
                return True
            self._as_enqueue_file_pipeline(thread_id, sender_id, local_path, media)
            return False

        av_url = (os.getenv("AV_GATEWAY_URL") or "http://av-gateway:8098").rstrip("/")
        session_id = f"zalo-{thread_id}"
        t0 = time.monotonic()
        try:
            src = Path(local_path)
            if not src.is_file():
                alt = Path("/opt/data") / "cache" / src.name
                src = alt if alt.is_file() else src
            data = await asyncio.to_thread(src.read_bytes) if src.is_file() else b""
            if not data:
                self._as_flow("av_skip", reason="empty_bytes", file=fn, thread_id=thread_id)
                done = getattr(self, "_as_mark_lookup_done", None)
                if callable(done):
                    done(thread_id)
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
                        done = getattr(self, "_as_mark_lookup_done", None)
                        if callable(done):
                            done(thread_id, time.monotonic() - t0)
                        self._as_enqueue_file_pipeline(thread_id, sender_id, local_path, media)
                        return False
                ready = False
                blocked = False
                for _ in range(40):
                    async with session.get(f"{av_url}/v1/sessions/{session_id}/ready") as r2:
                        if r2.status == 404:
                            break
                        if r2.status >= 300:
                            await asyncio.sleep(0.5)
                            continue
                        st = await r2.json(content_type=None)
                        if st.get("blocked"):
                            blocked = True
                            break
                        if st.get("ready"):
                            ready = True
                            break
                    await asyncio.sleep(0.5)
            elapsed = time.monotonic() - t0
            done = getattr(self, "_as_mark_lookup_done", None)
            if callable(done):
                done(thread_id, elapsed)
            if blocked:
                self._as_flow("av_blocked", thread_id=thread_id, file=fn, session_id=session_id, seconds=f"{elapsed:.2f}")
                try:
                    await self.send(
                        chat_id=str(thread_id),
                        content="File contains risks so it cannot be extracted to inspect information inside.",
                        metadata={
                            "thread_type": "user",
                            "as_skip_timing": True,
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
            self._as_enqueue_file_pipeline(thread_id, sender_id, local_path, media)
            return False
        except Exception as e:
            self._as_flow("av_error", thread_id=thread_id, file=fn, error=type(e).__name__)
            done = getattr(self, "_as_mark_lookup_done", None)
            if callable(done):
                done(thread_id)
            self._as_enqueue_file_pipeline(thread_id, sender_id, local_path, media)
            return False

    def _as_enqueue_file_pipeline(  # ASSISTANT_FILE_PIPELINE_v6
        self,
        thread_id,
        sender_id,
        local_path: str,
        media: dict,
    ) -> None:
        import asyncio

        if not self._as_file_pipeline_enabled():
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
    ) -> None:
        import asyncio
        import json
        import os
        import re
        import shutil
        import uuid
        from pathlib import Path

        if not thread_id or not local_path:
            return
        file_name = (media or {}).get("fileName") or Path(local_path).name or "document.bin"
        kind = (media or {}).get("kind") or "file"
        ingest_url = (os.getenv("INGEST_URL") or "http://ingest:8099").rstrip("/")
        ocr_url = (os.getenv("OCR_URL") or "http://ocr:8091").rstrip("/")
        inbound_root = Path(os.getenv("ASSISTANT_MEDIA_INBOUND", "/opt/data/media/inbound"))

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

        try:
            src = await asyncio.to_thread(_resolve_src)
            if src is None:
                self._as_flow("ingest_skip", reason="missing_source", path=local_path, thread_id=thread_id)
                return
            safe = re.sub(r"[^\w.\-() ]", "_", file_name)[:120].strip() or "document.bin"
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
                if low.endswith((".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")):
                    self._as_flow("ocr_start", thread_id=thread_id, file=file_name, path=ingest_rel)
                    try:
                        async with session.post(
                            f"{ocr_url}/v1/ocr",
                            json={"path": str(dest), "prompt": "Extract all text as markdown."},
                        ) as ocr_resp:
                            ocr_body = await ocr_resp.text()
                            try:
                                ocr_json = json.loads(ocr_body or "")
                                if isinstance(ocr_json, dict):
                                    ocr_text = str(ocr_json.get("text") or ocr_json.get("markdown") or "").strip()
                            except Exception:
                                ocr_text = ""
                            self._as_flow(
                                "ocr_done",
                                thread_id=thread_id,
                                file=file_name,
                                status=ocr_resp.status,
                                chars=len(ocr_text or ocr_body or ""),
                            )
                    except Exception as e:
                        self._as_flow("ocr_fail", thread_id=thread_id, file=file_name, error=type(e).__name__)

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
                self._as_flow("learn_submit", thread_id=thread_id, file=file_name, path=ingest_rel)
                async with session.post(
                    f"{ingest_url}/v1/learn/submit",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as r3:
                    body = await r3.text()
                    if r3.status >= 300:
                        self._as_flow("learn_fail", thread_id=thread_id, status=r3.status, error=(body or "")[:120])
                        return
                    try:
                        meta = json.loads(body or "{}")
                    except Exception:
                        meta = {}
                    self._as_flow(
                        "learn_pending",
                        thread_id=thread_id,
                        file=file_name,
                        pending_id=meta.get("pending_id"),
                        notified=meta.get("notified"),
                        path=ingest_rel,
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
        _red = getattr(self, "_as_redact_internal", None)
        if callable(_red):
            content = _red(content)  # ASSISTANT_PATH_REDACT_v1
        _trim = getattr(self, "_as_knowledge_trim", None)
        if callable(_trim):
            content = _trim(content)  # ASSISTANT_KNOWLEDGE_CITE_v7
        _trim = getattr(self, "_as_knowledge_trim", None)
        if callable(_trim):
            content = _trim(content)  # ASSISTANT_KNOWLEDGE_CITE_v6
        _trim = getattr(self, "_as_knowledge_trim", None)
        if callable(_trim):
            content = _trim(content)  # ASSISTANT_KNOWLEDGE_CITE_v5
        if not (isinstance(metadata, dict) and metadata.get("as_skip_autosend")):
            content = await self._as_autosend_turn_files(chat_id, content, metadata)  # ASSISTANT_AUTOSEND_v3
        content = self._apply_timing_footer(content, chat_id, metadata)  # ASSISTANT_TIMING_FOOTER_v6
        if self._is_gateway_noise(content):  # ASSISTANT_QUIET_SEND_v3
            logger.info("Zalo: drop gateway noise: %s", (content or "")[:100].replace("\n", " "))
            return SendResult(success=True, message_id=None)
        if self._is_gateway_noise(content):  # ASSISTANT_QUIET_SEND_v2
            logger.info("Zalo: drop gateway noise: %s", (content or "")[:100].replace("\n", " "))
            return SendResult(success=True, message_id=None)
        self._as_inflight_done(chat_id, metadata)  # ASSISTANT_INFLIGHT_v5
        if self._is_gateway_noise(content):  # ASSISTANT_QUIET_SEND
            logger.info("Zalo: drop gateway noise: %s", (content or "")[:100].replace("\n", " "))
            return SendResult(success=True, message_id=None)
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
            body = {"threadId": chat_id, "threadType": thread_type, "text": chunk}
            used_quote = False
            if first and quote and len(chunk) <= 1400:  # ASSISTANT_SEND_RETRY_v2
                body["quote"] = quote  # ASSISTANT_REPLY_QUOTE
                used_quote = True
                logger.info("Zalo: reply-quote msgId=%s type=%s thread=%s", quote.get("msgId"), quote.get("msgType"), chat_id)
            first = False
            res = await self._post("/send", body)
            if res.get("error") and used_quote:
                err = str(res.get("error") or "")
                logger.warning("Zalo: reply-quote send failed (%s) — retry plain", err[:120])
                body.pop("quote", None)
                await asyncio.sleep(1.2)
                res = await self._post("/send", body)
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
                    res = await self._post("/send", body)
            if res.get("error"):
                return SendResult(success=False, error=res["error"])
            last = res
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
        return SendResult(success=True, message_id=msg_id)

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        thread_type = self._thread_type_from_chat_id(chat_id, metadata)
        await self._post("/typing", {"threadId": chat_id, "threadType": thread_type})


    def _bridge_local_path(self, path: str) -> str:  # ASSISTANT_HOST_PATH_v2
        """Map container paths → host paths; chmod so host bridge can read."""
        import os
        import shutil

        p = str(path or "")
        if not p or p.startswith(("http://", "https://")):
            return p
        host_root = (
            os.getenv("ZALO_HOST_DATA_DIR")
            or os.getenv("HERMES_HOST_DATA_DIR")
            or "/data/hermes"
        ).rstrip("/")
        cont_root = (os.getenv("HERMES_HOME") or "/opt/data").rstrip("/")
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
                os.chmod(p, 0o644)
        except Exception as e:
            logger.warning("Zalo: could not stage/chmod file for bridge: %s", e)
        if p == cont_root or p.startswith(cont_root + "/"):
            mapped = host_root + p[len(cont_root):]
            logger.info("Zalo: bridge path %s → %s", path, mapped)
            return mapped
        return p

    def _bridge_attachment_payload(self, chat_id, thread_type, file_path, caption=""):  # ASSISTANT_BASE64_SEND_v3
        """Prefer base64 so host bridge never needs shared filesystem paths."""
        import base64
        import os
        import shutil

        payload = {
            "threadId": chat_id,
            "threadType": thread_type,
            "caption": caption or "",
        }
        p = str(file_path or "")
        cont_root = (os.getenv("HERMES_HOME") or "/opt/data").rstrip("/")
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
                if not p.startswith(out_dir + os.sep):
                    staged = os.path.join(out_dir, os.path.basename(p) or "attach.bin")
                    shutil.copy2(p, staged)
                    p = staged
            except Exception as e:
                logger.warning("Zalo: stage to media/out failed: %s", e)
            raw = open(p, "rb").read()
            payload["base64"] = base64.b64encode(raw).decode("ascii")
            payload["fileName"] = os.path.basename(p) or "attach.bin"
            logger.info(
                "Zalo: send-attachment base64 %s (%d bytes)",
                payload["fileName"],
                len(raw),
            )
            return payload
        logger.error("Zalo: local file missing for send: %s", file_path)
        payload["_missing"] = True
        payload["path"] = self._bridge_local_path(file_path)
        return payload

    async def send_image(self, chat_id, image_url, caption=None, reply_to=None, metadata=None):
        return await self.send_image_file(chat_id, image_url, caption, reply_to, metadata)

    async def send_image_file(self, chat_id, image_path, caption=None, reply_to=None, metadata=None, **kwargs):
        thread_type = self._thread_type_from_chat_id(chat_id, metadata)
        payload = self._bridge_attachment_payload(chat_id, thread_type, image_path, caption or "")
        if payload.pop("_missing", False):
            return SendResult(
                success=False,
                error=f"local file missing: {image_path} — write /opt/data/media/out/*.jpg or POST dispatcher /v1/image",
            )
        res = await self._post("/send-attachment", payload)
        if res.get("error"):
            return SendResult(success=False, error=res["error"])
        return SendResult(success=True)


    async def send_document(self, chat_id, file_path, caption=None, file_name=None, reply_to=None, metadata=None, **kwargs):
        thread_type = self._thread_type_from_chat_id(chat_id, metadata)
        payload = self._bridge_attachment_payload(chat_id, thread_type, file_path, caption or "")
        if payload.pop("_missing", False):
            return SendResult(
                success=False,
                error=f"local file missing: {file_path} — write under /opt/data/media/out first",
            )
        if file_name and "base64" in payload:
            payload["fileName"] = file_name
        _dest = getattr(self, "_as_autosend_turn_dest", lambda: {})()
        if isinstance(_dest, dict) and _dest.get("thread_id") and str(chat_id) != str(_dest["thread_id"]):
            logger.info(
                "Zalo: retarget file %s → %s type=%s",
                chat_id,
                _dest.get("thread_id"),
                _dest.get("thread_type"),
            )
            chat_id = _dest["thread_id"]
            payload["threadId"] = chat_id
            if _dest.get("thread_type") in {"user", "group"}:
                payload["threadType"] = _dest["thread_type"]
                metadata = {**(metadata or {}), "thread_type": _dest["thread_type"]}
        _claim = getattr(self, "_as_autosend_file_claim", None)
        if callable(_claim) and not _claim(file_path, chat_id):
            logger.info("Zalo: skip duplicate file %s", file_name or file_path)
            return SendResult(success=True)  # ASSISTANT_AUTOSEND_v3
        if not (isinstance(metadata, dict) and metadata.get("as_skip_outbound_av")):  # ASSISTANT_AUTOSEND_v3
            _scan = getattr(self, "_as_outbound_scan", None)
            if _scan:
                _verdict = await _scan(file_path, chat_id, file_name or payload.get("fileName"))
                if _verdict == "blocked":
                    return SendResult(success=False, error="av_blocked")
        res = await self._post("/send-attachment", payload)
        if res.get("error"):
            return SendResult(success=False, error=res["error"])
        return SendResult(success=True)


    async def send_video(self, chat_id, video_path, caption=None, reply_to=None, metadata=None, **kwargs):
        return await self.send_document(chat_id, video_path, caption=caption, metadata=metadata)

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
    return bool(os.getenv("ZALO_PLUGIN_URL"))


def validate_config(config) -> bool:
    extra = getattr(config, "extra", {}) or {}
    return bool(os.getenv("ZALO_PLUGIN_URL") or extra.get("bridge_url"))


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
