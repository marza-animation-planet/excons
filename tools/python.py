# MIT License
#
# Copyright (c) 2009 Gaetan Guidet
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
import os
import re
import sys
import subprocess
import excons
import distutils
import distutils.sysconfig


def GetOptionsString():
    return """PYTHON OPTIONS
  with-python=<str> : Python version or prefix [current interpreter]"""

def _GetPythonVersionOSX(pythonPath):
    # On osx, pythonPath must be the path to the python framework
    # i.e.  with-python=/System/Library/Frameworks/Python.framework
    p = subprocess.Popen("ls -l %s/Versions | grep Current" % pythonPath, shell=True, stdout=subprocess.PIPE)
    out, _ = p.communicate()
    m = re.search(r"Current\s+->\s+(%s/Versions/)?([0-9\.]+)" % pythonPath, out.decode("ascii") if sys.version_info.major >= 3 else out)
    if m is not None:
        return m.group(2)
    return None

def _GetPythonVersionWIN(pythonPath):
    # On windows, pythonPath must be the path to the python executable
    # i.e.  with-python=C:/Python27/python.exe
    dn = os.path.dirname(pythonPath)
    fl = excons.glob(excons.joinpath(dn, "python*.dll"))
    if len(fl) == 1:
        m = re.match(r"python(\d)(\d)\.dll", os.path.basename(fl[0]), re.IGNORECASE)
        if m is not None:
            return "%s.%s" % (m.group(1), m.group(2))
    return None

def _GetPythonVersionUNIX(pythonPath):
    # On unix, pythonPath must be the path to the python executable
    # i.e.  with-python=/usr/local/bin/python
    p = subprocess.Popen("ldd %s | grep libpython" % pythonPath, shell=True, stdout=subprocess.PIPE)
    out, _ = p.communicate()
    m = re.search(r"libpython([0-9\.]+m?)\.so", out.decode("ascii") if sys.version_info.major >= 3 else out)
    if m is not None:
        return m.group(1)
    return None

_specCache = {}

