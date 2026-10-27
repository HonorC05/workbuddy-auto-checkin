#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =================================================================================
#  WorkBuddy 长效令牌（refreshToken）独立导出脚本  [v1.0]  (export_rt.py)
#
#  本文件为本仓库原创（MIT，版权归 HonorC05 (workbuddy-auto-checkin)）。
#  功能：仅在「已安装 WorkBuddy 桌面客户端并已登录」的本机（Windows）运行，从客户端
#  登录态文件解出 refreshToken 并打印到屏幕，供 workbuddy_auto.py 配置长效令牌使用。
#  解密只在本机进行，脚本不联网、不上传任何数据。
#
#  依赖：标准库 + cryptography（若缺失请先 `pip install cryptography`）。
#  用法：python export_rt.py
# =================================================================================
"""
WorkBuddy 长效令牌（refreshToken）独立导出脚本  [v1.0]
=================================================================
仅在你「已安装 WorkBuddy 桌面客户端并已登录」的本机（Windows）运行。
效果：从客户端登录态文件解出 refreshToken 并打印到屏幕。
- 解密只在本机进行，脚本不联网、不上传任何数据。
- 若客户端为 5.5.x（明文登录态）会直接读出；5.6.2+ 会通过 DPAPI/进程内存定位密钥解密。
- 依赖：标准库 + cryptography（若缺失请先 `pip install cryptography`）。

用法：
    python export_rt.py
然后把屏幕上打印出的那一长串 refreshToken 复制保存，用于配置 workbuddy_auto.py 的长效令牌。
"""
import base64
import hashlib
import json
import os
import re
import sys

try:
    import ctypes
    from ctypes import wintypes
except Exception:
    ctypes = None

_AAD_DOMAIN = b"WB-AAD\x00"
_FRAMING_CODE = {"file": 1, "field": 2, "record": 3, "stream": 4}
_STANDARD_FORMAT_ID = {"file": "WBEF1", "field": "WBEV1", "record": "WBER1", "stream": "WBES1"}


# ----------------------------- 基础工具 -----------------------------
def _b64_canonical_decode(value, field):
    if not isinstance(value, str):
        raise ValueError("%s 不是字符串" % field)
    decoded = base64.b64decode(value)
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError("%s 不是规范 base64" % field)
    return decoded


def _derive_at_rest_key(at_rest_secret_key):
    if not isinstance(at_rest_secret_key, str) or len(at_rest_secret_key) != 44:
        raise ValueError("atRestSecretKey 必须是 44 字符规范 base64（32 字节）")
    raw = _b64_canonical_decode(at_rest_secret_key, "atRestSecretKey")
    if len(raw) != 32:
        raise ValueError("atRestSecretKey 解码后必须是 32 字节")
    key = hashlib.sha256(at_rest_secret_key.encode("utf-8")).digest()
    key_id = hashlib.sha256(key).hexdigest()[:16]
    return key, key_id


def _build_field_aad(key_id):
    def encode_uint32(v):
        return v.to_bytes(4, "big")

    def encode_length_prefixed(s):
        b = s.encode("utf-8")
        return encode_uint32(len(b)) + b

    return b"".join([
        _AAD_DOMAIN,
        bytes([1]),
        encode_length_prefixed(_STANDARD_FORMAT_ID["field"]),
        encode_length_prefixed("sym-v1"),
        encode_uint32(1),
        encode_length_prefixed(key_id),
        bytes([_FRAMING_CODE["field"]]),
        bytes([0]),
        bytes([0]),
    ])


def _aes_gcm_decrypt(key, nonce, ciphertext, aad, auth_tag):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aes = AESGCM(key)
        return aes.decrypt(nonce, ciphertext + auth_tag, aad)
    except ImportError:
        pass
    try:
        from Crypto.Cipher import AES
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        cipher.update(aad)
        return cipher.decrypt_and_verify(ciphertext, auth_tag)
    except ImportError:
        pass
    raise RuntimeError("缺少 AES-GCM 后端，请先执行: pip install cryptography")


def _re_hex16(s):
    return bool(re.fullmatch(r"[0-9a-f]{16}", s))


def _parse_suite1_envelope(envelope_bytes):
    env = json.loads(envelope_bytes.decode("utf-8"))
    if not isinstance(env, dict):
        raise ValueError("信封必须是对象")
    if env.get("suite") != 1:
        raise ValueError("只支持 suite=1，实际 %r" % env.get("suite"))
    key_id = env.get("keyId")
    if not isinstance(key_id, str) or not _re_hex16(key_id):
        raise ValueError("envelope.keyId 非法")
    nonce = _b64_canonical_decode(env["nonce"], "nonce")
    auth_tag = _b64_canonical_decode(env["authTag"], "authTag")
    ct = env.get("ciphertext")
    ciphertext = b"" if (isinstance(ct, str) and ct == "") else _b64_canonical_decode(ct, "ciphertext")
    if len(nonce) != 12 or len(auth_tag) != 16:
        raise ValueError("nonce(12)/authTag(16) 长度错误")
    return key_id, nonce, ciphertext, auth_tag


