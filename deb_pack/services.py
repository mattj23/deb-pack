"""
    Tooling for systemd services
"""
import os
import shutil
from typing import List
import click

from deb_pack.context import ServiceUnit

_install_path = "lib/systemd/system"

_post_inst = """
# Automatically added by dh_systemd_enable
# This will only remove masks created by d-s-h on package removal.
deb-systemd-helper unmask {0} >/dev/null || true

# was-enabled defaults to true, so new installations run enable.
if deb-systemd-helper --quiet was-enabled {0}; then
        # Enables the unit on first installation, creates new
        # symlinks on upgrades if the unit file has changed.
        deb-systemd-helper enable {0} >/dev/null || true
else
        # Update the statefile to add new symlinks (if any), which need to be
        # cleaned up on purge. Also remove old symlinks.
        deb-systemd-helper update-state {0} >/dev/null || true
fi
# End automatically added section
# Automatically added by dh_systemd_start
if [ -d /run/systemd/system ]; then
        systemctl --system daemon-reload >/dev/null || true
        deb-systemd-invoke start {0} >/dev/null || true
fi
# End automatically added section
"""

_pre_rm = """
# Automatically added by dh_systemd_start
if [ -d /run/systemd/system ]; then
        deb-systemd-invoke stop {0} >/dev/null
fi
"""

_post_rm = """
# Automatically added by dh_systemd_start
if [ -d /run/systemd/system ]; then
    systemctl --system daemon-reload >/dev/null || true
    
fi
# End automatically added section
# Automatically added by dh_installinit

# In case this system is running systemd, we make systemd reload the unit files
# to pick up changes.
if [ -d /run/systemd/system ] ; then
    systemctl --system daemon-reload >/dev/null || true
fi
# End automatically added section

# Automatically added by dh_systemd_enable
if [ "$1" = "remove" ]; then
    if [ -x "/usr/bin/deb-systemd-helper" ]; then
        deb-systemd-helper mask {0} >/dev/null
    fi
fi

if [ "$1" = "purge" ]; then
    if [ -x "/usr/bin/deb-systemd-helper" ]; then
        deb-systemd-helper purge {0} >/dev/null
        deb-systemd-helper unmask {0} >/dev/null
    fi
fi
# End automatically added section
"""


def _generate(items: List[ServiceUnit], script_body: str) -> str:
    output = []
    for item in items:
        _, item_filename = os.path.split(item.source_path)
        output.append(script_body.format(item_filename))
    return "\n\n".join(output)


def _build_script(script_name, script_body_template, items: List[ServiceUnit], working_folder: str):
    content = _generate(items, script_body_template)
    path = os.path.join(working_folder, "DEBIAN", script_name)
    if not os.path.exists(path):
        click.echo(f" > No {script_name} script, creating it")
        with open(path, "w") as handle:
            handle.write("#!/bin/sh\nset -e\n")
            handle.write(content)
            handle.write("\nexit 0\n")
    else:
        click.echo(f" > Existing {script_name} script, attempting to add service handling to end")
        with open(path, "r") as handle:
            script_contents = handle.read().strip().strip("exit 0")

        script_contents += "\n"
        script_contents += content
        script_contents += "exit 0\n"

        with open(path, "w") as handle:
            handle.write(script_contents)
    os.chmod(path, 0o755)


def install_services(items: List[ServiceUnit], working_folder: str):
    if not items:
        click.echo(" > No services")
        return

    for item in items:
        _, item_filename = os.path.split(item.source_path)
        dest = os.path.join(working_folder, _install_path, item_filename)
        dest_path, _ = os.path.split(dest)
        if not os.path.exists(dest_path):
            os.makedirs(dest_path)

        relative = "/" + os.path.relpath(dest, working_folder)
        shutil.copy(item.source_path, dest)
        click.echo(f" > Service: {relative}")

    _build_script("postinst", _post_inst, items, working_folder)
    _build_script("postrm", _post_rm, items, working_folder)
    _build_script("prerm", _pre_rm, items, working_folder)