def _GetPythonSpec(specString):
    if specString in _specCache:
        return _specCache[specString]

    spec = None
    specErr = ""

    plat = str(SCons.Script.Platform())

    if re.match(r"\d+\.\d+", specString):
        ver = specString

        # Look in standard locations

        if plat == "darwin":
            searchPaths = ["/System/Library/Frameworks", "/Library/Frameworks"]
            for searchPath in searchPaths:
                pythonPath = excons.joinpath(searchPath, "Python.framework", "Versions", ver)
                if os.path.isdir(pythonPath):
                    incdir = None
                    for isd in ("include/python%s" % ver, "Headers"):
                        _incdir = pythonPath + "/" + isd
                        if os.path.isdir(_incdir):
                            incdir = _incdir
                            break
                    if incdir is not None:
                        if ver == _GetPythonVersionOSX(excons.joinpath(searchPath, "Python.framework")):
                            spec = (ver, incdir, searchPath, "Python")
                            specErr = ""
                            break
                        else:
                            spec = (ver, incdir, None, "%s/Python" % (pythonPath))
                            specErr = ""
                            break
                    else:
                        specErr += "\n  Cannot find python %s include directory in %s" % (ver, pythonPath)
                else:
                    specErr += "\n  Cannot find python %s in %s" % (ver, searchPath)

        elif plat == "win32":
            # use path from where python is called
            pythonPath = sys.exec_prefix 
            # let's assume that if python running from virtualenv use real python path
            # because virtual env on windows is unreliable > 2.7
            if "VIRTUAL_ENV" in os.environ:
                pythonPath = sys.real_prefix if sys.version_info.major < 3 else sys.base_prefix

            if os.path.isdir(pythonPath):
                incdir = excons.joinpath(pythonPath, "include")
                libdir = excons.joinpath(pythonPath, "libs")
                lib = "python%s" % ver.replace(".", "")
                spec = (ver, incdir, libdir, lib)

        else:
            searchPath = distutils.sysconfig.get_config_var("BINDIR")
            spec = (ver, searchPath)

            if spec:
                ver, prefix = spec
                incdir = distutils.sysconfig.get_python_inc()
                libdir = distutils.sysconfig.get_config_var("LIBDIR")
                lib = "python%s" % distutils.sysconfig.get_config_var("LDVERSION")
                spec = (ver, incdir, libdir, lib)

        if spec is None:
            curver = str(distutils.sysconfig.get_python_version())
            specErr += "\n"
            if curver != ver:
                excons.PrintOnce("Couldn't find stock python %s.%sCurrent version doesn't match (%s), aborting build." % (ver, specErr, curver), tool="python")
                sys.exit(1)
            else:
                excons.PrintOnce("Couldn't find stock python %s.%sUse currently running version instead." % (ver, specErr), tool="python")

    else:
        if plat == "darwin":
            if specString[-1] == "/":
                specString = specString[:-1]
            m = re.search(r"/([^/]+)\.framework/Versions/([^/]+)/?$", specString)
            if m:
                fwn = m.group(1)
                ver = m.group(2)
                fw = "%s/%s" % (specString, fwn)
                fwh = "%s/Headers" % specString
                if not os.path.isdir(fwh):
                    fwh = "%s/include/python%s" % (specString, ver)
                if os.path.isfile(fw) and os.path.isdir(fwh):
                    # if it is the current version, use framework directory
                    fwd = re.sub(r"/Versions/.*$", "", specString)
                    if ver == _GetPythonVersionOSX(fwd):
                        spec = (ver, fwh, os.path.dirname(fwd), fwn)
                    else:
                        spec = (ver, fwh, None, fw)
                else:
                    if not os.path.isfile(fwh):
                        specErr += "\n  Cannot find python %s include directory in %s" % (ver, specString)
                    if not os.path.isfile(fw):
                        specErr += "\n  Cannot find python framework in %s" % specString
            else:
                ver = _GetPythonVersionOSX(specString)
                if ver is not None:
                    d = os.path.dirname(specString)
                    n = os.path.splitext(os.path.basename(specString))[0]
                    incdir = None
                    for isd in ("include/python%s" % ver, "Headers"):
                        _incdir = "%s/Versions/%s/%s" % (specString, ver, isd)
                        if os.path.isdir(_incdir):
                            incdir = _incdir
                            break
                    if incdir is not None:
                        spec = (ver, incdir, d, n)
                    else:
                        specErr += "\n  Cannot find python %s include directory in %s" % (ver, specString)

        elif plat == "win32":
            ver = _GetPythonVersionWIN(specString)
            if ver is not None:
                d = os.path.dirname(specString)
                incdir = excons.joinpath(d, "include")
                libdir = excons.joinpath(d, "libs")
                lib = "python%s" % ver.replace(".", "")
                spec = (ver, incdir, libdir, lib)

        else:
            ver = _GetPythonVersionUNIX(specString)
            if ver is not None:
                # not specString but 2 dirs up (as specString is the path to the python executable)
                d = os.path.dirname(specString)
                if os.path.basename(d) == "bin":
                    d = os.path.dirname(d)
                    incdir = excons.joinpath(d, "include", "python%s" % ver)
                    libdir = excons.joinpath(d, ("lib64" if excons.Build64() else "lib"))
                    lib = "python%s" % ver
                    spec = (ver, incdir, libdir, lib)

        if spec is None:
            specErr += "\n"
            excons.PrintOnce("[1] Invalid python specification \"%s\".%sAborting build." % (specErr, specString), tool="python")
            sys.exit(1)

    # check setup validity
    if spec is not None:
        if plat == "darwin":
            _, incdir, fwdir, fw = spec
            if fwdir is None:
                # directly linking version specific framework
                if not os.path.isdir(incdir) or not os.path.isfile(fw):
                    excons.PrintOnce("Cannot find incdir '%s' or fw '%s'" % (incdir, fw), tool="python")
                    spec = None
            else:
                if not os.path.isdir(incdir) or not os.path.isdir(fwdir):
                    excons.PrintOnce("Cannot find incdir '%s' or fwdir '%s'" % (incdir, fwdir), tool="python")
                    spec = None
        else:
            ver, incdir, libdir, lib = spec
            if not os.path.isdir(incdir) or not os.path.isdir(libdir):
                excons.PrintOnce("Cannot find incdir '%s' or libdir '%s'" % (incdir, libdir), tool="python")
                spec = None
            else:
                if plat == "win32":
                    if not os.path.isfile(excons.joinpath(libdir, "%s.lib" % lib)):
                        excons.PrintOnce("Cannot find '%s'" % (excons.joinpath(libdir, "%s.lib" % lib)), tool="python")
                        spec = None
                else:
                    ldlib = distutils.sysconfig.get_config_var("LDLIBRARY")
                    if not distutils.sysconfig.get_config_var("Py_ENABLE_SHARED"):
                        excons.PrintOnce("Cannot find '%s'" % ldlib, tool="python")
                        spec = None

        if spec is None:
            excons.PrintOnce("[2] Invalid python specification \"%s\". Aborting build." % specString, tool="python")
            sys.exit(1)

    excons.PrintOnce("Resolved python for \"%s\": %s" % (specString, ('<current>' if spec is None else spec)), tool="python")

    _specCache[specString] = spec

    return spec

