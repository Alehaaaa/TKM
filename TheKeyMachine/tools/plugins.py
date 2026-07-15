"""Shared build, load, context setup, validation, and cleanup for native Maya plug-ins."""

import hashlib
import os
import platform
import subprocess
import sys

from maya import cmds, mel


_PLUGIN_SPECS = {}


class NativePluginSpec(object):
    def __init__(
        self,
        *,
        label,
        source_paths,
        output_name,
        registry_name,
        build_recipe,
        required_commands=(),
        build_command=None,
        expected_build=None,
        libraries=("OpenMaya", "OpenMayaUI", "Foundation"),
        frameworks=(),
        compile_flags=(),
        context_fallbacks=None,
    ):
        self.label = str(label)
        self.source_paths = tuple(os.path.realpath(path) for path in source_paths)
        if not self.source_paths:
            raise ValueError("A native plug-in requires at least one source file.")
        self.output_name = str(output_name)
        self.registry_name = str(registry_name)
        self.build_recipe = str(build_recipe)
        self.required_commands = tuple(required_commands)
        self.build_command = build_command
        self.expected_build = expected_build
        self.libraries = tuple(libraries)
        self.frameworks = tuple(frameworks)
        self.compile_flags = tuple(compile_flags)
        self.context_fallbacks = dict(context_fallbacks or {})

        extension = ".bundle" if sys.platform == "darwin" else ".so"
        self.build_directory = os.path.join(
            os.path.dirname(self.source_paths[0]),
            "_native",
            "maya{}_{}".format(cmds.about(version=True), platform.machine()),
        )
        self.path = os.path.join(self.build_directory, self.output_name + extension)
        self.stamp_path = self.path + ".sha256"
        _PLUGIN_SPECS[self.registry_name] = self


def normalized_path(path):
    return os.path.normcase(os.path.realpath(path))


def command_exists(command_name):
    return bool(command_name and mel.eval('exists "{}"'.format(command_name)))


def context_exists(context_name):
    try:
        return bool(cmds.contextInfo(context_name, exists=True))
    except Exception:
        return False


def delete_context(context_name):
    if not context_exists(context_name):
        return False
    try:
        cmds.deleteUI(context_name, toolContext=True)
        return True
    except Exception:
        return False


def create_context(spec, command_name, context_name):
    for value in (command_name, context_name):
        if not str(value).replace("_", "").isalnum():
            raise ValueError("Invalid {} context identifier: {}".format(spec.label, value))
    try:
        mel.eval('{} "{}"'.format(command_name, context_name))
    except RuntimeError as error:
        raise RuntimeError(
            "{} plug-in could not create {} using {}: {}".format(
                spec.label, context_name, command_name, error
            )
        )


def loaded_plugin(spec):
    expected_path = normalized_path(spec.path)
    for plugin_name in cmds.pluginInfo(query=True, listPlugins=True) or []:
        try:
            if not cmds.pluginInfo(plugin_name, query=True, loaded=True):
                continue
            if normalized_path(cmds.pluginInfo(plugin_name, query=True, path=True)) == expected_path:
                return plugin_name
        except (RuntimeError, TypeError):
            continue
    return None


def _maya_native_paths(spec):
    maya_location = os.environ.get("MAYA_LOCATION")
    if not maya_location:
        raise RuntimeError("MAYA_LOCATION is unavailable; cannot build {}.".format(spec.label))
    if sys.platform == "darwin":
        maya_root = os.path.dirname(os.path.dirname(maya_location))
        return os.path.join(maya_root, "include"), os.path.join(maya_location, "MacOS")
    return os.path.join(maya_location, "include"), os.path.join(maya_location, "lib")


def source_digest(spec):
    digest = hashlib.sha256()
    build_inputs = (
        ("recipe", spec.build_recipe),
        ("platform", sys.platform),
        ("machine", platform.machine()),
        ("maya", str(cmds.about(version=True))),
        ("output", spec.output_name),
        ("libraries", spec.libraries),
        ("frameworks", spec.frameworks),
        ("compile_flags", spec.compile_flags),
    )
    for name, value in build_inputs:
        digest.update(name.encode("utf-8"))
        digest.update(repr(value).encode("utf-8"))
    for index, path in enumerate(spec.source_paths):
        digest.update("source:{}:".format(index).encode("utf-8"))
        digest.update(os.path.basename(path).encode("utf-8"))
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def needs_build(spec):
    if not os.path.isfile(spec.path) or not os.path.isfile(spec.stamp_path):
        return True
    try:
        with open(spec.stamp_path, "r", encoding="utf-8") as stream:
            return stream.read().strip() != source_digest(spec)
    except OSError:
        return True


