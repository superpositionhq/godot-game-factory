"""Machine root for Python tools (task-check, task-try, ...); same rules as machine/lib/ggf-root.ps1.

Order: env GGF_ROOT, then "root" in the config file (env GGF_CONFIG, else %USERPROFILE%/.godot-game-factory/config.json),
then %USERPROFILE%/GodotWork.

Use from a script in the repo:
    sys.path.insert(0, os.path.join(<godot-game-factory>, "machine", "lib")); import ggfroot; ggfroot.root()
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def config_path():
    return os.environ.get("GGF_CONFIG") or os.path.join(os.path.expanduser("~"), ".godot-game-factory", "config.json")


def config():
    p = config_path()
    if os.path.isfile(p):
        with open(p, encoding="utf-8-sig") as f:
            try:
                return json.load(f)
            except ValueError as e:   # a path typed with single backslashes is the usual cause
                import sys
                sys.exit("%s is not valid JSON (%s): write a Windows path in it with doubled backslashes or forward "
                         "slashes" % (p, e))
    return {}


def root():
    if os.environ.get("GGF_ROOT"):
        return os.path.abspath(os.environ["GGF_ROOT"])
    r = config().get("root")
    if r:
        return os.path.abspath(r)
    return os.path.join(os.path.expanduser("~"), "GodotWork")


def ggb():
    """The release builds' private clones: "ggb" in the config file, else <root>/_build."""
    b = config().get("ggb")
    return os.path.abspath(b) if b else os.path.join(root(), "_build")


def engine():
    """The pinned engine, machine/godot.json (the one place that names it): version, flavor, feature ("4.7": what a
    game's project.godot names in config/features), exe, console_exe, templates, urls, sha512."""
    with open(os.path.join(os.path.dirname(_HERE), "godot.json"), encoding="utf-8") as f:
        return json.load(f)


def godot_dir():
    """The pinned engine's folder, <root>/godot/<version> (self-contained: its editor_data/ holds the editor's settings
    and editor_data/export_templates/<templates>/ the export templates)."""
    return os.path.join(root(), "godot", engine()["version"])


def godot_exe(console=True):
    """The editor exe, as ggf-root.ps1 Get-GGFGodot (keep the two in step): env GODOT_EDITOR, else "godot" in the
    config, else <root>/godot/<version>/<exe>. console=True gives the console wrapper beside it (it waits for the
    engine and passes its output and exit code on: what tools run); an editor without one is returned as it is.
    Exits naming what installs it when the exe is missing. Forward slashes."""
    import sys
    exe = os.environ.get("GODOT_EDITOR") or config().get("godot") or os.path.join(godot_dir(), engine()["exe"])
    exe = os.path.abspath(exe)
    if not os.path.isfile(exe):
        sys.exit("Godot %s is not at %s: run machine\\get-godot.ps1, or name the editor exe in \"godot\" in %s"
                 % (engine()["version"], exe, config_path()))
    if console and not exe.lower().endswith("_console.exe"):
        c = exe[:-4] + "_console.exe" if exe.lower().endswith(".exe") else ""
        if c and os.path.isfile(c):
            exe = c
    return exe.replace("\\", "/")


def android():
    """The Android toolchain machine/get-android.ps1 installs, as ggf-root.ps1 Get-GGFAndroid (keep the two in step),
    or None when any piece of it is missing (a mobile game is then still made, played, recorded and task-checked; only
    its APK is skipped). Its home is "android": {"home": ...} in the config, else <root>/android. Keys: home, jdk
    (JAVA_HOME), java, keytool, sdk (ANDROID_HOME), gradle_home (GRADLE_USER_HOME), godot (the engine version it was
    made for), build_tools, compile_sdk, ndk ("" when none), debug_keystore and release_keystore (each: path, user,
    password)."""
    home = (config().get("android") or {}).get("home")
    home = os.path.abspath(home) if home else os.path.join(root(), "android")
    try:
        with open(os.path.join(home, "toolchain.json"), encoding="utf-8-sig") as f:
            tc = json.load(f)
    except (OSError, ValueError):
        return None
    sdk = os.path.join(home, "sdk")
    need = [os.path.join(home, "jdk", "bin", "java.exe"),
            os.path.join(sdk, "cmdline-tools", "latest", "bin", "sdkmanager.bat"),
            os.path.join(sdk, "platform-tools", "adb.exe"),
            os.path.join(sdk, "build-tools", str(tc.get("build_tools")), "apksigner.bat"),
            os.path.join(sdk, "platforms", "android-%s" % tc.get("compile_sdk"), "android.jar")]
    if tc.get("ndk"):
        need.append(os.path.join(sdk, "ndk", str(tc["ndk"]), "source.properties"))
    out = {"home": home, "jdk": os.path.join(home, "jdk"), "java": need[0],
           "keytool": os.path.join(home, "jdk", "bin", "keytool.exe"), "sdk": sdk,
           "gradle_home": os.path.join(home, "gradle"), "godot": str(tc.get("godot") or ""),
           "build_tools": str(tc.get("build_tools") or ""), "compile_sdk": int(tc.get("compile_sdk") or 0),
           "ndk": str(tc.get("ndk") or "")}
    for k in ("debug", "release"):
        ks = tc.get(k + "_keystore") or {}
        path = os.path.join(home, "keystores", k + ".keystore")
        if not (ks.get("user") and ks.get("password")):
            return None
        need.append(path)
        out[k + "_keystore"] = {"path": path, "user": str(ks["user"]), "password": str(ks["password"])}
    if not all(os.path.isfile(p) for p in need):
        return None
    return out


