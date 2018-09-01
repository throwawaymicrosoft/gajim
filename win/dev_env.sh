#!/usr/bin/env bash

set -e

function main {
    pacman --noconfirm -S --needed \
        git \
        mingw-w64-i686-toolchain \
        mingw-w64-i686-gdk-pixbuf2 \
        mingw-w64-i686-gtk3 \
        mingw-w64-i686-gstreamer \
        intltool \
        mingw-w64-i686-sqlite3 \
        mingw-w64-i686-python3 \
        mingw-w64-i686-python3-gobject \
        mingw-w64-i686-python3-pip \
        mingw-w64-i686-sqlite3

    pip3 install setuptools_scm

    PIP_REQUIREMENTS="\
certifi
git+https://dev.gajim.org/gajim/python-nbxmpp.git
git+https://dev.gajim.org/lovetox/pybonjour-python3.git 
protobuf
cryptography
pyopenssl
python-gnupg
docutils
qrcode
keyring
pillow==4.3.0
"

    pip3 install --no-binary ":all:" \
        --force-reinstall $(echo "$PIP_REQUIREMENTS" | tr ["\\n"] [" "])

    pip3 install python-axolotl

}

main;
