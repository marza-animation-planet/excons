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
import os
import subprocess


_hou_mscver = {
    "15.0": "11.0",
    "15.5": "14.0",
    "16.0": "14.0",
    "16.5": "14.0",
    "17.0": "14.1",
    "17.5": "14.1",
    "18.0": "14.1",
    "18.5": "14.1"
}

_hou_gccver = {
    "17.0": "6",
    "17.5": "6",
    "18.0": "6",
    "18.5": "6"
}

def GetOptionsString():
    return """HOUDINI OPTIONS
  with-houdini=<str> : Houdini version or install directory []"""

def SetupMscver():
    if sys.platform == "win32":
        excons.InitGlobals()
        mscver = excons.GetArgument("mscver", None)
        if mscver is None:
            houver = Version(full=False)
            if houver is not None:
                mscver = _hou_mscver.get(houver, None)
                if mscver is not None:
                    print("Using msvc %s" % mscver)
                    excons.SetArgument("mscver", mscver)

def SetupGccver():
    if sys.platform.startswith("linux"):
        excons.InitGlobals()
        # bypass the arguments cache by using ARGUMENTS rather than
        #   calling excons.GetArgument
        gccver = SCons.Script.ARGUMENTS.get("devtoolset", None)
        if gccver is None:
            mayaver = Version(full=False)
            if mayaver is not None:
                gccver = _hou_gccver.get(mayaver, "")
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
        return ".dylib"
    elif str(SCons.Script.Platform()) == "win32":
        return ".dll"
    else:
        return ".so"

def Plugin(env):
    env.Append(CPPDEFINES=["MAKING_DSO"])

def Version(asString=True, full=True):
    ver, _ = GetVersionAndDirectory(noexc=True)
    if ver is None:
        return (None if not asString else "")
    else:
        if not full or not asString:
            ver = ".".join(ver.split(".")[:2])
        if asString:
            return ver
        else:
            return float(ver)

def GetVersionAndDirectory(noexc=False):
    verexp = re.compile(r"\d+\.\d+\.\d+(\.\d+)?")
    hspec = excons.GetArgument("with-houdini")

    if hspec is None:
        msg = "Please set Houdini version or directory using with-houdini="
        if not noexc:
            raise Exception(msg)
        else:
            excons.WarnOnce(msg, tool="houdini")
            return (None, None)

    if not os.path.isdir(hspec):
        ver = hspec
        if not verexp.match(ver):
            msg = "Invalid Houdini version format: \"%s\"" % ver
            if not noexc:
                raise Exception(msg)
            else:
                excons.WarnOnce(msg, tool="houdini")
                return (None, None)
        if sys.platform == "win32":
            if excons.arch_dir == "x64":
                hfs = "C:/Program Files/Side Effects Software/Houdini %s" % ver
            else:
                hfs = "C:/Program Files (x86)/Side Effects Software/Houdini %s" % ver
        elif sys.platform == "darwin":
            hfs = "/Library/Frameworks/Houdini.framework/Versions/%s/Resources" % ver
        else:
            hfs = "/opt/hfs%s" % ver

    else:
        # retrive version from hfs
        hfs = hspec
        m = verexp.search(hfs)
        if not m:
            msg = "Could not figure out houdini version from path \"%s\". Please provide it using houdini-ver=" % hfs
            if not noexc:
                raise Exception(msg)
            else:
                excons.WarnOnce(msg, tool="houdini")
                return (None, None)
        else:
            ver = m.group(0)

        if sys.platform == "darwin":
            # Path specified by with-houdini should point the the version folder
            # Append the "Resources" as is expected in HFS environment variable
            hfs += "/Resources"

    if not os.path.isdir(hfs):
        msg = "Invalid Houdini directory: %s" % hfs
        if not noexc:
            raise Exception(msg)
        else:
            excons.WarnOnce(msg, tool="houdini")
            return (None, None)

    return (ver, hfs)

def Require(env):
    excons.AddHelpOptions(houdini=GetOptionsString())

    ver, hfs = GetVersionAndDirectory(noexc=True)
    if not ver or not hfs:
        return

    # Call hcustom -c, hcustom -m to setup compile and link flags

    hcustomenv = os.environ.copy()
    hcustomenv["HFS"] = hfs
    if sys.platform == "win32":
        # Oldver version of hcustom on windows require MSVCDir to be set
        cmntools = "VS%sCOMNTOOLS" % env["MSVC_VERSION"].replace(".", "")
        if cmntools in hcustomenv:
            cmntools = hcustomenv[cmntools]
            if cmntools.endswith("\\") or cmntools.endswith("/"):
                cmntools = cmntools[:-1]
            cmntools = excons.joinpath(os.path.split(os.path.split(cmntools)[0])[0], "VC")
            hcustomenv["MSVCDir"] = cmntools

    hcustom = "%s/bin/hcustom" % hfs

    cmd = "\"%s\" -c" % hcustom
    p = subprocess.Popen(cmd, shell=True, env=hcustomenv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = p.communicate()
    ccflags = out.decode("ascii").strip() if sys.version_info.major > 2 else out.strip()
    if not "DLLEXPORT" in ccflags:
        if sys.platform == "win32":
            ccflags += ' /DDLLEXPORT="__declspec(dllexport)"'
        else:
            ccflags += ' -DDLLEXPORT='
    if sys.platform != "win32":
        if int(ver.split(".")[0]) >= 14:
            if not "-std=c++11" in ccflags:
                ccflags += ' -DBOOST_NO_DEFAULTED_FUNCTIONS -DBOOST_NO_DELETED_FUNCTIONS'

    cmd = "\"%s\" -m" % hcustom
    p = subprocess.Popen(cmd, shell=True, env=hcustomenv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, _ = p.communicate()
    linkflags = out.decode("ascii").strip() if sys.version_info.major > 2 else out.strip()
    if sys.platform == "win32":
        linkflags = re.sub(r"-link\s+", "", linkflags)
    elif sys.platform != "darwin":
        # On linux, $HFS/dsolib doesn't seem appear in linkflags
        linkflags += " -L %s/dsolib" % hfs
    else:
        # On OSX, linkflags does not provide frameworks or libraries to link
        libs = [
            "HoudiniUI", "HoudiniOPZ", "HoudiniOP3", "HoudiniOP2", "HoudiniOP1",
            "HoudiniSIM", "HoudiniGEO", "HoudiniPRM", "HoudiniUT"]

        libdir = "%s/Libraries" % "/".join(hfs.split("/")[:-1])
        linkflags += " -flat_namespace -L %s -l%s" % (libdir, " -l".join(libs))

    env.Append(CXXFLAGS=" %s" % ccflags)
    env.Append(LINKFLAGS=" %s" % linkflags)