# ----------------------------- Windows DPAPI -----------------------------
def _dpapi_unprotect(blob):
    if ctypes is None or not sys.platform.startswith("win"):
        raise OSError("DPAPI 仅在 Windows 可用")
    crypt32 = ctypes.windll.crypt32
    blob_len = len(blob)
    blob_buf = ctypes.create_string_buffer(blob, blob_len)

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    in_blob = DATA_BLOB(blob_len, blob_buf)
    out_blob = DATA_BLOB()
    res = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob))
    if not res:
        raise OSError("CryptUnprotectData 失败（可能不是当前用户/本机加密的 blob）")
    try:
        size = out_blob.cbData
        ptr = ctypes.cast(out_blob.pbData, ctypes.POINTER(ctypes.c_byte * size))
        data = bytes(ptr.contents[:size])
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return data


# ----------------------------- 进程内存扫描（5.6.2+） -----------------------------
_B64_CANDIDATE_RE = r"[A-Za-z0-9+/]{43}="
_B64_CANDIDATE_TEXT_RE = r"[A-Za-z0-9+/]{43}="
_B64_CANDIDATE_RE_UTF16 = rb"(?:[A-Za-z0-9+/]\x00){43}=\x00"
_MAX_MEMORY_CANDIDATES = 200000


def _list_workbuddy_pids():
    if ctypes is None or not sys.platform.startswith("win"):
        return []
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    TH32CS_SNAPPROCESS = 0x2
    INVALID_HANDLE_VALUE = ctypes.c_size_t(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]

    names = {"workbuddy.exe"}
    extra = os.environ.get("WORKBUDDY_PROCESS_NAMES", "")
    if extra:
        names |= {n.strip().lower() for n in extra.split(",") if n.strip()}

    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE_VALUE:
        return []
    pids = []
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            name = entry.szExeFile
            if name and name.lower() in names:
                pids.append(int(entry.th32ProcessID))
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return pids


def _iter_process_readable_regions(kernel32, handle, max_total_bytes=3 * 1024 * 1024 * 1024):
    class MEMORY_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                    ("AllocationProtect", wintypes.DWORD), ("PartitionId", wintypes.DWORD),
                    ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                    ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD),
                    ("PartitionId2", wintypes.DWORD)]

    kernel32.VirtualQueryEx.restype = ctypes.c_size_t
    kernel32.VirtualQueryEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
    kernel32.ReadProcessMemory.restype = wintypes.BOOL
    kernel32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    MEM_COMMIT = 0x1000
    PAGE_NOACCESS = 0x01
    PAGE_GUARD = 0x100
    CHUNK = 8 * 1024 * 1024
    total = 0
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION()
    while total < max_total_bytes:
        ret = kernel32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not ret:
            break
        base = mbi.BaseAddress or addr
        region_size = mbi.RegionSize or 0
        if region_size <= 0:
            break
        if mbi.State == MEM_COMMIT and mbi.Protect != PAGE_NOACCESS and not (mbi.Protect & PAGE_GUARD):
            read = 0
            while read < region_size and total < max_total_bytes:
                n = min(CHUNK, region_size - read)
                buf = ctypes.create_string_buffer(n)
                got = ctypes.c_size_t(0)
                ok = kernel32.ReadProcessMemory(handle, ctypes.c_void_p(base + read),
                                                buf, n, ctypes.byref(got))
                if ok and got.value:
                    data = buf.raw[:got.value]
                    total += len(data)
                    yield data
                    read += got.value
                else:
                    read = region_size
        nxt = base + region_size
        if nxt <= addr:
            break
        addr = nxt


def _key_candidate_matches(candidate_text, target_key_id):
    try:
        _, key_id = _derive_at_rest_key(candidate_text)
        return key_id == target_key_id
    except Exception:
        return False


def _extract_key_near_hits(data, hit_indexes, pattern_len, target_key_id, utf16=False):
    win = 4096
    checked = set()
    for h in hit_indexes:
        lo = max(0, h - win)
        hi = min(len(data), h + pattern_len + win)
        seg = data[lo:hi]
        if utf16:
            for m in re.finditer(_B64_CANDIDATE_TEXT_RE, seg.decode("utf-16-le", "ignore")):
                cand = m.group(0)
                if cand in checked:
                    continue
                checked.add(cand)
                if _key_candidate_matches(cand, target_key_id):
                    return cand
        else:
            for m in re.finditer(_B64_CANDIDATE_RE.encode("ascii", "ignore"), seg):
                cand = m.group(0).decode("ascii")
                if cand in checked:
                    continue
                checked.add(cand)
                if _key_candidate_matches(cand, target_key_id):
                    return cand
    return None


