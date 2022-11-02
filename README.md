# Debian Package Generation Tool

Debian packaging tool for building binary .deb files and optionally pushing them to *aptly* repositories. Designed for use in CI/CD build pipelines.

## Usage

Create a build context.  No files get moved or created until the build step, rather a working context is saved in `~/.deb-pack.json` and during the build step everything is performed in a temporary directory.

```bash
pack create

# Or
pack create --from <path-to-folder>
```

