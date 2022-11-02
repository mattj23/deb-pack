import os
import shutil
import pathlib
import click
import sys
import subprocess
from aptly_api import Client
from tempfile import TemporaryDirectory

from pack.context import Context, create_context, load_context

_context_file = os.path.join(pathlib.Path.home(), ".deb-pack.json")


@click.group()
def main():
    pass


@main.command()
def build():
    try:
        context = load_context(_context_file)
    except FileNotFoundError:
        click.echo(f"There is no active working context!")
        sys.exit(1)

    try:
        output_name = context.built_name()
    except KeyError as e:
        click.echo(e)
        sys.exit(1)

    if os.path.exists(output_name):
        click.echo(f"Package {output_name} already exists, doing nothing")

    click.echo(f"Building {output_name}...")
    output_path, _ = os.path.splitext(output_name)

    with TemporaryDirectory() as directory:
        root = os.path.join(directory, output_path)
        deb_folder = os.path.join(root, "DEBIAN")
        os.makedirs(deb_folder)

        for target in context.targets:
            destination = os.path.join(root, target.target_path)
            dest_path, _ = os.path.split(destination)
            if not os.path.exists(dest_path):
                os.makedirs(dest_path)
            click.echo(f" > {destination}")
            shutil.copy(target.source_path, destination)

        with open(os.path.join(deb_folder, "control"), "w") as handle:
            handle.write("\n".join(f"{key}: {value}" for key, value in context.control.items()))
            handle.write("\n")

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
    try:
        context = load_context(_context_file)
    except FileNotFoundError:
        click.echo(f"There is no active working context!")
        sys.exit(1)

    click.echo("Control data:")
    for k, v in context.control.items():
        click.echo(f"  {k}: {v}")

    click.echo("\nTargets:")
    for item in context.targets:
        click.echo(f"{item.source_path} -> {item.target_path}")


@main.command()
@click.argument("key", type=str)
@click.argument("value", type=str)
def control(key, value):
    try:
        context = load_context(_context_file)
    except FileNotFoundError:
        click.echo(f"There is no active working context!")
        sys.exit(1)

    context.control[key] = value
    click.echo(f"Setting control '{key}': {value}")
    context.save(_context_file)


@main.command()
@click.argument("source_path", type=click.Path(exists=True))
@click.argument("destination_path", type=click.Path())
@click.option("-n", "--name", type=str)
def add(source_path, destination_path, name):
    try:
        context = load_context(_context_file)
    except FileNotFoundError:
        click.echo(f"There is no active working context!")
        sys.exit(1)

    absolute = os.path.abspath(source_path)
    if not name:
        _, name = os.path.split(source_path)
    dest = os.path.join(destination_path, name)
    if dest.startswith("/"):
        dest = dest[1:]

    context.add_target(absolute, dest)
    click.echo(f"Adding target: {absolute} -> {dest}")
    context.save(_context_file)


@main.command()
@click.option("-f", "--from", "from_path")
def create(from_path):
    click.echo(f"Creating at {os.getcwd()}")
    context = create_context()
    if from_path:
        context.populate(from_path)

    context.save(_context_file)


if __name__ == '__main__':
    main()