def _discover_at_rest_key_from_memory(target_key_id):
    if ctypes is None or not sys.platform.startswith("win"):
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        PROCESS_QUERY_INFORMATION = 0x0400
        PROCESS_VM_READ = 0x0010
        pattern = target_key_id.encode("ascii", "ignore")
        if len(pattern) != 16:
            return None
        utf16_pattern = target_key_id.encode("utf-16-le")
        b64_ascii_re = re.compile(_B64_CANDIDATE_RE.encode("ascii", "ignore"))
        b64_utf16_re = re.compile(_B64_CANDIDATE_RE_UTF16)
        pids = _list_workbuddy_pids()
        if not pids:
            return None
        seen_candidates = set()
        for pid in pids:
            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if not handle:
                continue
            try:
                for data in _iter_process_readable_regions(kernel32, handle):
                    for pat, is_u16 in ((pattern, False), (utf16_pattern, True)):
                        hits = []
                        start = 0
                        while True:
                            i = data.find(pat, start)
                            if i < 0:
                                break
                            hits.append(i)
                            start = i + 1
                        if hits:
                            key = _extract_key_near_hits(data, hits, len(pat), target_key_id, utf16=is_u16)
                            if key:
                                return key
                    for m in b64_ascii_re.finditer(data):
                        cand = m.group(0).decode("ascii")
                        if cand in seen_candidates:
                            continue
                        seen_candidates.add(cand)
                        if len(seen_candidates) > _MAX_MEMORY_CANDIDATES:
                            return None
                        if _key_candidate_matches(cand, target_key_id):
                            return cand
                    for m in b64_utf16_re.finditer(data):
                        cand = m.group(0).decode("utf-16-le")
                        if cand in seen_candidates:
                            continue
                        seen_candidates.add(cand)
                        if len(seen_candidates) > _MAX_MEMORY_CANDIDATES:
                            return None
                        if _key_candidate_matches(cand, target_key_id):
                            return cand
            finally:
                kernel32.CloseHandle(ctypes.c_void_p(handle))
        return None
    except Exception:
        return None


# ----------------------------- 定位 atRestSecretKey -----------------------------
def _candidate_to_at_rest_key(blob_or_text, target_key_id):
    text = None
    try:
        plain = _dpapi_unprotect(blob_or_text)
        text = plain.decode("utf-8", "replace").strip()
    except Exception:
        try:
            text = blob_or_text.decode("utf-8", "replace").strip()
        except Exception:
            text = None
    if not text:
        raise ValueError("无法解析候选密钥")
    text = text.strip().strip('"').strip("'")
    try:
        key, key_id = _derive_at_rest_key(text)
    except Exception:
        raise ValueError("候选不是合法 atRestSecretKey")
    if key_id != target_key_id:
        raise ValueError("keyId 不匹配")
    return text


def _at_rest_scan_roots():
    roots = []
    home = os.path.expanduser("~")
    for env in ("LOCALAPPDATA", "APPDATA"):
        base = os.environ.get(env, "")
        if base:
            roots.append(os.path.join(base, "CodeBuddyExtension", "Data"))
            roots.append(os.path.join(base, "WorkBuddyExtension", "Data"))
    roots.append(os.path.join(home, ".config", "CodeBuddyExtension", "Data"))
    roots.append(os.path.join(home, ".workbuddy"))
    seen = set()
    out = []
    for r in roots:
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out


_SKIP_DIRS = {"cache", "code cache", "gpucache", "file-tree", "extensions", "blob_storage",
              "indexeddb", "service worker", "logs", "crashpad", "swreporter", "network",
              "application cache", "shadercache", "webrtc", "videodecodestats"}


def _iter_candidate_files(root):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in _SKIP_DIRS]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                sz = os.path.getsize(p)
            except Exception:
                continue
            yield p, sz
            count += 1
            if count > 4000:
                return


