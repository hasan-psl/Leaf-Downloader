#!/usr/bin/env python3
import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from leaf_downloader.app import LeafDownloaderApp

def main():
    app = LeafDownloaderApp()
    return app.run(sys.argv)

if __name__ == '__main__':
    sys.exit(main())
