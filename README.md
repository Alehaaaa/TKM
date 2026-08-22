# TheKeyMachine Native Plug-ins

This branch is an independent build lane for TheKeyMachine's native Maya plug-ins.
It intentionally contains only the files needed to compile and package native
plug-in binaries:

- `.github/workflows/build-plugins.yml`
- `native_plugins/`
- `TheKeyMachine/tools/depth_mover/plugin.cpp`
- `TheKeyMachine/tools/micro_move/plugin.cpp`

The full Python toolset, UI, icons, docs, release metadata, and generated
`__builds__` binaries live on `main`. When this branch builds successfully, the
workflow checks out `origin/main`, replaces only the generated native build
folders there, and pushes those binaries back to `main`.

Website: https://alehaaaa.github.io/TKM/