def android_env(env=None):
    """What an Android export reads from the environment, added to env (default: a copy of os.environ), as ggf-root.ps1
    Set-GGFAndroidEnv: GRADLE_USER_HOME, JAVA_HOME, ANDROID_HOME, ANDROID_USER_HOME, ANDROID_PREFS_ROOT and the
    keystores (GODOT_ANDROID_KEYSTORE_DEBUG_* / _RELEASE_*: PATH, USER, PASSWORD). None when the toolchain is not
    installed."""
    a = android()
    if not a:
        return None
    env = dict(os.environ if env is None else env)
    env.update({"GRADLE_USER_HOME": a["gradle_home"], "JAVA_HOME": a["jdk"], "ANDROID_HOME": a["sdk"],
                "ANDROID_USER_HOME": os.path.join(a["home"], ".android"), "ANDROID_PREFS_ROOT": a["home"]})
    for k in ("debug", "release"):
        for f, name in (("path", "PATH"), ("user", "USER"), ("password", "PASSWORD")):
            env["GODOT_ANDROID_KEYSTORE_%s_%s" % (k.upper(), name)] = a[k + "_keystore"][f]
    return env


def ffmpeg():
    """ffmpeg.exe, as ggf-root.ps1 Get-GGFFfmpeg: env GGF_FFMPEG, else "ffmpeg" in the config, else the pinned copy
    machine/get-ffmpeg.ps1 puts in <root>/tools/ffmpeg-8.1.2, else the one on PATH. "" when there is none."""
    import shutil
    for p in (os.environ.get("GGF_FFMPEG"), config().get("ffmpeg"),
              os.path.join(root(), "tools", "ffmpeg-8.1.2", "ffmpeg-8.1.2-full_build", "bin", "ffmpeg.exe")):
        if p and os.path.isfile(p):
            return os.path.abspath(p)
    return shutil.which("ffmpeg") or ""


def org():
    """GitHub organisation (or user) owning godot-game-factory and the godot-game-<slug> repos: env GGF_ORG, else
    "github_org" in the config file (bootstrap.ps1 -Org writes it), else ""."""
    return (os.environ.get("GGF_ORG") or config().get("github_org") or "").strip()


def out():
    """Output root for packages: the creation replay's, and the dataset packager's commit maps, audit files and run
    lock (its zip goes next to the game repo unless --out). Env GGF_OUT, else "out" in the config file, else
    <root>/deliverables."""
    o = os.environ.get("GGF_OUT") or config().get("out")
    return os.path.abspath(o) if o else os.path.join(root(), "deliverables")


def check_free(path, what="this job"):
    """Exit when the drive holding path has less free than the floor (env GGF_MIN_FREE_GB, else "min_free_gb" in the
    config file, else 50 GB): a disk that fills mid-job corrupts the result. Returns the free GB."""
    import shutil
    import sys
    floor = float(os.environ.get("GGF_MIN_FREE_GB") or config().get("min_free_gb") or 50)
    p = os.path.abspath(path)
    while not os.path.exists(p) and os.path.dirname(p) != p:
        p = os.path.dirname(p)
    free = shutil.disk_usage(p).free / 2 ** 30
    if free < floor:
        sys.exit("%s: only %.1f GB free on %s (floor %.0f GB; GGF_MIN_FREE_GB / min_free_gb). Free space or move "
                 "--scratch (the task check and the task try) / GGF_OUT (packages) to another drive."
                 % (what, free, os.path.splitdrive(p)[0] or p, floor))
    return free


def computed_slots():
    """The hardware formula of ggf-root.ps1 Get-GGFComputedSlots (keep the two in step):
    heavy_slots = clamp(1..8, min((RAM GB - 6) // 6, logical cores // 4, (commit limit GB - 6) // 8)),
    gpu_slots = clamp(1..4, min(VRAM GB of the largest NVIDIA GPU // 4, heavy_slots - 1)); 1 without nvidia-smi."""
    import ctypes
    import subprocess

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    ms = MS()
    ms.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    ram, commit = ms.ullTotalPhys / 2 ** 30, ms.ullTotalPageFile / 2 ** 30
    heavy = int(max(1, min(8, (ram - 6) // 6, (os.cpu_count() or 4) // 4, (commit - 6) // 8)))
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True).stdout
        vram = max([int(x) for x in out.split() if x.strip().isdigit()] or [0])
    except OSError:
        vram = 0
    gpu = int(max(1, min(4, vram // 1024 // 4, heavy - 1))) if vram else 1
    return {"heavy_slots": heavy, "gpu_slots": gpu}


def slot_plan():
    """heavy_slots / gpu_slots in effect: the config's keys, else computed_slots()."""
    c = config()
    comp = None
    out = {}
    for k in ("heavy_slots", "gpu_slots"):
        try:
            v = int(c.get(k) or 0)
        except (TypeError, ValueError):
            v = 0
        if v <= 0:
            comp = comp or computed_slots()
            v = comp[k]
        out[k] = v
    return out
