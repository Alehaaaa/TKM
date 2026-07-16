cmake_minimum_required(VERSION 3.20)

project(TheKeyMachineNativePlugins LANGUAGES CXX)

set(MAYA_VERSION "" CACHE STRING "Four-digit Maya release, for example 2025")
set(MAYA_DEVKIT_ROOT "" CACHE PATH "Root of the extracted Maya devkit")
set(TKM_PLATFORM "" CACHE STRING "TKM platform key: windows, linux, or macos")
set(TKM_ARCH "" CACHE STRING "TKM architecture key: x86_64 or arm64")
set(
    TKM_OUTPUT_ROOT
    "${CMAKE_BINARY_DIR}/builds-package"
    CACHE PATH
    "Root of the release-ready native plug-in tree"
)

if(NOT MAYA_VERSION MATCHES "^20[0-9][0-9]$")
    message(FATAL_ERROR "MAYA_VERSION must be a four-digit Maya release")
endif()
if(NOT IS_DIRECTORY "${MAYA_DEVKIT_ROOT}")
    message(FATAL_ERROR "MAYA_DEVKIT_ROOT does not exist: ${MAYA_DEVKIT_ROOT}")
endif()
if(NOT TKM_PLATFORM MATCHES "^(windows|linux|macos)$")
    message(FATAL_ERROR "TKM_PLATFORM must be windows, linux, or macos")
endif()
if(NOT TKM_ARCH MATCHES "^(x86_64|arm64)$")
    message(FATAL_ERROR "TKM_ARCH must be x86_64 or arm64")
endif()

find_path(
    MAYA_INCLUDE_DIR
    maya/MFnPlugin.h
    HINTS "${MAYA_DEVKIT_ROOT}"
    PATH_SUFFIXES include devkit/include
    NO_DEFAULT_PATH
)
if(NOT MAYA_INCLUDE_DIR)
    message(FATAL_ERROR "Could not find Maya headers below ${MAYA_DEVKIT_ROOT}")
endif()

set(_maya_library_hints
    "${MAYA_DEVKIT_ROOT}/lib"
    "${MAYA_DEVKIT_ROOT}/devkit/lib"
    "${MAYA_DEVKIT_ROOT}/Maya.app/Contents/MacOS"
)
file(GLOB _maya_application_library_hints "${MAYA_DEVKIT_ROOT}/*.app/Contents/MacOS")
list(APPEND _maya_library_hints ${_maya_application_library_hints})
foreach(_library OpenMaya OpenMayaUI Foundation)
    find_library(
        MAYA_${_library}_LIBRARY
        NAMES ${_library}
        HINTS ${_maya_library_hints}
        NO_DEFAULT_PATH
    )
    if(NOT MAYA_${_library}_LIBRARY)
        message(FATAL_ERROR "Could not find Maya ${_library} below ${MAYA_DEVKIT_ROOT}")
    endif()
endforeach()

if(WIN32)
    set(_plugin_suffix ".mll")
    add_compile_definitions(NT_PLUGIN REQUIRE_IOSTREAM)
elseif(APPLE)
    set(_plugin_suffix ".bundle")
    add_compile_definitions(OSMac_ CC_GNU_ Bits64_ REQUIRE_IOSTREAM)
else()
    set(_plugin_suffix ".so")
    add_compile_definitions(Bits64_ UNIX _BOOL LINUX FUNCPROTO _GNU_SOURCE REQUIRE_IOSTREAM)
endif()

function(tkm_add_maya_plugin target tool output_name source)
    add_library(${target} MODULE "${source}")
    target_compile_features(${target} PRIVATE cxx_std_17)
    target_include_directories(${target} PRIVATE "${MAYA_INCLUDE_DIR}")
    target_link_libraries(
        ${target}
        PRIVATE
        "${MAYA_OpenMaya_LIBRARY}"
        "${MAYA_OpenMayaUI_LIBRARY}"
        "${MAYA_Foundation_LIBRARY}"
    )

    set(_output_directory
        "${TKM_OUTPUT_ROOT}/TheKeyMachine/tools/${tool}/__builds__/${TKM_PLATFORM}-${TKM_ARCH}/maya${MAYA_VERSION}"
    )
    set_target_properties(
        ${target}
        PROPERTIES
        PREFIX ""
        SUFFIX "${_plugin_suffix}"
        OUTPUT_NAME "${output_name}"
        LIBRARY_OUTPUT_DIRECTORY "${_output_directory}"
        RUNTIME_OUTPUT_DIRECTORY "${_output_directory}"
        LIBRARY_OUTPUT_DIRECTORY_RELEASE "${_output_directory}"
        RUNTIME_OUTPUT_DIRECTORY_RELEASE "${_output_directory}"
        BUILD_RPATH ""
        INSTALL_RPATH ""
    )
endfunction()

get_filename_component(TKM_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)

tkm_add_maya_plugin(
    tkmDepthMoverNative
    depth_mover
    tkmDepthMoverNative
    "${TKM_ROOT}/TheKeyMachine/tools/depth_mover/plugin.cpp"
)
tkm_add_maya_plugin(
    tkmMicroMove
    micro_move
    tkmMicroMove
    "${TKM_ROOT}/TheKeyMachine/tools/micro_move/plugin.cpp"
)
