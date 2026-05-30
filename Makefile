# Leaf Downloader — Build & Installation Makefile
# ==================================================

APP_ID = io.github.hasan_psl.Leaf-Downloader
PREFIX ?= /usr/local
DESTDIR ?=

# Directories
BINDIR     = $(DESTDIR)$(PREFIX)/bin
SHAREDIR   = $(DESTDIR)$(PREFIX)/share
APPDIR     = $(SHAREDIR)/leaf-downloader
ICONDIR    = $(SHAREDIR)/icons/hicolor
APPENTRY   = $(SHAREDIR)/applications
METAINFO   = $(SHAREDIR)/metainfo

# Output directory for built .deb packages
DIST_DIR  ?= dist

# Pinned yt-dlp version used by debian/rules (kept in sync manually)
YT_DLP_VERSION := 2026.3.17
YT_DLP_WHEEL   := yt_dlp-$(YT_DLP_VERSION)-py3-none-any.whl
YT_DLP_SHA256  := 32992db94303a8a5d211a183f2174834fe7f8c29d83ed2e7a324eae97a8f26d8
YT_DLP_URL     := https://files.pythonhosted.org/packages/cd/13/5093bcb954878e50f7217fd2ab94282b53934022e4e4a03265582da83bf5/$(YT_DLP_WHEEL)

.PHONY: all install uninstall flatpak flatpak-install flatpak-run \
        deb deb-fetch-deps deb-clean clean help

all: help

help:
	@echo ""
	@echo "  Leaf Downloader — Build Targets"
	@echo "  ================================"
	@echo ""
	@echo "  System Install:"
	@echo "    make install          Install to $(PREFIX)"
	@echo "    make uninstall        Remove from $(PREFIX)"
	@echo ""
	@echo "  Debian Package:"
	@echo "    make deb              Build .deb package → $(DIST_DIR)/"
	@echo "    make deb-fetch-deps   Pre-download vendor wheels (for offline build)"
	@echo "    make deb-clean        Remove all Debian build artefacts"
	@echo ""
	@echo "  Flatpak:"
	@echo "    make flatpak          Build the Flatpak package"
	@echo "    make flatpak-install  Build and install Flatpak (user)"
	@echo "    make flatpak-run      Run the installed Flatpak"
	@echo ""
	@echo "  Utilities:"
	@echo "    make validate         Validate desktop & metainfo files"
	@echo "    make icons            Generate icon PNGs from SVG"
	@echo "    make clean            Remove build artifacts"
	@echo ""

# ---------------------------------------------------------------
# System Installation (non-Flatpak)
# ---------------------------------------------------------------

install:
	@echo "Installing Leaf Downloader to $(PREFIX)..."

	# Launcher
	install -Dm755 bin/leaf-downloader $(BINDIR)/leaf-downloader

	# Application files
	install -d $(APPDIR)
	install -Dm644 main.py $(APPDIR)/main.py
	cp -r leaf_downloader $(APPDIR)/

	# Desktop entry
	install -Dm644 data/$(APP_ID).desktop $(APPENTRY)/$(APP_ID).desktop

	# AppStream metainfo
	install -Dm644 data/$(APP_ID).metainfo.xml $(METAINFO)/$(APP_ID).metainfo.xml

	# Icons
	install -Dm644 data/icons/$(APP_ID).svg \
		$(ICONDIR)/scalable/apps/$(APP_ID).svg
	@for size in 48 64 128 256; do \
		if [ -f "data/icons/hicolor/$${size}x$${size}/apps/$(APP_ID).png" ]; then \
			install -Dm644 "data/icons/hicolor/$${size}x$${size}/apps/$(APP_ID).png" \
				"$(ICONDIR)/$${size}x$${size}/apps/$(APP_ID).png"; \
		fi; \
	done

	# Update icon/desktop caches — only on live system installs, not during
	# DESTDIR package builds (running here would embed cache files in the .deb).
	@if [ -z "$(DESTDIR)" ]; then \
	    gtk-update-icon-cache -f -t $(ICONDIR) 2>/dev/null || true; \
	    update-desktop-database $(APPENTRY) 2>/dev/null || true; \
	fi

	@echo "Done! Run with: leaf-downloader"

uninstall:
	@echo "Uninstalling Leaf Downloader from $(PREFIX)..."
	rm -f $(BINDIR)/leaf-downloader
	rm -rf $(APPDIR)
	rm -f $(APPENTRY)/$(APP_ID).desktop
	rm -f $(METAINFO)/$(APP_ID).metainfo.xml
	rm -f $(ICONDIR)/scalable/apps/$(APP_ID).svg
	@for size in 48 64 128 256; do \
		rm -f "$(ICONDIR)/$${size}x$${size}/apps/$(APP_ID).png"; \
	done
	-gtk-update-icon-cache -f -t $(ICONDIR) 2>/dev/null || true
	@echo "Done!"

# ---------------------------------------------------------------
# Flatpak
# ---------------------------------------------------------------

flatpak:
	flatpak-builder --force-clean build-dir $(APP_ID).yml

flatpak-install:
	flatpak-builder --force-clean --user --install build-dir $(APP_ID).yml