def _discover_at_rest_key(target_key_id):
    env_key = os.environ.get("WORKBUDDY_ATREST_KEY")
    if env_key:
        _derive_at_rest_key(env_key)
        return env_key
    env_file = os.environ.get("WORKBUDDY_ATREST_KEY_FILE")
    if env_file and os.path.isfile(env_file):
        try:
            raw = open(env_file, "rb").read()
            return _candidate_to_at_rest_key(raw, target_key_id)
        except Exception:
            pass
    roots = _at_rest_scan_roots()
    DPAPI_MAGIC = b"\x01\x00\x00\x00\xd0\x8c\x9d\x0a"
    dpapi_tried = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        for path, size in _iter_candidate_files(root):
            if size > 256 * 1024:
                continue
            try:
                content = open(path, "rb").read()
            except Exception:
                continue
            idx = content.find(DPAPI_MAGIC)
            if idx < 0:
                continue
            blob = content[idx:]
            dpapi_tried += 1
            try:
                candidate = _candidate_to_at_rest_key(blob, target_key_id)
                if candidate:
                    return candidate
            except Exception:
                continue
    try:
        mem_key = _discover_at_rest_key_from_memory(target_key_id)
    except Exception:
        mem_key = None
    if mem_key:
        return mem_key
    raise RuntimeError(
        "无法在本机定位 WorkBuddy 5.6.2+ 的 atRestSecretKey"
        "（已尝试 %d 个 DPAPI blob 与运行中客户端进程内存扫描）。\n"
        "请确认 WorkBuddy 客户端已启动并登录，且本脚本与客户端在同一 Windows 用户下运行。"
        % dpapi_tried)


# ----------------------------- 信封解密 -----------------------------
def decrypt_access_token_field(raw_value):
    if isinstance(raw_value, str):
        return raw_value
    if isinstance(raw_value, dict) and raw_value.get("$wbEncrypted") == 1:
        envelope_b64 = raw_value.get("envelope")
        if not isinstance(envelope_b64, str):
            raise ValueError("加密信封缺少 envelope 字段")
        envelope_bytes = base64.b64decode(envelope_b64)
        if base64.b64encode(envelope_bytes).decode("ascii") != envelope_b64:
            raise ValueError("envelope 不是规范 base64")
        key_id, nonce, ciphertext, auth_tag = _parse_suite1_envelope(envelope_bytes)
        at_rest_secret_key = _discover_at_rest_key(key_id)
        key, _ = _derive_at_rest_key(at_rest_secret_key)
        aad = _build_field_aad(key_id)
        plaintext = _aes_gcm_decrypt(key, nonce, ciphertext, aad, auth_tag)
        return plaintext.decode("utf-8")
    raise ValueError("refreshToken 既不是明文也不是加密信封")


# ----------------------------- 定位登录态文件 -----------------------------
def _auth_candidates():
    home = os.path.expanduser("~")
    cands = []
    if sys.platform.startswith("win"):
        for env in ("LOCALAPPDATA", "APPDATA"):
            base = os.environ.get(env, "")
            if base:
                cands.append(os.path.join(base, "CodeBuddyExtension", "Data", "Public",
                                         "auth", "workbuddy-desktop.info"))
    elif sys.platform == "darwin":
        cands.append(os.path.join(home, "Library", "Application Support",
                                  "CodeBuddyExtension", "Data", "Public", "auth", "workbuddy-desktop.info"))
    else:
        cands.append(os.path.join(home, ".config", "CodeBuddyExtension", "Data", "Public",
                                  "auth", "workbuddy-desktop.info"))
    cands.append(os.path.join(home, ".workbuddy", "auth", "workbuddy-desktop.info"))
    return [p for p in cands if p]


# ----------------------------- 主流程 -----------------------------
def main():
    candidates = _auth_candidates()
    auth_path = None
    for p in candidates:
        if os.path.isfile(p):
            auth_path = p
            break
    if not auth_path:
        print("[错误] 未找到登录态文件 workbuddy-desktop.info，候选路径：")
        for p in candidates:
            print("  - " + p)
        print("请确认 WorkBuddy 桌面客户端已安装并登录。")
        sys.exit(1)

    print("[信息] 找到登录态文件：%s" % auth_path)
    try:
        with open(auth_path, "r", encoding="utf-8") as f:
            auth = json.load(f).get("auth", {})
    except Exception as e:
        print("[错误] 读取登录态文件失败：%s" % e)
        sys.exit(1)

    raw = auth.get("refreshToken")
    if raw is None:
        print("[错误] 登录态中未找到 refreshToken（可能未登录或登录态已失效）。")
        sys.exit(1)

    try:
        token = decrypt_access_token_field(raw)
    except Exception as e:
        print("[错误] 解密 refreshToken 失败：%s" % e)
        print("若提示缺少 cryptography，请先执行: pip install cryptography")
        sys.exit(1)

    if not (len(token) >= 200 and token.count(".") == 2):
        print("[警告] 解密结果不像标准 refreshToken（应是一长串含两个点的 base64）。")
        print("原始内容如下，请核对：")
        print(token)
        sys.exit(1)

    print("=" * 60)
    print("以下为你的长效令牌（refreshToken），请复制整段保存好：")
    print("-" * 60)
    print(token)
    print("-" * 60)
    print("（令牌等同账号钥匙，仅用于本助手在本机自动签到，请勿泄露给他人。）")


if __name__ == "__main__":
    main()
