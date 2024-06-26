# MIT License
#
# Copyright (c) 2013 Gaetan Guidet
#
# This file is part of excons.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import SCons.Script # pylint: disable=import-error
import excons
import excons.devtoolset
import sys
import re
import io
import os


_maya_mscver = {
    "2013": "9.0",
    "2013.5": "9.0",
    "2014": "10.0",
    "2015": "11.0",
    "2016": "11.0",
    "2016.5": "11.0",
    "2017": "11.0",
    "2018": "14.0",
    "2019": "14.0",
    "2020": "14.1",
    "2022": "14.2",
    "2023": "14.2",
    "2024": "14.3"
}

_maya_gccver = {
    "2019": "6",
    "2020": "6",
    "2022": "9",
    "2023": "9",
    "2024": "11"
}

def GetOptionsString():
    return """MAYA OPTIONS
  with-maya=<str>        : Version or Maya install directory []
  with-mayadevkit=<path> : Maya platform devkit path         []"""

def SetupMscver():
    if sys.platform == "win32":
        excons.InitGlobals()
        # bypass the arguments cache by using ARGUMENTS rather than
        #  calling excons.GetArgument
        mscver = SCons.Script.ARGUMENTS.get("mscver", None)
        if mscver is None:
            mayaver = Version(nice=True)
            if mayaver is not None:
                mscver = _maya_mscver.get(mayaver, None)
                if mscver is not None:
                    print("Using msvc %s" % mscver)
                    excons.SetArgument("mscver", mscver)

def SetupGccver():
    if sys.platform.startswith("linux"):
        excons.InitGlobals()
        # bypass the arguments cache by using ARGUMENTS rather than
        #  calling excons.GetArgument
        gccver = SCons.Script.ARGUMENTS.get("devtoolset", None)
        if gccver is None:
            mayaver = Version(nice=True)
            if mayaver is not None:
                gccver = _maya_gccver.get(mayaver, "")
                if gccver is not None:
                    print("Using gcc %s" % excons.devtoolset.GetGCCFullVer(gccver))
                    excons.SetArgument("devtoolset", gccver)

def SetupCompiler():
    if sys.platform == "win32":
        SetupMscver()
    else:
        SetupGccver()

def PluginExt():
    if str(SCons.Script.Platform()) == "darwin":
        return ".bundle"
    elif str(SCons.Script.Platform()) == "win32":
        return ".mll"
    else:
        return ".so"

def Plugin(env):
    if not sys.platform in ["win32", "darwin"]:
        env.Append(LINKFLAGS=" -Wl,-Bsymbolic")

def GetMayaRoot(noWarn=False):
    mayaspec = excons.GetArgument("with-maya")

    if "MAYA_LOCATION" in os.environ:
        if not "with-maya" in SCons.Script.ARGUMENTS:
            # MAYA_LOCATION environment is set and with-maya is either undefined or read from cache
            excons.PrintOnce("Using MAYA_LOCATION environment.", tool="maya")
            mayadir = os.environ["MAYA_LOCATION"]
            return mayadir
        else:
            excons.PrintOnce("Ignoring MAYA_LOCATION environment.", tool="maya")

    if not mayaspec:
        if not noWarn:
            #excons.WarnOnce("Please set Maya version or directory using with-maya=", tool="maya")
            excons.WarnConfig()
        return None

    if not os.path.isdir(mayaspec):
        if not re.match(r"\d+(\.\d+)?", mayaspec):
            if not noWarn:
                excons.WarnOnce("Invalid Maya specification \"%s\": Must be a directory or a version number" % mayaspec, tool="maya")
            return None
        ver = mayaspec
        if sys.platform == "win32":
            if excons.arch_dir == "x64":
                mayadir = "C:/Program Files/Autodesk/Maya%s" % ver
            else:
                mayadir = "C:/Program Files (x86)/Autodesk/Maya%s" % ver
        elif sys.platform == "darwin":
            mayadir = "/Applications/Autodesk/maya%s" % ver
        else:
            mayadir = "/usr/autodesk/maya%s" % ver
            if excons.arch_dir == "x64" and os.path.isdir(mayadir+"-x64"):
                mayadir += "-x64"

    else:
        mayadir = mayaspec.replace("\\", "/")
        if len(mayadir) > 0 and mayadir[-1] == "/":
            mayadir = mayadir[:-1]

    return mayadir

