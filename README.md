# Debian Package Generation Tool

Debian packaging tool for building binary .deb files and optionally pushing them to *aptly* repositories. Designed for use in CI/CD build pipelines, but will function perfectly well as a normal command line tool.

## Quick Examples

**Command line example:**

```bash
# Imagine that "starting_folder" is a folder containing most of the package files and a DEBIAN/control file
pack create --from starting_folder/

# Imagine that "build/my_binary" is a binary just compiled locally that needs to be installed in /usr/local/bin
pack add build/my_binary /usr/local/bin

pack control Version 1.0.0
pack control Architecture arm64

# After pack build a my-package-name_1.0.0_arm64.deb exists in the working directory
pack build

# Optionally, push it to an aptly repo
pack aptly http://aptly-api.example.com:8080 my_repo
```

*In the above example, imagine there is a folder in the current directory called `starting_folder` which contains the skeleton of a `.deb` package that just needs a binary copied into it.  We create the build context from that folder with the `--from` option, which pre-loads most of what the package build will do and reads the `starting_folder/DEBIAN/control` file to pre-populate most of the keys.*

*Imagine we just ran a `make` command which built a binary in the `./build/` folder.  We add that binary to the build context, specifying that it will installed into `/usr/local/bin` with the same name (the `--name` option would allow us to overwrite this), set the `Version` and `Architecture` keys in the control file, and run the `pack build` command.*

*After that the `.deb` file will be put into the current working directory, and we can push it to an aptly API.*

**Gitlab CI example:**

```yaml
build_job:
  image: python:3.9-bullseye
  before_script:
    - apt-get update
    - apt-get -y install git
    - pip install git+https://github.com/mattj23/deb-pack
  script:
    - make
    - pack create
    - pack control Version ${CI_COMMIT_TAG}
    - pack control Description "My binary service commit ${CI_COMMIT_SHORT_SHA}"
    - pack control Package my-binary
    - pack add build/my_binary
    - pack service ./my-binary.service
    - pack build
    - pack aptly http://aptly-api.example.com:8080 my_repo --update-publish
  only:
    - tags
```

*In the above example, imagine a traditional project that compiles a binary with `make`. We install the tool in the `before_script` (though it would more likely be baked into a custom starting build image), invoke `make`, and imagine that a `./build/my_binary` file has been created.*

*Unlike the previous example which used a starting folder containing most of the package contents, we create an empty build context with the bare `pack create` command.  We add the bare minimum entities to the debian control file, then add the built binary.*

*Imagining that there is a `my-binary.service` systemd unit file in the root directory of the repository, we add this to the context with the `pack service` command. During package build it will move this to `/lib/systemd/system/my-binary.service` and set up the `postinst`, `prerm`, and  `postrm` scripts to activate/start/remove the service.*

*Lastly we build and push the `.deb` file to an aptly repository, using the `--update-publish` flag so that it goes live immediately.*

## Overview

The packaging tool works by generating and storing a working context which contains a manifest of files to be included in the final .deb package and a list of key/value pairs to be written into the control file.  This context is stored in a local file at `~/.deb-pack.json` and so is preserved between invocations of the tool.

The file name of the package is determined by the `Package`, `Version`, and `Architecture` keys.  Once all three are specified in the context, the filename is resolvable and the build command will work.

The build process involves creating a temporary working directory, copying all the files from the context's manifest into the directory at the specific target location for each file, writing the control file, and then calling `dpkg-deb` on the folder. If it works correctly the final `.deb` file is moved to the current working directory before the temporary build directory is cleaned up.

Once the package is built, there is a command to push it to an *aptly* API with the option to update the *aptly* publishing.  This can be used to make the package go live in the repository.

Currently, the main limitations are:

* Dependence on `dpkg-deb` which means this tool needs to run on debian based systems. A future feature might be to implement the construction of the `.deb` file in pure python, allowing it to run on any system.
* Currently it is hardcoded to use the `--root-owner-group` command in `dpkg-deb`, no reason this can't be changed
* Simple interaction with *aptly*, I basically built what I needed and started using it. Commands to set up more complex features like authentication and creating repos/snapshots would be welcome additions.

## Installation

On a system with Python 3.8 or greater, this can be installed via pip:

```bash
pip3 install git+https://github.com/mattj23/deb-pack
```

Or it can be updated:

```bash
pip3 install git+https://github.com/mattj23/deb-pack --upgrade
```

*Currently, the tool will only function correctly on a debian based system because of the reliance on `dpkg-deb`*

## Usage

### Create a Build Context

First, create a build context.  No files get moved or created until the build step, rather a working context is saved in `~/.deb-pack.json` and will be retrieved at each invocation of the tool.  Running other commands before a build context is created will throw an error.  You may either create an empty context, or you may bootstrap one from a directory which is structured the way your final package will be.

Create an empty context:

```bash
pack create
```

Or create one from a starting folder.  In this case, the directory structure of the given path will be traversed and all files except for `DEBIAN/control` will be added as copy targets to the context with their relative path from the root of the folder.  If there is a file located at `DEBIAN/control` it will be loaded and the key/value pairs copied into the context.

```bash
pack create --from <path-to-folder>
```

At any point the contents of the build context can be displayed with `pack show`

### Add Files

Files can be added to the context using the following command.  

The first argument is a path to the existing file on disk from the current working directory. Files will be stored in the context with their absolute paths, so it is perfectly fine to navigate around the filesystem while adding files to the context.

The second argument is the directory path within the package where the file should be installed.  Leading and trailing slashes will be stripped, and paths will be handled correctly whether they are included or not.

If the file is to be renamed the optional `--name` parameter can be used.

```bash
pack add ./local-binary-89c03ef /usr/local/bin --name my_utility
```

### Add Systemd Services

Scripts which install and enable unit files for systemd services can be difficult to build automatically for debian binary packages because debhelper is made for creating binary packages from source packages.

This tool will generate the `postinst`, `prerm`, and `postrm` scripts for unit files based on scripts taken from a debhelper run.  To do so, add the service unit file with the following command:

```bash
pack service path/to/my-unit-file.service
```

Multiple unit files can be added if desired. On package build, the service files will be set to install in `/lib/systemd/system` and the installation/enabling bash code will be generated based on the templates in [deb_pack/services.py](./deb_pack/services.py).

If no script exists for each generated item, a new script will be created which has the correct header and ends with an `exit 0`.  If a script does exist, the tool will attempt to add the code at the end of the file before any trailing `exit 0`. This behavior is currently primitive and extensions are welcome.

### Set Control Key/Values

Set the control key/value pairs. The minimum items required by debian must be adhered to, and the `Package`, `Version`, and `Architecture` keys will themselves be required to generate the name of the `.deb` file.

```bash
pack control Version 1.0.2
```

### Build the Debian Package

Build the actual `.deb` file with the following command.  If successful the final package will be copied to the current working directory.

```bash
pack build
```

### Upload to Aptly

If a `.deb` file with the name which results from the current context exists in the current working folder (as would be the case if `pack build` was just run successfully), running `pack aptly` will push the file to an *aptly* API endpoint.  

```bash
pack aptly http://my.aptly.url:8080 my-repo-name
```

Optionally, to directly trigger *aptly*'s publishing update on an already published repo, the `--update-publish` flag can be used.  This will make the package live immediately.

```bash
pack aptly http://my.aptly.url:8080 my-repo-name --update-publish
```
