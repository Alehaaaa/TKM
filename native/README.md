# Native plug-in builds

TKM releases contain prebuilt Micro Move and Depth Mover plug-ins for every
supported Maya/platform target. Maya selects the matching binary at runtime;
users do not need a compiler or the Maya devkit.

Each tool stores its release binaries under
`__builds__/<platform>-<architecture>/maya<year>/`. These are Maya C++ plug-ins,
not CPython extension modules, so Maya version is part of the binary ABI while
Python version is not.

The C++ sources remain next to their Python APIs under `TheKeyMachine/tools/`.
To make an explicit development build, configure this directory with CMake:

```shell
cmake -S native -B build/native \
  -DMAYA_VERSION=2025 \
  -DMAYA_DEVKIT_ROOT=/path/to/devkit \
  -DTKM_PLATFORM=linux \
  -DTKM_ARCH=x86_64
cmake --build build/native --config Release
```

This CMake project is the only supported build path. Maya never compiles native
code; it only selects and loads the matching binary shipped in the TKM release.

GitHub Actions runs the complete matrix when either plug-in source, this build
project, or the workflow changes. Pull requests validate the outputs. A push to
`main` also commits changed `__builds__` files back to `main`; local clones pick
up those generated files on their next normal pull.