def GetMayaInc(mayadir):
    # Starting maya 2016, the base install doesn't come with include files
    require_mdk = False
    if sys.platform == "darwin":
        require_mdk = not os.path.isdir(mayadir + "/devkit/include/maya")
    else:
        require_mdk = not os.path.isdir(mayadir + "/include/maya")

    mdk = (None if not require_mdk else excons.GetArgument("with-mayadevkit"))

    if "MAYA_INCLUDE" in os.environ:
        if not require_mdk or "with-mayadevkit" not in SCons.Script.ARGUMENTS:
            # MAYA_INCLUDE environment is set and maya is older than 2016 or with-mayadevkit is either undefined or read from cache
            excons.PrintOnce("Using MAYA_INCLUDE environment.", tool="maya")
            mayainc = os.environ["MAYA_INCLUDE"]
            return mayainc
        else:
            excons.PrintOnce("Ignoring MAYA_INCLUDE environment.", tool="maya")

    if mdk is None:
        if sys.platform == "darwin":
            mayainc = mayadir + "/devkit/include"
        else:
            mayainc = mayadir + "/include"

    else:
        mdk = mdk.replace("\\", "/")
        if len(mdk) > 0 and mdk[-1] == "/":
            mdk = mdk[:-1]

        if os.path.isabs(mdk):
            mayainc = mdk + "/include"
        else:
            mayainc = mayadir + "/" + mdk + "/include"

    return mayainc

def GetMayaLib(mayadir):
    if sys.platform == "darwin":
        return "%s/Maya.app/Contents/MacOS" % mayadir
    else:
        return "%s/lib" % mayadir

def Version(asString=True, nice=False):
    mayadir = GetMayaRoot(noWarn=True)
    if not mayadir:
        return (None if not asString else "")

    mayainc = GetMayaInc(mayadir)

    mayaspec = excons.GetArgument("with-maya")
    if mayaspec is not None and not os.path.isdir(mayaspec):
        wantedver = mayaspec
    else:
        wantedver = None

    mtypes = excons.joinpath(mayainc, "maya", "MTypes.h")

    if os.path.isfile(mtypes):
        defexp = re.compile(r"^\s*#define\s+MAYA_API_VERSION\s+([0-9]+)")
        f = io.open(mtypes, "r", encoding="UTF-8", newline="\n")
        for line in f.readlines():
            m = defexp.match(line)
            if m:
                year = int(m.group(1)[:4])
                sub = int(m.group(1)[4])
                if wantedver is not None:
                    usever = "%d%s" % (year, ".5" if sub >= 5 else "")
                    if usever != wantedver:
                        excons.WarnOnce("Maya headers version (%s) doesn't seem to match requested one (%s).\nMake sure to set or reset devkit path using 'with-mayadevkit=' flag." % (usever, wantedver))
                if nice:
                    # Maya 2013 and 2016 have a binary incompatible .5 version
                    if sub >= 5 and year in (2013, 2016):
                        return (year+0.5 if not asString else "%d.5" % year)
                    else:
                        return (year if not asString else str(year))
                else:
                    return (int(m.group(1)) if not asString else m.group(1))
        f.close()

    excons.WarnOnce("Cannot find maya headers (missing with-mayadevkit= ?).")
    return (None if not asString else "")

def Require(env):
    excons.AddHelpOptions(maya=GetOptionsString())

    mayadir = GetMayaRoot()
    if not mayadir:
        return

    env.Append(CPPPATH=[GetMayaInc(mayadir)])
    env.Append(CPPDEFINES=["REQUIRE_IOSTREAM", "_BOOL"])

    if sys.platform == "darwin":
        env.Append(CPPDEFINES=["OSMac_"])
        env.Append(CPPFLAGS=" -Wno-unused-private-field")
        env.Append(LIBPATH=["%s/Maya.app/Contents/MacOS" % mayadir])
        mach = "%s/maya/OpenMayaMac.h" % GetMayaInc(mayadir)

        if os.path.isfile(mach):
            env.Append(CCFLAGS=" -include \"%s\" -fno-gnu-keywords" % mach)

        maya_ver = Version(asString=False, nice=True)
        if maya_ver:
            # Starting Maya 2017, on osx libc++ is used instead of libstdc++
            # Before this version, and unless explicitely overridden by 'use-c++11=' command line flag, use c++0x and libstdc++
            if maya_ver < 2017:
                excons.WarnOnce("Maya below 2017 requires linking against libstdc++.\nThis can be done using by using the command line flag 'use-stdc++=1'.", tool="maya")
            # Starting Maya 2018, Maya API is using C++11 standard
            if maya_ver >= 2018:
                env.Append(CPPFLAGS=" -std=c++11")
    else:
        env.Append(LIBPATH=["%s/lib" % mayadir])
        if sys.platform == "win32":
            env.Append(CPPDEFINES=["NT_PLUGIN"])
        else:
            maya_ver = Version(asString=False, nice=True)
            # Starting Maya 2018, Maya API is using C++11 standard
            if maya_ver and maya_ver in [2018, 2019, 2020]:
                env.Append(CPPFLAGS=" -std=c++11")
            # Starting Maya 2022, Maya API is using C++14 standard
            # Not sure about Maya 2024
            elif maya_ver and maya_ver >= 2022:
                env.Append(CPPFLAGS=" -std=c++14")

            env.Append(CPPDEFINES=["LINUX"])
            env.Append(CPPFLAGS=" -fno-strict-aliasing -Wno-comment -Wno-sign-compare -funsigned-char -Wno-reorder -fno-gnu-keywords -pthread")

    env.Append(LIBS=["OpenMaya", "OpenMayaAnim", "OpenMayaFX", "OpenMayaRender", "OpenMayaUI", "Foundation"])
