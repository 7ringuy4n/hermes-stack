"""Safe archive extract: media members only. Supports zip/7z/rar/tar (+ optional password).

Nested archives and non-media members are skipped. No regex / no intent scanning.
"""
from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Callable

# Keep in sync with hermes zalo attachment media kinds.
TEXT_EXTS = (".txt", ".md", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml", ".xml")
OCR_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
OFFICE_EXTS = (".docx", ".doc", ".xlsx", ".xlsm", ".xls", ".pptx")
AV_EXTS = (
    ".mp4",
    ".webm",
    ".mov",
    ".m4v",
    ".mkv",
    ".avi",
    ".mp3",
    ".m4a",
    ".aac",
    ".wav",
    ".ogg",
    ".opus",
    ".flac",
)
ARCHIVE_EXTS = (
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".tgz",
)
# Nested members with these suffixes are never expanded again.
NESTED_SKIP_EXTS = (
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".tgz",
    ".gz",
    ".bz2",
    ".xz",
)

MAX_MEDIA_MEMBERS = 30
MAX_MEMBER_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 80 * 1024 * 1024


def archive_kind(path: Path | str) -> str:
    """Return zip|7z|rar|tar|none from filename suffixes (no content sniff)."""
    name = Path(path).name.lower()
    if name.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tgz")):
        return "tar"
    suf = Path(name).suffix
    if suf == ".zip":
        return "zip"
    if suf == ".7z":
        return "7z"
    if suf == ".rar":
        return "rar"
    if suf == ".tar":
        return "tar"
    return "none"


def member_basename(name: str) -> str:
    return str(name or "").replace("\\", "/").rsplit("/", 1)[-1].strip()


def member_path_safe(name: str) -> bool:
    """Reject absolute paths and parent traversal."""
    raw = str(name or "").replace("\\", "/")
    if not raw or raw.startswith("/") or raw.startswith("../") or "/../" in raw:
        return False
    if ".." in raw.split("/"):
        return False
    base = member_basename(raw)
    return bool(base) and base not in {".", ".."}


def is_media_member(name: str) -> bool:
    """True when the archive member is a processable media file (not nested archive)."""
    if not member_path_safe(name):
        return False
    base = member_basename(name).lower()
    if not base or "." not in base:
        return False
    if any(base.endswith(x) for x in NESTED_SKIP_EXTS):
        return False
    if base.endswith((".tar.gz", ".tar.bz2", ".tar.xz")):
        return False
    return any(base.endswith(x) for x in (TEXT_EXTS + OCR_EXTS + OFFICE_EXTS + AV_EXTS))


def _pwd_bytes(password: str | None) -> bytes | None:
    raw = str(password or "").strip()
    if not raw:
        return None
    return raw.encode("utf-8", errors="replace")


def _write_limited(src: Any, dest: Path, max_bytes: int) -> int:
    written = 0
    with dest.open("wb") as out:
        while written < max_bytes:
            chunk = src.read(min(65536, max_bytes - written))
            if not chunk:
                break
            out.write(chunk)
            written += len(chunk)
    return written


def _collect(
    names_sizes: list[tuple[str, int]],
    open_member: Callable[[str], Any],
    dest_dir: Path,
) -> dict[str, Any]:
    """Shared media-only write loop. open_member(name) -> binary file-like."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    total = 0
    for name, size in names_sizes:
        if not is_media_member(name):
            continue
        if size > MAX_MEMBER_BYTES:
            continue
        if total + max(size, 0) > MAX_TOTAL_BYTES:
            break
        base = member_basename(name)
        target = dest_dir / f"{len(written):02d}_{base}"
        try:
            with open_member(name) as src:
                got = _write_limited(src, target, MAX_MEMBER_BYTES)
        except Exception as e:
            err = str(e).lower()
            if "password" in err or "encrypted" in err or "bad password" in err:
                return {"ok": False, "reason": "password_required", "written": written}
            continue
        written.append(
            {
                "name": base,
                "path": str(target),
                "bytes": got,
                "archive_member": name,
            }
        )
        total += got
        if len(written) >= MAX_MEDIA_MEMBERS:
            break
    return {"ok": True, "reason": "", "written": written}


def _extract_zip(path: Path, dest_dir: Path, password: str | None) -> dict[str, Any]:
    pwd = _pwd_bytes(password)
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return {"ok": False, "reason": "bad_archive", "written": []}
    try:
        # Encrypted zip: flag_bits bit 0
        encrypted = any((i.flag_bits & 0x1) and not i.is_dir() for i in zf.infolist())
        if encrypted and not pwd:
            return {"ok": False, "reason": "password_required", "written": []}
        names_sizes: list[tuple[str, int]] = []
        for info in zf.infolist():
            if info.is_dir():
                continue
            names_sizes.append((info.filename or "", int(info.file_size or 0)))

        def open_member(name: str):
            return zf.open(name, "r", pwd=pwd)

        try:
            # Probe password on first media member if encrypted
            if encrypted and pwd:
                for n, _ in names_sizes:
                    if is_media_member(n):
                        try:
                            with zf.open(n, "r", pwd=pwd) as _:
                                pass
                        except Exception:
                            return {"ok": False, "reason": "bad_password", "written": []}
                        break
            return _collect(names_sizes, open_member, dest_dir)
        except RuntimeError as e:
            msg = str(e).lower()
            if "password" in msg or "encrypted" in msg:
                return {
                    "ok": False,
                    "reason": "bad_password" if pwd else "password_required",
                    "written": [],
                }
            return {"ok": False, "reason": "bad_archive", "written": []}
    finally:
        zf.close()


def _extract_7z(path: Path, dest_dir: Path, password: str | None) -> dict[str, Any]:
    try:
        import py7zr
    except ImportError:
        return {"ok": False, "reason": "unsupported", "written": []}
    pwd = str(password or "").strip() or None
    try:
        with py7zr.SevenZipFile(path, mode="r", password=pwd) as zf:
            if zf.needs_password() and not pwd:
                return {"ok": False, "reason": "password_required", "written": []}
            names_sizes: list[tuple[str, int]] = []
            for info in zf.list():
                if getattr(info, "is_directory", False):
                    continue
                names_sizes.append((info.filename or "", int(getattr(info, "uncompressed", 0) or 0)))

            # Extract selected media to memory then disk (py7zr API)
            dest_dir.mkdir(parents=True, exist_ok=True)
            written: list[dict[str, Any]] = []
            total = 0
            media_names = [n for n, sz in names_sizes if is_media_member(n) and sz <= MAX_MEMBER_BYTES]
            if not media_names:
                return {"ok": True, "reason": "", "written": []}
            try:
                targets = media_names[:MAX_MEDIA_MEMBERS]
                bio = zf.read(targets)
            except Exception as e:
                err = str(e).lower()
                if "password" in err or "encrypt" in err:
                    return {
                        "ok": False,
                        "reason": "bad_password" if pwd else "password_required",
                        "written": [],
                    }
                return {"ok": False, "reason": "bad_archive", "written": []}
            for name in targets:
                data = bio.get(name) if isinstance(bio, dict) else None
                if data is None:
                    continue
                raw = data.read() if hasattr(data, "read") else bytes(data or b"")
                if len(raw) > MAX_MEMBER_BYTES:
                    continue
                if total + len(raw) > MAX_TOTAL_BYTES:
                    break
                base = member_basename(name)
                target = dest_dir / f"{len(written):02d}_{base}"
                target.write_bytes(raw)
                written.append(
                    {
                        "name": base,
                        "path": str(target),
                        "bytes": len(raw),
                        "archive_member": name,
                    }
                )
                total += len(raw)
            return {"ok": True, "reason": "", "written": written}
    except Exception as e:
        err = str(e).lower()
        if "password" in err or "encrypt" in err:
            return {
                "ok": False,
                "reason": "bad_password" if pwd else "password_required",
                "written": [],
            }
        return {"ok": False, "reason": "bad_archive", "written": []}


def _extract_rar(path: Path, dest_dir: Path, password: str | None) -> dict[str, Any]:
    try:
        import rarfile
    except ImportError:
        return {"ok": False, "reason": "unsupported", "written": []}
    pwd = str(password or "").strip() or None
    try:
        rf = rarfile.RarFile(path)
    except Exception:
        return {"ok": False, "reason": "bad_archive", "written": []}
    try:
        if rf.needs_password() and not pwd:
            return {"ok": False, "reason": "password_required", "written": []}
        if pwd:
            rf.setpassword(pwd)
        names_sizes: list[tuple[str, int]] = []
        for info in rf.infolist():
            if info.is_dir():
                continue
            names_sizes.append((info.filename or "", int(info.file_size or 0)))

        def open_member(name: str):
            return rf.open(name)

        try:
            return _collect(names_sizes, open_member, dest_dir)
        except rarfile.PasswordRequired:
            return {"ok": False, "reason": "password_required", "written": []}
        except rarfile.BadRarFile:
            return {
                "ok": False,
                "reason": "bad_password" if pwd else "bad_archive",
                "written": [],
            }
        except Exception as e:
            err = str(e).lower()
            if "password" in err:
                return {
                    "ok": False,
                    "reason": "bad_password" if pwd else "password_required",
                    "written": [],
                }
            return {"ok": False, "reason": "bad_archive", "written": []}
    finally:
        try:
            rf.close()
        except Exception:
            pass


def _extract_tar(path: Path, dest_dir: Path, password: str | None) -> dict[str, Any]:
    # tar has no standard password; ignore password field
    name = path.name.lower()
    mode = "r:*"
    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        mode = "r:gz"
    elif name.endswith(".tar.bz2"):
        mode = "r:bz2"
    elif name.endswith(".tar.xz"):
        mode = "r:xz"
    elif name.endswith(".tar"):
        mode = "r:"
    try:
        tf = tarfile.open(path, mode=mode)
    except Exception:
        return {"ok": False, "reason": "bad_archive", "written": []}
    try:
        names_sizes: list[tuple[str, int]] = []
        for m in tf.getmembers():
            if not m.isfile():
                continue
            names_sizes.append((m.name or "", int(m.size or 0)))

        def open_member(member_name: str):
            f = tf.extractfile(member_name)
            if f is None:
                raise FileNotFoundError(member_name)
            return f

        return _collect(names_sizes, open_member, dest_dir)
    finally:
        tf.close()


def extract_media_members(
    archive_path: Path,
    dest_dir: Path,
    *,
    password: str | None = None,
) -> dict[str, Any]:
    """Extract media-only members. Returns {ok, reason, written}."""
    kind = archive_kind(archive_path)
    if kind == "zip":
        return _extract_zip(archive_path, dest_dir, password)
    if kind == "7z":
        return _extract_7z(archive_path, dest_dir, password)
    if kind == "rar":
        return _extract_rar(archive_path, dest_dir, password)
    if kind == "tar":
        return _extract_tar(archive_path, dest_dir, password)
    return {"ok": False, "reason": "unsupported", "written": []}


# Back-compat for callers expecting a list
def extract_media_members_list(
    archive_path: Path, dest_dir: Path, *, password: str | None = None
) -> list[dict[str, Any]]:
    got = extract_media_members(archive_path, dest_dir, password=password)
    if not got.get("ok"):
        return []
    return list(got.get("written") or [])
