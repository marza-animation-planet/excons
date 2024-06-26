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
import sys
import re
import io
import os


def GetOptionsString():
    return """ARNOLD OPTIONS
  with-arnold=<path>     : Arnold root directory.
  with-arnold-inc=<path> : Arnold headers directory.   [<root>/include]
  with-arnold-lib=<path> : Arnold libraries directory. [<root>/bin or <prefix>/lib]"""

def PluginExt():
    if str(SCons.Script.Platform()) == "darwin":
        return ".dylib"
    elif str(SCons.Script.Platform()) == "win32":
        return ".dll"
    else:
        return ".so"

def Version(asString=True, compat=False):
    arnoldinc, _ = excons.GetDirs("arnold", libdirname=("bin" if sys.platform != "win32" else "lib"))

    if arnoldinc is None:
        if compat:
            return ("0.0" if asString else (0, 0))
        else:
            return ("0.0.0.0" if asString else (0, 0, 0, 0))

    ai_version = excons.joinpath(arnoldinc, "ai_version.h")

    varch, vmaj, vmin, vpatch = 0, 0, 0, 0

    if os.path.isfile(ai_version):
        defexp = re.compile(r"^\s*#define\s+AI_VERSION_(ARCH_NUM|MAJOR_NUM|MINOR_NUM|FIX)\s+([^\s]+)")
        with io.open(ai_version, "r", encoding="UTF-8", newline="\n") as f:
            for line in f.readlines():
                m = defexp.match(line)
                if m:
                    which = m.group(1)
                    if which == "ARCH_NUM":
                        varch = int(m.group(2))
                    elif which == "MAJOR_NUM":
                        vmaj = int(m.group(2))
                    elif which == "MINOR_NUM":
                        vmin = int(m.group(2))
                    elif which == "FIX":
                        m = re.search(r"\d+", m.group(2))
                        vpatch = (0 if m is None else int(m.group(0)))

    rv = (varch, vmaj, vmin, vpatch)

    if compat:
        cv = (rv[0], rv[1])
        return ("%s.%s" % cv if asString else cv)
    else:
        return ("%s.%s.%s.%s" % rv if asString else rv)

def Require(env):
    arnoldinc, arnoldlib = excons.GetDirs("arnold", libdirname=("bin" if sys.platform != "win32" else "lib"))

    if arnoldinc:
        env.Append(CPPPATH=[arnoldinc])

    if arnoldlib:
        env.Append(LIBPATH=[arnoldlib])

    aver = Version(asString=False)
    if aver[0] >= 5:
        if sys.platform == "win32":
            if float(excons.mscver) < 14:
                excons.WarnOnce("Arnold 5 and above require Visual Studio 2015 or newer (mscver 14.0)")
    if aver[0] >= 6:
        if sys.platform != "win32":
            if not excons.GetArgument("use-c++11", 0, int):
                excons.SetArgument("use-c++11", 1)
            if not "-std=c++11" in " ".join(env["CXXFLAGS"]):
                env.Append(CXXFLAGS=" -std=c++11")

    env.Append(LIBS=["ai"])

    excons.AddHelpOptions(arnold=GetOptionsString())
