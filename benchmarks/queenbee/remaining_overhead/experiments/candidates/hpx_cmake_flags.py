#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""Query an installed HPX CMake package; emit Autotools flags without building FFTW.

Usage: python3 hpx_cmake_flags.py PREFIX OUTPUT [additional -D... CMake options]
Run on the machine where PREFIX and its dependency installations exist.
"""
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

CMAKE_SOURCE = r'''cmake_minimum_required(VERSION 3.18)
project(hpx_autotools_metadata LANGUAGES CXX)
find_package(HPX CONFIG REQUIRED)
set(CMAKE_CXX_STANDARD "${HPX_CXX_STANDARD}")
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/component.cpp" "void hpx_flag_probe() {}\n")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/application.cpp" "int main() { return 0; }\n")
add_library(hpx_flag_component SHARED "${CMAKE_CURRENT_BINARY_DIR}/component.cpp")
set_target_properties(hpx_flag_component PROPERTIES DEFINE_SYMBOL "" NO_SONAME ON)
target_link_libraries(hpx_flag_component PRIVATE HPX::hpx HPX::component)
add_executable(hpx_flag_application "${CMAKE_CURRENT_BINARY_DIR}/application.cpp")
set_target_properties(hpx_flag_application PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_link_libraries(hpx_flag_application PRIVATE HPX::hpx)
'''


def compile_flags(target):
    groups = target.get("compileGroups", [])
    if len(groups) != 1 or groups[0]["language"] != "CXX":
        raise RuntimeError("Expected one C++ compile group")
    group = groups[0]
    flags = []
    for fragment in group.get("compileCommandFragments", []):
        flags.extend(shlex.split(fragment["fragment"]))
    for definition in group.get("defines", []):
        value = definition["define"]
        # These only encode the throwaway target name/install prefix. HPX's
        # public pkg-config flags do not contain them either.
        if value.split("=", 1)[0] not in {
            "HPX_APPLICATION_NAME_DEFAULT", "HPX_COMPONENT_NAME_DEFAULT",
            "HPX_PLUGIN_NAME_DEFAULT", "HPX_PREFIX_DEFAULT"
        }:
            flags.append("-D" + value)
    for include in group.get("includes", []):
        flags.extend(["-isystem" if include.get("isSystem") else "-I", include["path"]])
    return flags


def link_flags(target):
    flags = []
    for fragment in target["link"]["commandFragments"]:
        flags.extend(shlex.split(fragment["fragment"]))
    # Libtool, rather than the HPX dependency metadata, owns output type.
    return [flag for flag in flags if flag != "-shared"]


def variable_value(flags):
    # Autotools stores flag variables as words and re-expands them in recipes.
    # Fail rather than silently emit a value needing another shell parse.
    for flag in flags:
        if not re.fullmatch(r"[A-Za-z0-9_./,:+=@%^-]+", flag):
            raise RuntimeError("Flag cannot safely be exported to Autotools: " + repr(flag))
    return " ".join(flags)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    prefix = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    candidates = [prefix / lib / "cmake/HPX" for lib in ("lib64", "lib")]
    package = next((path for path in candidates if (path / "HPXConfig.cmake").is_file()), None)
    if package is None:
        raise RuntimeError("HPXConfig.cmake was not found under " + str(prefix))
    source = output / "source"
    binary = output / "query"
    source.mkdir(parents=True, exist_ok=True)
    query = binary / ".cmake/api/v1/query"
    query.mkdir(parents=True, exist_ok=True)
    (query / "codemodel-v2").touch()
    (source / "CMakeLists.txt").write_text(CMAKE_SOURCE)
    subprocess.run([
        "cmake", "-G", "Unix Makefiles", "-S", str(source), "-B", str(binary),
        "-DHPX_DIR=" + str(package), "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_CXX_FLAGS=", "-DCMAKE_CXX_FLAGS_RELEASE=", *sys.argv[3:]
    ], check=True)
    reply = binary / ".cmake/api/v1/reply"
    index_path = max(reply.glob("index-*.json"), key=lambda path: path.stat().st_mtime_ns)
    index = json.loads(index_path.read_text())
    model = json.loads((reply / index["reply"]["codemodel-v2"]["jsonFile"]).read_text())
    config = next(item for item in model["configurations"] if item["name"] == "Release")
    targets = {item["name"]: json.loads((reply / item["jsonFile"]).read_text())
               for item in config["targets"]}
    variables = {}
    for stem, name in (("HPX", "hpx_flag_component"), ("HPX_APP", "hpx_flag_application")):
        variables[stem + "_CFLAGS"] = variable_value(compile_flags(targets[name]))
        variables[stem + "_LIBS"] = variable_value(link_flags(targets[name]))
    # Keep a structured artifact and sourceable, safely quoted environment.
    (output / "hpx-flags.json").write_text(json.dumps(variables, indent=2) + "\n")
    env_file = output / "hpx-flags.sh"
    env_file.write_text("\n".join("export " + key + "=" + shlex.quote(value)
                                 for key, value in variables.items()) + "\n")
    print("HPX dependency flags: " + str(env_file))


if __name__ == "__main__":
    main()