def Version():
    po = excons.GetArgument("with-python")

    if po is not None:
        rv = _GetPythonSpec(po)
        if rv is not None:
            return rv[0]

    return str(distutils.sysconfig.get_python_version())

def Require(e, ignoreLinkFlags=False):
    po = excons.GetArgument("with-python")

    if po is not None:
        rv = _GetPythonSpec(po)

        if rv is not None:
            ver, incdir, libdir, lib = rv
            plat = str(SCons.Script.Platform())

            e.Append(CCFLAGS=" -DPY_VER=%s" % ver)
            e.Append(CPPPATH=[incdir])

            if not ignoreLinkFlags:
                if plat == "darwin":
                    if libdir:
                        e.Append(LINKFLAGS=" -F%s -framework %s" % (libdir, lib))
                    else:
                        e.Append(LINKFLAGS=" %s" % lib)
                else:
                    e.Append(LIBPATH=[libdir])
                    e.Append(LIBS=[lib])

            return

    # Default settings: use the python that this script runs on

    pyver = distutils.sysconfig.get_python_version()
    e.Append(CCFLAGS=" -DPY_VER=%s" % pyver)
    e.Append(CPPPATH=[distutils.sysconfig.get_python_inc()])

    if distutils.sysconfig.get_config_var("PYTHONFRAMEWORK"):
        if not ignoreLinkFlags:
            fwdir = distutils.sysconfig.get_config_var("PYTHONFRAMEWORKPREFIX")
            fwname = distutils.sysconfig.get_config_var("PYTHONFRAMEWORK")
            if _GetPythonVersionOSX("%s/%s.framework" % (fwdir, fwname)) != pyver:
                e.Append(LINKFLAGS=" %s/%s.framework/Versions/%s/%s" % (fwdir, fwname, pyver, fwname))
            else:
                e.Append(LINKFLAGS=" -F%s -framework %s" % (fwdir, fwname))
    else:
        if str(SCons.Script.Platform()) == "win32":
            e.Append(LIBPATH=[distutils.sysconfig.PREFIX+'\\libs'])
            e.Append(LIBS=["python%s" % pyver.replace(".", "")])
        else:
            pyver = distutils.sysconfig.get_config_var("LDVERSION")
            e.Append(CCFLAGS=" %s" % distutils.sysconfig.get_config_var("CFLAGS"))
            if not ignoreLinkFlags:
                e.Append(LINKFLAGS=" %s" % distutils.sysconfig.get_config_var("LINKFORSHARED"))
                e.Append(LIBS=["python%s" % pyver])

    excons.AddHelpOptions(python=GetOptionsString())

