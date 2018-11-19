# 2018 Peter Petrik (zilolv at gmail dot com)
# GNU General Public License 2 any later version

import argparse
import os
import subprocess
import sys

thisDir = os.path.dirname(os.path.realpath(__file__))
resourcesDir = os.path.join(thisDir, "resources")


class QGISPackageError(Exception):
    pass


def sign_this(path, identity, keychain):
    try:
        args = ["codesign",
                "-s", identity,
                "-v"]

        if keychain:
            args += ["--keychain", keychainFile]

        args += [path]


        out = subprocess.check_output(args, stderr=subprocess.STDOUT, encoding='UTF-8')
        print(out.strip())
    except subprocess.CalledProcessError as err:
        if not "is already signed" in str(err.output):
            print(err.output)
            raise
        else:
            print(path + " is already signed")


def sign_bundle_content(qgisApp, identity, keychain):
    # sign all binaries/libraries but QGIS
    for root, dirs, files in os.walk(qgisApp, topdown=False):
        # first sign all binaries
        for file in files:
            filepath = os.path.join(root, file)
            filename, file_extension = os.path.splitext(filepath)
            if file_extension in [".dylib", ".so", ""] and os.access(filepath, os.X_OK):
                if not filepath.endswith("/Contents/MacOS/QGIS"):
                    sign_this(filepath, identity, keychain)

    # now sign resources
    # for root, dirs, files in os.walk(qgisApp, topdown=False):
    #     for file in files:
    #         filepath = os.path.join(root, file)
    #        filename, file_extension = os.path.splitext(filepath)
    #        if file_extension not in [".dylib", ".so", ""]:
    #            sign_this(filepath, identity)

    # now sign the directory
    print("Sign the app dir")
    sign_this(qgisApp + "/Contents/MacOS/QGIS", identity, keychain)
    sign_this(qgisApp, identity, keychain)


def verify_sign(path):
    args = ["codesign",
            "--verify",
            "--verbose",
            path]

    try:
        out = subprocess.check_output(args, stderr=subprocess.STDOUT, encoding='UTF-8')
        print(out.strip())
    except subprocess.CalledProcessError as err:
        print(err.output)
        raise


def print_identities(keychain):
    args = ["security",
            "find-identity",
            "-v", "-p",
            "codesigning"]

    if keychain:
        args += [keychain]

    try:
        out = subprocess.check_output(args, stderr=subprocess.STDOUT, encoding='UTF-8')
        print(out.strip())
    except subprocess.CalledProcessError as err:
        print(err.output)
        raise


parser = argparse.ArgumentParser(description='Package QGIS Application')

parser.add_argument('--bundle_directory',
                    required=True,
                    help='output directory with resulting QGIS.app bundle')
parser.add_argument('--outname', required=True, help="resulting file")
parser.add_argument('--sign',
                    required=False,
                    type=argparse.FileType('r'),
                    help='File with Apple signing identity')
parser.add_argument('--keychain',
                    required=False,
                    help="keychain file",
                    default=None)

pkg = False
dmg = True

args = parser.parse_args()
print("BUNDLE DIRECTORY: " + args.bundle_directory)
print("OUTNAME: " + args.outname)

qgisApp = os.path.join(args.bundle_directory, "QGIS.app")

if not os.path.exists(qgisApp):
    raise QGISPackageError(qgisApp + " does not exists")

identity = None
if args.sign:
    # parse token
    identity = args.sign.read().strip()
    if len(identity) != 40:
        raise QGISPackageError("ERROR: Looks like your ID is not valid, should be 40 char long")

keychainFile = args.keychain
if keychainFile:
    keychainFile = os.path.realpath(keychainFile)
    print("Using keychain " + keychainFile)
    if not os.path.exists(keychainFile):
        raise QGISPackageError("missing file " + keychainFile)
else:
    print("No keychain file specified")

print("Print available identities")
print_identities(keychainFile)

if identity:
    print("Signing the bundle")
    sign_bundle_content(qgisApp, identity, keychainFile)
    verify_sign(qgisApp)
else:
    print("Signing skipped, no identity supplied")

if pkg:
    print(100*"*")
    print("STEP: Create pkg installer")
    print(100*"*")
    pkgFile = args.outname.replace(".dmg", ".pkg")
    if os.path.exists(pkgFile):
        print("Removing old pkg")
        os.remove(pkgFile)

    args = ["productbuild",
            "--identifier", "co.uk.lutraconsulting.qgis",
            "--component", qgisApp,
            "/Applications",
            pkgFile
            ]
    subprocess.check_output(args)
    fsize = subprocess.check_output(["du", "-h", pkgFile])
    print("pkg done: \n" + fsize)

if dmg:
    print(100*"*")
    print("STEP: Create dmg image")
    print(100*"*")
    dmgFile = args.outname.replace(".pkg", ".dmg")
    if os.path.exists(dmgFile):
        print("Removing old dmg")
        os.remove(dmgFile)

    args = ["create-dmg",
            "--volname", "QGIS Installer",
            "--volicon", resourcesDir + "/QGIS.icns",
            "--background", resourcesDir + "/background.jpg",
            "--window-pos", "200", "120",
            "--window-size", "800", "600",
            "--icon-size", "120",
            "--icon", resourcesDir + "/qgis-icon-120x120.png" ,"300", "190",
            "--hide-extension", "QGIS.app",
            "--app-drop-link", "600", "185",
            "--eula", resourcesDir + "/EULA.txt",
            dmgFile,
            qgisApp
            ]

    out = subprocess.check_output(args, encoding='UTF-8')
    print(out)

    if identity:
        sign_this(dmgFile, identity, keychainFile)
        verify_sign(qgisApp)
    else:
        print("Signing skipped, no identity supplied")

    fsize = subprocess.check_output(["du", "-h", dmgFile], encoding='UTF-8')
    print("ALL DONE\n" + fsize)
