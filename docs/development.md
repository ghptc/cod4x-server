# Fork development

This fork retains the complete upstream master history and existing notices.
Development uses feature branches, Conventional Commits and pull requests to
master. The owner alone approves merges. Nothing in this workflow enables CI,
publishes artifacts, or authorizes deployment.

## Local Linux i386 build

Use the repository's existing makefile and vendored mbedTLS/LibTomCrypt sources:

```sh
make -j4
file bin/cod4x18_dedrun
readelf -h bin/cod4x18_dedrun
```

Required tools are GCC/G++ with 32-bit development libraries, make and NASM.
Use a disposable build environment; generated objects, static libraries and
executables are not contributions. `make release` is out of scope: upstream's
target tags and pushes. The inherited workflow files are retained unchanged;
this phase does not configure or enable them.

Changes must distinguish actual gameplay tests from compilation/static checks.
The private preserved PoC contains historical raw evidence and local inputs;
only minimal source, attribution and compact evidence summaries belong in Git.
