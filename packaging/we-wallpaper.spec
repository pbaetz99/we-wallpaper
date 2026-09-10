Name:           we-wallpaper
Version:        0.3.0
Release:        1%{?dist}
Summary:        Wallpaper Engine workshop wallpapers on KDE Plasma 6 / Wayland
License:        MIT
URL:            https://github.com/pbaetz99/we-wallpaper
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  systemd-rpm-macros
Requires:       python3
Requires:       python3-pyside6
Requires:       libkscreen-qt6
Requires:       systemd
Recommends:     ffmpeg-free
# Backend "owe" (waywallen + Open Wallpaper Engine) is installed per user by
# %{_datadir}/we-wallpaper/install-owe.sh and needs flatpak and kpackagetool6.
Suggests:       flatpak
# The renderer itself is not packaged: build linux-wallpaperengine from source
# (see README) and point the "renderer" config key or WE_RENDERER at it.

%description
Control script, PySide6 GUI with a properties editor, and a pause daemon that
freezes linux-wallpaperengine while the wallpaper is invisible (fullscreen,
screen lock, maximized windows). Optional switch to wallpaper-engine-kde-plugin
or to waywallen + Open Wallpaper Engine, which keeps the desktop icons visible.

%prep
%autosetup -n %{name}-%{version}

%build
# nothing to compile

%install
install -Dm755 bin/we-wallpaper        %{buildroot}%{_bindir}/we-wallpaper
install -Dm755 bin/we-wallpaper-gui    %{buildroot}%{_bindir}/we-wallpaper-gui
install -Dm755 bin/we-wallpaper-watch  %{buildroot}%{_bindir}/we-wallpaper-watch
install -Dm644 share/fullscreen-watch.js %{buildroot}%{_datadir}/we-wallpaper/fullscreen-watch.js
install -Dm755 packaging/install-owe.sh  %{buildroot}%{_datadir}/we-wallpaper/install-owe.sh
install -Dm644 share/wwproto/control.proto %{buildroot}%{_datadir}/we-wallpaper/wwproto/control.proto
install -Dm644 share/wwproto/filter.proto  %{buildroot}%{_datadir}/we-wallpaper/wwproto/filter.proto
install -Dm644 share/wwproto/README.md     %{buildroot}%{_datadir}/we-wallpaper/wwproto/README.md
install -Dm644 packaging/we-wallpaper.service       %{buildroot}%{_userunitdir}/we-wallpaper.service
install -Dm644 packaging/we-wallpaper-watch.service %{buildroot}%{_userunitdir}/we-wallpaper-watch.service
sed 's|^Exec=.*|Exec=%{_bindir}/we-wallpaper-gui|' desktop/we-wallpaper-gui.desktop \
    > %{buildroot}%{_datadir}/applications/we-wallpaper-gui.desktop 2>/dev/null || {
    mkdir -p %{buildroot}%{_datadir}/applications
    sed 's|^Exec=.*|Exec=%{_bindir}/we-wallpaper-gui|' desktop/we-wallpaper-gui.desktop \
        > %{buildroot}%{_datadir}/applications/we-wallpaper-gui.desktop; }

%check
QT_QPA_PLATFORM=offscreen WE_LANG=de python3 -m unittest discover -s tests -p 'test_*.py' || :

%files
%license LICENSE
%doc README.md CHANGELOG.md docs/ARCHITECTURE.md
%{_bindir}/we-wallpaper
%{_bindir}/we-wallpaper-gui
%{_bindir}/we-wallpaper-watch
%{_datadir}/we-wallpaper/
%{_userunitdir}/we-wallpaper.service
%{_userunitdir}/we-wallpaper-watch.service
%{_datadir}/applications/we-wallpaper-gui.desktop

%changelog
* Fri Sep 11 2026 pbaetz99 - 0.3.0-1
- backend owe: waywallen + Open Wallpaper Engine, desktop icons for every type
- install-owe.sh, owe subcommands, dependency-free control protocol client

* Fri Sep 11 2026 pbaetz99 - 0.2.3-1
- span_pause_any option
* Thu Sep 10 2026 pbaetz99 - 0.2.2-1
- KDE plugin patches (no plasmashell abort on broken scenes), doctor QtWebSockets check
* Thu Sep 10 2026 pbaetz99 - 0.2.1-1
- KDE plugin: packed WallpaperSource, build helper, scene guard
* Thu Sep 10 2026 pbaetz99 - 0.2.0-1
- English UI, doctor command, renderer config key, test suite, docs, KDE-plugin backend switch
* Thu Sep 10 2026 pbaetz99 - 0.1.0-1
- First public release
