#!/usr/bin/env bash
# Baut das RPM lokal (braucht rpm-build, rpmdevtools, systemd-rpm-macros, python3-devel).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VER="$(sed -n 's/^Version:\s*//p' "$HERE/packaging/we-wallpaper.spec")"
TOP="${RPM_TOPDIR:-$HOME/rpmbuild}"
mkdir -p "$TOP"/{SOURCES,SPECS,BUILD,RPMS,SRPMS}
tar --exclude=.git --exclude='*.png' --transform "s|^\.|we-wallpaper-$VER|" -czf "$TOP/SOURCES/we-wallpaper-$VER.tar.gz" -C "$HERE" .
cp "$HERE/packaging/we-wallpaper.spec" "$TOP/SPECS/"
rpmbuild --define "_topdir $TOP" -ba "$TOP/SPECS/we-wallpaper.spec"
ls -1 "$TOP"/RPMS/noarch/we-wallpaper-*.rpm "$TOP"/SRPMS/we-wallpaper-*.src.rpm
