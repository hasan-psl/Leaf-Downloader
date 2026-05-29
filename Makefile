# Leaf Downloader — Build & Installation Makefile
# ==================================================

APP_ID = io.github.hasan_psl.LeafDownloader
PREFIX ?= /usr/local
DESTDIR ?=

# Directories
BINDIR     = $(DESTDIR)$(PREFIX)/bin
SHAREDIR   = $(DESTDIR)$(PREFIX)/share
APPDIR     = $(SHAREDIR)/leaf-downloader
ICONDIR    = $(SHAREDIR)/icons/hicolor
APPENTRY   = $(SHAREDIR)/applications
METAINFO   = $(SHAREDIR)/metainfo

.PHONY: all install uninstall flatpak flatpak-install flatpak-run clean help

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

	# Update icon cache if possible
	-gtk-update-icon-cache -f -t $(ICONDIR) 2>/dev/null || true
	-update-desktop-database $(APPENTRY) 2>/dev/null || true

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