def build(spec):
    missing_sources = [path for path in spec.source_paths if not os.path.isfile(path)]
    if missing_sources:
        raise RuntimeError(
            "{} native source is missing: {}".format(spec.label, ", ".join(missing_sources))
        )
    if not needs_build(spec):
        return spec.path
    if sys.platform != "darwin":
        raise RuntimeError("{} native builds currently support Maya on macOS.".format(spec.label))

    include_directory, library_directory = _maya_native_paths(spec)
    os.makedirs(spec.build_directory, exist_ok=True)
    temporary_path = spec.path + ".tmp"
    command = [
        "xcrun", "clang++", "-std=c++17", "-arch", platform.machine(),
        "-dynamiclib", "-fPIC", "-O2", "-Wno-nontrivial-memcall",
        "-DOSMac_", "-DCC_GNU_", "-DBits64_", "-DREQUIRE_IOSTREAM",
        "-I{}".format(include_directory), "-L{}".format(library_directory),
        "-Wl,-rpath,{}".format(library_directory),
    ]
    command.extend(spec.compile_flags)
    command.extend("-l{}".format(library) for library in spec.libraries)
    for framework in spec.frameworks:
        command.extend(("-framework", framework))
    command.extend(("-o", temporary_path))
    command.extend(spec.source_paths)

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as error:
        raise RuntimeError("{} could not start the native compiler: {}".format(spec.label, error))
    if result.returncode != 0:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise RuntimeError("{} native plug-in build failed:\n{}".format(spec.label, result.stdout))

    os.replace(temporary_path, spec.path)
    try:
        with open(spec.stamp_path, "w", encoding="utf-8") as stream:
            stream.write(source_digest(spec))
    except OSError as error:
        raise RuntimeError("{} could not update its native build cache: {}".format(spec.label, error))
    return spec.path


def plugin_build_id(spec):
    if not spec.build_command:
        return None
    result = getattr(cmds, spec.build_command)()
    if isinstance(result, (list, tuple)):
        result = result[0] if result else ""
    return str(result)


def is_ready(spec):
    if not loaded_plugin(spec):
        return False
    if not all(command_exists(command) for command in spec.required_commands):
        return False
    if spec.expected_build is not None:
        try:
            return plugin_build_id(spec) == spec.expected_build
        except (RuntimeError, AttributeError, TypeError):
            return False
    return True


def _restore_context(spec):
    current = cmds.currentCtx()
    fallback = spec.context_fallbacks.get(current)
    if fallback:
        try:
            cmds.setToolTo(fallback)
        except Exception:
            pass


def unload(spec, restore_context=True):
    if restore_context:
        _restore_context(spec)
    for context_name in spec.context_fallbacks:
        delete_context(context_name)

    plugin_name = loaded_plugin(spec)
    if not plugin_name:
        return False
    cmds.unloadPlugin(plugin_name)
    try:
        cmds.pluginInfo(plugin_name, edit=True, remove=True)
    except RuntimeError:
        pass
    return True


def load(spec, force_reload=False):
    rebuild = needs_build(spec)
    if is_ready(spec) and not force_reload and not rebuild:
        return loaded_plugin(spec)

    # Compile to an atomic replacement before disturbing the currently loaded
    # tool. If compilation fails, Maya keeps the last working plug-in/context.
    if rebuild:
        build(spec)
    if loaded_plugin(spec):
        unload(spec, restore_context=True)
    if not rebuild:
        build(spec)
    loaded_names = cmds.loadPlugin(spec.path, name=spec.registry_name, quiet=True)
    plugin_name = loaded_names[0] if loaded_names else loaded_plugin(spec)

    try:
        missing = [command for command in spec.required_commands if not command_exists(command)]
        if missing:
            raise RuntimeError(
                "{} plug-in {} loaded but did not register: {}".format(
                    spec.label, plugin_name or spec.path, ", ".join(missing)
                )
            )
        if spec.expected_build is not None:
            loaded_build = plugin_build_id(spec)
            if loaded_build != spec.expected_build:
                raise RuntimeError(
                    "{} loaded stale native code: expected {}, Maya reported {}.".format(
                        spec.label, spec.expected_build, loaded_build
                    )
                )
    except Exception as validation_error:
        try:
            unload(spec, restore_context=True)
        except Exception as rollback_error:
            raise RuntimeError(
                "{} Validation failed and rollback was incomplete: {}".format(
                    validation_error, rollback_error
                )
            ) from validation_error
        raise
    return plugin_name


def ensure_contexts(spec, context_commands, configure_command=None, configure_args=()):
    """Load, configure, and recreate a native tool's Maya contexts."""
    pairs = tuple(context_commands)
    load(spec)
    if configure_command:
        if not command_exists(configure_command):
            raise RuntimeError(
                "{} plug-in did not register {}.".format(spec.label, configure_command)
            )
        getattr(cmds, configure_command)(*tuple(configure_args))

    for _command_name, context_name in pairs:
        delete_context(context_name)

    created = []
    try:
        for command_name, context_name in pairs:
            create_context(spec, command_name, context_name)
            created.append(context_name)
    except Exception:
        for context_name in reversed(created):
            delete_context(context_name)
        raise
    return tuple(created)


def shutdown_all():
    for spec in reversed(tuple(_PLUGIN_SPECS.values())):
        try:
            unload(spec, restore_context=True)
        except Exception:
            pass
