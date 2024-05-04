# Debian Package Generation Tool

Debian packaging tool for building binary .deb files and optionally pushing them to *aptly* repositories. Designed for use in CI/CD build pipelines, but will function perfectly well as a normal command line tool.

This is a simple tool which wraps `dpkg-deb` and adds some convenience features.  It is not as capable or complex as [deb-pkg-tools](https://github.com/xolox/python-deb-pkg-tools), but is meant to be dead simple to use for most needs.  I built this after facing challenges creating binary debian packages while trying to use some of the features of `debhelper`.

## Quick Start

### Installation

This project is available on PyPI, and can be installed into a Python virtual environment, using `pipx`, or with the `pip install --break-system-packages` flag (sometimes useful in build environments).

```bash
pip install deb-pack
```

*Currently, the tool will only function correctly on a Debian based system because of the reliance on `dpkg-deb`. This is installed by default on most Debian based distributions, but if not it's typically available with `apt install dpkg`.*

### Examples

**Packing a simple binary on the command line**

Imagine you wanted to pack an updated version of `kubectl` (as of this writing, the current Bookworm version is 1.20 while the current `kubectl` release is 1.30).

```bash
# Download the version of interest and make it executable
curl -LO https://dl.k8s.io/release/v1.30.0/bin/linux/amd64/kubectl
chmod +x kubectl

# Create a new build 'context' and add the minimum necessary control information to it
pack create
pack control Package kubectl
pack control Version 1.30.0
pack control Architecture amd64

# Set the kubectl binary to go into /usr/local/bin
pack add kubectl /usr/local/bin

# Now create the deb file
pack build
```

The `dpkg-deb` binary will complain that there was no Description or Maintainer field, but will execute successfully.  When finished, the file `kubectl_1.30.0_amd64.deb` will be in the current directory.

**Creating a package using a starting folder**

If you're used to using `dpkg-deb`, you know that it works on a specially prepared directory.  Within this directory there is a `./DEBIAN` folder which holds the control file alongside a number of optional metadata and script files, such as the pre/post installation and removal bash scripts.  Then, files getting deployed onto the system are put in sub-directories based on the absolute path of the intended destination.

The `deb-pack` tool can use a folder with that structure as a starting point for a build context.

Imagine you have a repository that, in addition to the source, has a folder with the scaffolding for the package.  It includes a configuration file that gets deployed to `/etc/my_project.conf` and has pre/post scripts for both installation and removal.  The `DEBIAN/control` file is already populated with all of the relevant fields except the latest version number.

```
my_project/
├── Makefile
├── packaging/
│   ├── DEBIAN/
│   │   ├── conffiles
│   │   ├── control
│   │   ├── postinst
│   │   ├── postrm
│   │   ├── preinst
│   │   └── prerm
│   └── etc/
│       └── my_project.conf
└── src/
```

In this case, you can use the `packaging/` folder as a starting point and only add the version and the compiled binary.

```bash
pack create --from packaging/

# Imagine that after running make you end up with `my_binary` that needs to get installed to /usr/local/bin
make
pack add my_binary /usr/local/bin

# Finally, update the version and build the .deb file
pack control Version 1.0.0
pack build

# Optionally, push it to an aptly repo
pack aptly http://aptly-api.example.com:8080 my_repo
```

**Gitlab CI example**

This example shows the use of `deb-pack` in Gitlab CI to create a `.deb` package and push it to a locally hosted `aptly` repository.  The source repository contains a `packaging/` folder similar to the previous example that has a control file pre-populated with most of the expected Debian package metadata fields.

Also in the root folder of the repository is a `my-binary.service` unit file.  This example makes use of the `deb-pack service` command, which configures the unit file to be installed in `/lib/systemd/system` and automatically adds the `postinst`, `prerm`, and `postrm` scripts to reload/enable/start/stop the service.  These scripts are based on the output of `debhelper`, and will provide smooth installation, update, and removal behavior under most circumstances.

Finally, this example includes deployment of a package to a locally hosted `aptly` repository with the `--update-publish` flag to update the published repository immediately.

```yaml
build_job:
  image: python:3.9-bullseye
  before_script:
    - apt-get update
    - apt-get -y install git
    - pip install deb-pack
  script:
    - make
    - pack create --from packaging/
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

## Overview

The packaging tool works by generating and storing a working context which contains a manifest of files to be included in the final .deb package and a list of key/value pairs to be written into the control file.  This context is stored in a local file at `~/.deb-pack.json` and so is preserved between invocations of the tool.

The file name of the package is determined by the `Package`, `Version`, and `Architecture` keys.  Once all three are specified in the context, the filename is resolvable and the build command will work.

The build process involves creating a temporary working directory, copying all the files from the context's manifest into the directory at the specific target location for each file, writing the control file, and then calling `dpkg-deb` on the folder. If it works correctly the final `.deb` file is moved to the current working directory before the temporary build directory is cleaned up.

Once the package is built, there is a command to push it to an *aptly* API with the option to update the *aptly* publishing.  This can be used to make the package go live in the repository.

Currently, the main limitations are:

* Dependence on `dpkg-deb` which means this tool needs to run on debian based systems. A future feature might be to implement the construction of the `.deb` file in pure python, allowing it to run on any system.
* Currently it is hardcoded to use the `--root-owner-group` command in `dpkg-deb`, no reason this can't be changed
* Simple interaction with *aptly*, I basically built what I needed and started using it. Commands to set up more complex features like authentication and creating repos/snapshots would be welcome additions.


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