flatpak-run:
	flatpak run $(APP_ID)

# ---------------------------------------------------------------
# Development Utilities
# ---------------------------------------------------------------

validate:
	@echo "Validating desktop entry..."
	-desktop-file-validate data/$(APP_ID).desktop
	@echo ""
	@echo "Validating AppStream metainfo..."
	-appstreamcli validate data/$(APP_ID).metainfo.xml
	@echo ""
	@echo "Validating YAML manifest..."
	-python3 -c "import yaml; yaml.safe_load(open('$(APP_ID).yml')); print('YAML: OK')" 2>/dev/null || \
		python3 -c "import json, sys; print('YAML validation requires PyYAML'); sys.exit(0)"

icons:
	@echo "Generating icon PNGs from SVG..."
	python3 -c "\
import cairo; \
import gi; \
gi.require_version('Rsvg', '2.0'); \
from gi.repository import Rsvg; \
handle = Rsvg.Handle.new_from_file('data/icons/$(APP_ID).svg'); \
[( \
    (lambda s: ( \
        (lambda surface, ctx: ( \
            handle.render_document(ctx, (lambda vp: (setattr(vp, 'x', 0), setattr(vp, 'y', 0), setattr(vp, 'width', s), setattr(vp, 'height', s), vp))[-1])(Rsvg.Rectangle())), \
            surface.write_to_png(f'data/icons/hicolor/{s}x{s}/apps/$(APP_ID).png'), \
            print(f'  Generated {s}x{s}') \
        ))(cairo.ImageSurface(cairo.FORMAT_ARGB32, s, s), cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, s, s))) \
    ))(size) \
) for size in [48, 64, 128, 256]]"
	@echo "Done!"

clean:
	rm -rf build-dir .flatpak-builder
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
	@echo "Cleaned build artifacts."

# ---------------------------------------------------------------
# Debian Package Building
# ---------------------------------------------------------------

# deb-fetch-deps — Pre-download the pinned yt-dlp wheel into
# debian/vendor-wheels/ so that the build can proceed offline.
# debian/rules also downloads it on demand if this target is skipped.
deb-fetch-deps:
	@echo "Pre-fetching yt-dlp $(YT_DLP_VERSION) wheel for offline build …"
	@mkdir -p debian/vendor-wheels
	@python3 -c "\
import urllib.request, hashlib, sys, os; \
dest = 'debian/vendor-wheels/$(YT_DLP_WHEEL)'; \
if os.path.exists(dest): \
    print('  Already cached:', dest); \
else: \
    print('  Downloading …'); \
    urllib.request.urlretrieve('$(YT_DLP_URL)', dest); \
    print('  Saved to:', dest); \
digest = hashlib.sha256(open(dest, 'rb').read()).hexdigest(); \
expected = '$(YT_DLP_SHA256)'; \
if digest != expected: \
    print(f'SHA256 mismatch!\n  got:      {digest}\n  expected: {expected}', file=sys.stderr); \
    sys.exit(1); \
print('  SHA256 OK');"
	@echo "Done — run 'make deb' for an offline-capable build."

# deb — Build the .deb binary package and copy it to $(DIST_DIR)/.
#
# dpkg-buildpackage places output files one directory above the source
# tree (i.e. the workspace root in CI, or the parent directory locally).
# We copy them into dist/ afterwards for easy reference.
deb:
	@echo "Building Debian package (leaf-downloader) …"
	@mkdir -p $(DIST_DIR)
	dpkg-buildpackage --no-sign -b
	@echo "Collecting build artefacts into $(DIST_DIR)/ …"
	@find "$(CURDIR)/.." -maxdepth 1 \
	    \( -name 'leaf-downloader_*.deb' \
	    -o -name 'leaf-downloader_*.buildinfo' \
	    -o -name 'leaf-downloader_*.changes' \) \
	    -exec cp -v {} $(DIST_DIR)/ \;
	@echo ""
	@echo "✓ Package ready in $(DIST_DIR)/:"
	@ls -lh $(DIST_DIR)/leaf-downloader_*.deb 2>/dev/null || true
	@echo ""
	@echo "  Install with:  sudo dpkg -i $(DIST_DIR)/leaf-downloader_*.deb"
	@echo "  Lint with:     lintian $(DIST_DIR)/leaf-downloader_*.deb"

# deb-clean — Remove all Debian build artefacts.
# Runs dh_clean via debian/rules to ensure the Debian staging tree
# (debian/leaf-downloader/, debian/.debhelper/, etc.) is fully removed.
deb-clean:
	@echo "Cleaning Debian build artefacts …"
	fakeroot debian/rules clean 2>/dev/null || true
	rm -rf $(DIST_DIR)
	rm -rf debian/vendor-wheels
	@find "$(CURDIR)/.." -maxdepth 1 \
	    \( -name 'leaf-downloader_*.deb' \
	    -o -name 'leaf-downloader_*.buildinfo' \
	    -o -name 'leaf-downloader_*.changes' \
	    -o -name 'leaf-downloader_*.dsc' \) \
	    -delete 2>/dev/null || true
	@echo "Debian build artefacts removed."
