import subprocess
import os
import multiprocessing
import shutil
from pathlib import Path

def tools_configure(install_dir: Path, arches=None):
    print(f"Rust: tools_configure (install_dir={install_dir})")
    repo_root = Path(__file__).parent.parent

    # Check for vendor directory before writing config.toml to avoid catch-22
    if not (repo_root / "vendor").exists():
        cfg_path = repo_root / "config.toml"
        # Write bootstrap config.toml with vendor = false and bootstrap paths so it doesn't download stage0
        bootstrap_config = """# Suppresses a warning about tracking changes which we don't care about.
change-id = "ignore"
[build]
cargo = "/usr/sbin/cargo"
rustc = "/usr/sbin/rustc"
rustfmt = "/usr/sbin/rustfmt"
python = "python3"
vendor = false
"""
        cfg_path.write_text(bootstrap_config)
        
        try:
            print("Rust: vendor directory missing, running 'x.py vendor'...")
            env = os.environ.copy()
            env["CARGO"] = "/usr/sbin/cargo"
            # Run vendor command.
            subprocess.run(["python3", "x.py", "vendor"], cwd=repo_root, env=env, check=True)

            # Create .cargo/config.toml to point to the vendor directory
            cargo_config_dir = repo_root / ".cargo"
            cargo_config_dir.mkdir(exist_ok=True)
            (cargo_config_dir / "config.toml").write_text("""
[source.crates-io]
replace-with = "vendored-sources"

[source.vendored-sources]
directory = "vendor"
""")
        finally:
            # We will overwrite config.toml with the real one anyway
            pass
    
    # We use LLVM built in the tools directory
    llvm_config_path = install_dir / "bin" / "llvm-config"
    
    # config.toml for tools build
    config_content = f"""# Suppresses a warning about tracking changes which we don't care about.
change-id = "ignore"
profile = "dist"
[llvm]
download-ci-llvm = false
optimize = true
release-debuginfo = false
assertions = false
ninja = true
targets = "X86"
experimental-targets = ""
link-shared = true

enable-warnings = false
[llvm.build-config]
CMAKE_VERBOSE_MAKEFILE = "ON"
CMAKE_C_FLAGS_RELEASE = "-fmerge-all-constants -fprefetch-loop-arrays -ftree-vectorize -fgcse-las -frename-registers -fdevirtualize-at-ltrans -ffunction-sections -fdata-sections -Werror=lto-type-mismatch -fuse-linker-plugin -pipe --param l1-cache-size=32 --param l1-cache-line-size=64 --param l2-cache-size=4096"
CMAKE_CXX_FLAGS_RELEASE = "-fmerge-all-constants -fprefetch-loop-arrays -ftree-vectorize -fgcse-las -frename-registers -fdevirtualize-at-ltrans -ffunction-sections -fdata-sections -Werror=lto-type-mismatch -fuse-linker-plugin -pipe --param l1-cache-size=32 --param l1-cache-line-size=64 --param l2-cache-size=4096"
CMAKE_EXE_LINKER_FLAGS_RELEASE = "-Wl,-O1 -Wl,--as-needed -Wl,-z,pack-relative-relocs"
CMAKE_MODULE_LINKER_FLAGS_RELEASE = "-Wl,-O1 -Wl,--as-needed -Wl,-z,pack-relative-relocs"
CMAKE_SHARED_LINKER_FLAGS_RELEASE = "-Wl,-O1 -Wl,--as-needed -Wl,-z,pack-relative-relocs"
CMAKE_STATIC_LINKER_FLAGS_RELEASE = ""

[build]
build-stage = 2
test-stage = 2
build = "x86_64-unknown-linux-gnu"
host = ["x86_64-unknown-linux-gnu"]
target = ["x86_64-unknown-linux-gnu"]
cargo = "/usr/sbin/cargo"
rustc = "/usr/sbin/rustc"
rustfmt = "/usr/sbin/rustfmt"
description = "gentoo"
docs = false
compiler-docs = false
submodules = false
python = "python3"
locked-deps = true
vendor = true
extended = false
tools = []
verbose = 2
sanitizers = false
profiler = true
cargo-native-static = false

[install]
prefix = "{install_dir}"
sysconfdir = "etc"
docdir = "share/doc/rust"
bindir = "bin"
libdir = "lib"
mandir = "share/man"

[rust]
codegen-units-std = 1
optimize = true
debug = false
debug-assertions = false
debug-assertions-std = false
debuginfo-level = 0
debuginfo-level-rustc = 0
debuginfo-level-std = 0
debuginfo-level-tools = 0
debuginfo-level-tests = 0
backtrace = true
incremental = false
default-linker = "x86_64-pc-linux-gnu-cc"
channel = "stable"
rpath = true
verbose-tests = true
optimize-tests = true
codegen-tests = true
omit-git-hash = false
dist-src = false
remap-debuginfo = true
lld = false

deny-warnings = true
backtrace-on-ice = true
jemalloc = false
lto = "thin"

[dist]
src-tarball = false
compression-formats = ["xz"]
compression-profile = "balanced"

[target.x86_64-unknown-linux-gnu]
ar = "x86_64-pc-linux-gnu-ar"
cc = "x86_64-pc-linux-gnu-gcc"
cxx = "x86_64-pc-linux-gnu-g++"
linker = "x86_64-pc-linux-gnu-gcc"
ranlib = "x86_64-pc-linux-gnu-ranlib"
llvm-libunwind = "no"
llvm-config = "{llvm_config_path}"
"""
    (repo_root / "config.toml").write_text(config_content)

def tools_build(install_dir: Path):
    print(f"Rust: tools_build")
    repo_root = Path(__file__).parent.parent
    
    env = os.environ.copy()
    
    # Point to the LLVM library directory in tools install dir
    env["RUSTFLAGS"] = f"-Lnative={install_dir}/lib -Lnative={install_dir}/lib64"
    env["RUSTFLAGS_BOOTSTRAP"] = ""
    env["RUSTFLAGS_NOT_BOOTSTRAP"] = ""
    env["MAGIC_EXTRA_RUSTFLAGS"] = ""
    
    env["CFLAGS_x32"] = "-mx32"
    env["CFLAGS_x86"] = "-m32 -mfpmath=sse"
    env["CFLAGS_x86_64_unknown_linux_gnu"] = "-m64"
    env["CFLAGS_amd64"] = "-m64"
    
    # Use all CPUs for compilation
    make_jobs = multiprocessing.cpu_count()
    
    # We build compiler/rustc only
    subprocess.run(["python3", "x.py", "build", "compiler/rustc", "-j", str(make_jobs)], cwd=repo_root, env=env, check=True)

def tools_install(install_dir: Path):
    print(f"Rust: tools_install to {install_dir}")
    repo_root = Path(__file__).parent.parent
    
    env = os.environ.copy()
    subprocess.run(["python3", "x.py", "install"], cwd=repo_root, env=env, check=True)
