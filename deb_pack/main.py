import os
import shutil
import pathlib
from typing import Tuple, Optional, List

import click
import sys
import subprocess
from aptly_api import Client, PublishEndpoint
from tempfile import TemporaryDirectory

from deb_pack.context import Context, create_context, load_context
from deb_pack.services import install_services

_context_file = os.path.join(pathlib.Path.home(), ".deb-pack.json")


@click.group()
def main():
    pass


@main.command()
@click.argument("api_url", type=str)
@click.argument("repo", type=str)
@click.option("--update-publish/--no-update-publish", default=False, help="Update the publishing to make the new "
                                                                          "package go live in the repository")
def aptly(api_url, repo, update_publish):
    """ Push a package which has already been built to an aptly API endpoint with a given repository name"""
    context, build_name = _load_context_and_build_name()

    if not os.path.exists(build_name):
        click.echo(f"Package {build_name} doesn't exist, aborting")
        sys.exit(1)

    root_name, _ = os.path.splitext(build_name)
    client = Client(api_url)
    client.files.upload(root_name, build_name)
    client.repos.add_uploaded_file(repo, root_name)
    click.echo(f"Uploaded {build_name} and added to repo {repo}")

    if update_publish:
        pub_endpoint = _get_endpoint(repo, client.publish.list())
        if pub_endpoint is None:
            click.echo(f"Could not find existing publish endpoint for {repo}")
            sys.exit(1)

        click.echo(f"Updating published repo {repo}")
        client.publish.update(prefix=pub_endpoint.prefix, distribution=pub_endpoint.distribution)


@main.command()
def build():
    """ Build a fully prepared context into a debian .deb file saved to the current working directory

    The build operation occurs in a temporary folder which is removed when the build is completed, whether it passes
    or fails. This operation consists of copying all the files specified in the build context to the temporary folder,
    writing the control file, and then running dpkg-deb on it."""
    context, output_name = _load_context_and_build_name()

    if os.path.exists(output_name):
        click.echo(f"Package {output_name} already exists, doing nothing")
        return

    click.echo(f"Building {output_name}...")
    output_path, _ = os.path.splitext(output_name)

    with TemporaryDirectory() as directory:
        root = os.path.join(directory, output_path)
        deb_folder = os.path.join(root, "DEBIAN")
        os.makedirs(deb_folder)

        # Copy targets
        for target in context.targets:
            destination = os.path.join(root, target.target_path)
            dest_path, _ = os.path.split(destination)
            if not os.path.exists(dest_path):
                os.makedirs(dest_path)
            relative = "/" + os.path.relpath(destination, root)
            click.echo(f" > {relative}")
            shutil.copy(target.source_path, destination)

        # Write control file
        click.echo(" > Creating control file")
        with open(os.path.join(deb_folder, "control"), "w") as handle:
            handle.write("\n".join(f"{key}: {value}" for key, value in context.control.items()))
            handle.write("\n")

        # Handle services
        install_services(context.services, root)

        # Fix any permissions issues on the scripts
        for script in ["preinst", "postinst", "prerm", "postrm"]:
            path = os.path.join(deb_folder, script)
            if os.path.exists(path):
                os.chmod(path, 0o755)

        subprocess.call(["dpkg-deb", "--build", "--root-owner-group", root])
        built = os.path.join(directory, output_name)
        if not os.path.exists(built):
            click.echo("No file was built!")
            sys.exit(1)

        shutil.copy(built, output_name)
        click.echo(f"Final file copied to {os.path.abspath(output_name)}")
    click.echo("Done")


@main.command()
def show():
    """ Show the contents of the current working build context """
    context = _load_context_or_exit()

    click.echo("Control data:")
    if context.control:
        for k, v in context.control.items():
            click.echo(f"  {k}: {v}")
    else:
        click.echo(" [no items]")

    click.echo("\nTargets:")
    if context.targets:
        for item in context.targets:
            click.echo(f"{item.source_path} -> {item.target_path}")
    else:
        click.echo(" [no items]")

    click.echo("\nServices:")
    if context.services:
        for item in context.services:
            click.echo(f"{item.source_path}")
    else:
        click.echo(" [no items]")


@main.command()
@click.argument("key", type=str)
@click.argument("value", type=str)
def control(key, value):
    """ Set a key/value pair in the debian control file

    \b
    examples:
        pack control Version 1.0.1
        pack control Architecture amd64
    """
    context = _load_context_or_exit()

    context.control[key] = value
    click.echo(f"Setting control '{key}': {value}")
    context.save(_context_file)


@main.command()
@click.argument("source_path", type=click.Path(exists=True))
def service(source_path):
    """ Add a service unit file to the context; path and inst/rm scripts will be handled automatically.

    Adds a systemd unit file for a service to the build context. The location of installation and the
    creation/modification of the postinst, postrm, and prerm scripts will be handled automatically during build.

    Be aware that if there are existing scripts the system will make a best effort to merge the handling elements
    into them, however the mechanics for this should be consulted in the project documentation.
    """
    context = _load_context_or_exit()

    absolute = os.path.abspath(source_path)
    if not absolute.endswith(".service"):
        click.echo("The source path must point to a .service file")
        sys.exit(1)

    context.add_service(absolute)
    click.echo(f"Adding service: {absolute}")
    context.save(_context_file)


@main.command()
@click.argument("source_path", type=click.Path(exists=True))
@click.argument("destination_path", type=click.Path())
@click.option("-n", "--name", type=str, help="If a name is specified, the file will be copied into the package with the"
                                             " given name, otherwise the original file name will be preserved")
def add(source_path, destination_path, name):
    """ Add a new file to the build context

    \b
    examples:
        pack add this/local/file.text etc/package/
        pack add binary-file-1234 usr/local/bin --name newname
    """
    context = _load_context_or_exit()

    absolute = os.path.abspath(source_path)
    if not name:
        _, name = os.path.split(source_path)
    dest = os.path.join(destination_path, name)
    dest = dest.strip("/")

    context.add_target(absolute, dest)
    click.echo(f"Adding target: {absolute} -> {dest}")
    context.save(_context_file)


@main.command()
@click.option("-f", "--from", "from_path", help="Uses an existing path as a basis for creating the context")
def create(from_path):
    """ Create a new build context and saves it in ~/.deb-pack.json """
    click.echo(f"Creating at {os.getcwd()}")
    context = create_context()
    if from_path:
        context.populate(from_path)

    context.save(_context_file)


def _load_context_or_exit() -> Context:
    try:
        return load_context(_context_file)
    except FileNotFoundError:
        click.echo(f"There is no active working context!")
        sys.exit(1)


def _load_context_and_build_name() -> Tuple[Context, str]:
    context = _load_context_or_exit()
    try:
        return context, context.built_name()
    except KeyError as e:
        click.echo(e)
        sys.exit(1)


def _get_endpoint(repo_name: str, endpoints: List[PublishEndpoint]) -> Optional[PublishEndpoint]:
    for e in endpoints:
        if any(d.get("Name", None) == repo_name for d in e.sources):
            return e
    return None


if __name__ == '__main__':
    main()
