# -*- coding: utf8 -*-
#
#   pyrayopt - raytracing for optical imaging systems
#   Copyright (C) 2012 Robert Jordens <jordens@phys.ethz.ch>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

from enthought.traits.api import (HasTraits, List, Float, Array, Dict,
        Bool, Str, Instance, Trait, cached_property, Property, Callable,
        Tuple, Enum)

from numpy import (array, sqrt, ones_like, float64, dot, sign, zeros,
        linalg, where, nan, nan_to_num, finfo, inf, mgrid, ones,
        concatenate, linspace, putmask, zeros_like, extract)


lambda_f = 486.1e-9
lambda_d = 589.3e-9
lambda_c = 656.3e-9


class Material(HasTraits):
    name = Str
    comment = Str
    glasscode = Float
    nd = Float
    vd = Float
    density = Float
    alpham3070 = Float
    alpha20300 = Float
    chemical = Tuple
    thermal = Tuple
    price = Float
    transmission = Dict
    sellmeier = Array(dtype=float64, shape=(None, 2))

    def __str__(self):
        return self.name

    def refractive_index(self, wavelength):
        w2 = (wavelength/1e-6)**2
        c0 = self.sellmeier[:,0]
        c1 = self.sellmeier[:,1]
        n2 = 1.+(c0*w2/(w2-c1)).sum(-1)
        return sqrt(n2)

    def _nd_default(self):
        return self.refractive_index(lambda_d)

    def dispersion(self, wavelength_short, wavelength_mid,
            wavelength_long):
        return (self.refractive_index(wavelength_mid)-1)/(
                self.refractive_index(wavelength_short)-
                self.refractive_index(wavelength_long))

    def delta_n(self, wavelength_short, wavelength_long):
        return (self.refractive_index(wavelength_short)-
                self.refractive_index(wavelength_long))

    def _vd_default(self):
        return (self.nd-1)/(
                self.refractive_index(lambda_f)-
                self.refractive_index(lambda_c))

    def dn_thermal(self, t, n, wavelength):
        d0, d1, d2, e0, e1, tref, lref = self.thermal
        dt = t-tref
        w = wavelength/1e-6
        dn = (n**2-1)/(2*n)*(d0*dt+d1*dt**2+d2*dt**3+
                (e0*dt+e1*dt**2)/(w**2-lref**2))
        return dn


class FictionalMaterial(Material):
    def refractive_index(self, wavelength):
        return ones_like(wavelength)*self.nd

    def dispersion(self, wavelength_short, wavelength_mid,
            wavelength_long):
        return ones_like(wavelength_mid)*self.vd

    def delta_n(self, wavelength_short, wavelength_long):
        return (self.nd-1)/self.vd*ones_like(wavelength_short)


class GlassCatalog(HasTraits):
    db = Dict(Str, Instance(Material))
    name = Str

    def __getitem__(self, name):
        return self.db[name]

    def import_zemax(self, fil):
        dat = open(fil)
        for line in dat:
            try:
                cmd, args = line.split(" ", 1)
                if cmd == "CC":
                    self.name = args
                elif cmd == "NM":
                    args = args.split()
                    g = Material(name=args[0], glasscode=float(args[2]),
                            nd=float(args[3]), vd=float(args[4]))
                    self.db[g.name] = g
                elif cmd == "GC":
                    g.comment = args
                elif cmd == "ED":
                    args = map(float, args.split())
                    g.alpham3070, g.alpha20300, g.density = args[0:3]
                elif cmd == "CD":
                    s = array(map(float, args.split())).reshape((-1,2))
                    g.sellmeier = array([si for si in s if not si[0] == 0])
                elif cmd == "TD":
                    s = map(float, args.split())
                    g.thermal = s
                elif cmd == "OD":
                    g.chemical = map(float, s[1:])
                    g.price = s[0]=="-" and None or float(s[0])
                elif cmd == "LD":
                    s = map(float, args.split())
                    pass
                elif cmd == "IT":
                    s = map(float, args.split())
                    g.transmission[(s[0], s[2])] = s[1]
                else:
                    print cmd, args, "not handled"
            except Exception, e:
                print cmd, args, "failed parsing", e
        self.db[g.name] = g

    @classmethod
    def cached_or_import(cls, fil):
        filpick = fil + ".pickle"
        try:
            c = pickle.load(open(filpick))
        except IOError:
            c = cls()
            c.import_zemax(fil)
            pickle.dump(c, open(filpick, "wb"), protocol=2)
        return c

# http://refractiveindex.info
vacuum = FictionalMaterial(name="vacuum", nd=1., vd=inf)

air = Material(name="air", sellmeier=[
    [5792105E-8, 238.0185],
    [167917E-8, 57.362],
    ], vd=inf)
def air_refractive_index(wavelength):
        w2 = (wavelength/1e-6)**-2
        c0 = air.sellmeier[:,0]
        c1 = air.sellmeier[:,1]
        n  = 1.+(c0/(c1-w2)).sum(-1)
        return n
air.refractive_index = air_refractive_index


#catpath = "/home/rj/.wine/drive_c/Program Files/ZEMAX/Glasscat/"
catpath = "/home/rjordens/work/nist/glass/"
schott = GlassCatalog.cached_or_import(catpath+"SCHOTT.AGF")
#schott = GlassCatalog.cached_or_import(catpath+"schott-17-03-2009.agf")
ohara = GlassCatalog.cached_or_import(catpath+"ohara.agf")
misc = GlassCatalog.cached_or_import(catpath+"MISC.AGF")
infrared = GlassCatalog.cached_or_import(catpath+"INFRARED.AGF")

