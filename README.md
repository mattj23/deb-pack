# Debian Package Generation Tool

Debian packaging tool for building binary .deb files and optionally pushing them to *aptly* repositories. Designed for use in CI/CD build pipelines, but will function perfectly well as a normal command line tool.

## Overview

The packaging tool works by generating and storing a working context which contains a manifest of files to be included in the final .deb package and a list of key/value pairs to be written into the control file.  This context is stored in a local file at `~/.deb-pack.json` and so is preserved between invocations of the tool.

The file name of the package is determined by the `Package`, `Version`, and `Architecture` keys.  Once all three are specified in the context, the filename is resolvable and the build command will work.

The build process involves creating a temporary working directory, copying all the files from the context's manifest into the directory at the specific target location for each file, writing the control file, and then calling `dpkg-deb` on the folder. If it works correctly the final `.deb` file is moved to the current working directory before the temporary build directory is cleaned up.

Once the package is built, there is a command to push it to an *aptly* API with the option to update the *aptly* publishing.  This can be used to make the package go live in the repository.

Currently the main limitations are:

* Dependence on `dpkg-deb` which means this tool needs to run on debian based systems. A future feature might be to implement the construction of the `.deb` file in pure python, allowing it to run on any system.
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