def SoftRequire(e):
    if str(SCons.Script.Platform()) == "darwin":
        e.Append(LINKFLAGS=" -undefined dynamic_lookup")
        Require(e, ignoreLinkFlags=True)
    else:
        Require(e)

def ModulePrefix():
    return "lib/python/"

def ModuleExtension():
    return distutils.sysconfig.get_config_var("SO" if sys.version_info.major < 3 else "EXT_SUFFIX")


_cython = ""

def RequireCython(e):
    global _cython

    cython = excons.GetArgument("with-cython", _cython)
    if not os.path.isfile(cython):
        excons.PrintOnce("Invalid 'cython' specification", tool="python")
        cython = None
    if not cython:
        cython = "cython%s" % Version()
        path = excons.Which(cython)
        if path is None:
            excons.PrintOnce("No \"%s\" found in PATH. Try with \"cython\" instead" % cython, tool="python")
            cython = "cython"
            path = excons.Which(cython)
            if path is None:
                excons.PrintOnce("Cannot find a valid cython in your PATH, use with-cython= flag to provide a valid location.", tool="python")
                return False
        excons.PrintOnce("Use \"%s\" found in %s." % (cython, path), tool="python")

    _cython = cython

    cython_include_re = re.compile(r"^include\s+([\"'])(\S+)\1", re.MULTILINE)

    def scan_cython_includes(node, env, path):
        if hasattr(node, "get_text_contents"):
            lst = [m[1] for m in cython_include_re.findall(node.get_text_contents())]
            return lst
        elif hasattr(node, "get_contents"):
            lst = [m[1] for m in cython_include_re.findall(str(node.get_contents()))]
            return lst
        else:
            return []

    e.Append(SCANNERS=SCons.Script.Scanner(function=scan_cython_includes, skeys=".pyx"))

    return True

def CythonGenerate(e, pyx, h=None, c=None, incdirs=None, cpp=False, cte=None, directives=None):
    global _cython

    if incdirs is None:
        incdirs = []

    if cte is None:
        cte = {}

    if directives is None:
        directives = {}

    if float(Version()) < 3:
        directives["language_level"] = 2
    else:
        # really?
        directives["language_level"] = 3

    if not _cython:
        excons.PrintOnce("No 'cython' to generate %s" % pyx, tool="python")
        return None

    if h is None:
        h = os.path.splitext(pyx)[0] + ".h"

    if c is None:
        c = os.path.splitext(pyx)[0] + (".cpp" if cpp else ".c")

    cteflags = "".join([" -E %s=%s" % (k, v) for k, v in cte.items()])
    dirflags = "".join([" --directive %s=%s" % (k, v) for k, v in directives.items()])
    cmd = _cython + " " + " ".join(["-I %s" % x for x in incdirs]) + (" --cplus" if cpp else "") + cteflags + dirflags + " --embed-positions -o $TARGET $SOURCE"

    # Command seems to fail if PATH and PYTHONPATH are not set
    ec = e.Clone()
    ec["ENV"]["PATH"] = os.environ.get("PATH", "")
    ec["ENV"]["PYTHONPATH"] = os.environ.get("PYTHONPATH", "")
    return ec.Command([c, h], pyx, cmd)

def SilentCythonWarnings(env):
    plat = str(SCons.Script.Platform())
    if plat == "darwin":
        env.Append(CPPFLAGS=" -Wno-unused-function -Wno-unneeded-internal-declaration")
    elif plat != "win32":
        env.Append(CPPFLAGS=" -Wno-strict-aliasing")
    else:
        env.Append(CPPFLAGS=" /wd4310 /wd4706")
