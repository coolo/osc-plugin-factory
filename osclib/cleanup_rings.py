from xml.etree import cElementTree as ET

from osc.core import makeurl
from osc.core import http_GET
from osclib.core import fileinfo_ext_all
from osclib.core import builddepinfo

try:
    from urllib.error import HTTPError
except ImportError:
    #python 2.x
    from urllib2 import HTTPError

class CleanupRings(object):
    def __init__(self, api):
        self.bin2src = {}
        self.pkgdeps = {}
        self.sources = set()
        self.api = api
        self.links = {}
        self.commands = []
        self.whitelist = ['obs-service-tar_scm', 'obs-service-recompress']

    def perform(self):
        self.check_depinfo_ring('home:coolo:carwos', None)
        print('\n'.join(self.commands))

    def find_inner_ring_links(self, prj):
        query = {
            'view': 'info',
            'nofilename': '1'
        }
        url = makeurl(self.api.apiurl, ['source', prj], query=query)
        f = http_GET(url)
        root = ET.parse(f).getroot()
        for si in root.findall('sourceinfo'):
            links = si.findall('linked')
            pkg = si.get('package')
            if links is None or len(links) == 0:
                print('# {} not a link'.format(pkg))
            else:
                linked = links[0]
                dprj = linked.get('project')
                dpkg = linked.get('package')
                if dprj != self.api.project:
                    if not dprj.startswith(self.api.crings):
                        print("#{} not linking to base {} but {}".format(pkg, self.api.project, dprj))
                    self.links[dpkg] = pkg
                # multi spec package must link to ring
                elif len(links) > 1:
                    mainpkg = links[1].get('package')
                    mainprj = links[1].get('project')
                    if mainprj != self.api.project:
                        print('# FIXME: {} links to {}'.format(pkg, mainprj))
                    else:
                        destring = None
                        if mainpkg in self.api.ring_packages:
                            destring = self.api.ring_packages[mainpkg]
                        if not destring:
                            print('# {} links to {} but is not in a ring'.format(pkg, mainpkg))
                            print("osc linkpac {}/{} {}/{}".format(mainprj, mainpkg, prj, mainpkg))
                        else:
                            if pkg != 'glibc.i686': # FIXME: ugly exception
                                print("osc linkpac -f {}/{} {}/{}".format(destring, mainpkg, prj, pkg))
                                self.links[mainpkg] = pkg

    def fill_pkgdeps(self, prj, repo, arch):
        root = builddepinfo(self.api.apiurl, prj, repo, arch)

        for package in root.findall('package'):
            # use main package name for multibuild. We can't just ignore
            # multibuild as eg installation-images has no results for the main
            # package itself
            # https://github.com/openSUSE/open-build-service/issues/4198
            name = package.attrib['name'].split(':')[0]
            if name.startswith('preinstall'):
                continue

            self.sources.add(name)

            for subpkg in package.findall('subpkg'):
                subpkg = subpkg.text
                if subpkg in self.bin2src:
                    if self.bin2src[subpkg] == name:
                        # different archs
                        continue
                    print('# Binary {} is defined twice: {}/{}'.format(subpkg, prj, name))
                self.bin2src[subpkg] = name

        for package in root.findall('package'):
            name = package.attrib['name'].split(':')[0]
            for pkg in package.findall('pkgdep'):
                if pkg.text not in self.bin2src:
                    print('Package {} not found in place'.format(pkg.text))
                    continue
                b = self.bin2src[pkg.text]
                self.pkgdeps[b] = name

    def repo_state_acceptable(self, project):
        url = makeurl(self.api.apiurl, ['build', project, '_result'])
        root = ET.parse(http_GET(url)).getroot()
        for repo in root.findall('result'):
            repostate = repo.get('state', 'missing')
            if repostate not in ['unpublished', 'published'] or repo.get('dirty', 'false') == 'true':
                print('Repo {}/{} is in state {}'.format(repo.get('project'), repo.get('repository'), repostate))
                return False
            for package in repo.findall('status'):
                code = package.get('code')
                if code not in ['succeeded', 'excluded', 'disabled']:
                    print('Package {}/{}/{} is {}'.format(repo.get('project'), repo.get('repository'), package.get('package'), code))
                    return False
        return True

    def check_image_bdeps(self, project, arch):
        for dvd in ['openSUSE-MicroOS:RawPC']:
            try:
                url = makeurl(self.api.apiurl, ['build', project, 'images', arch, dvd, '_buildinfo'])
                root = ET.parse(http_GET(url)).getroot()
            except HTTPError as e:
                if e.code == 404:
                    continue
                raise
            for bdep in root.findall('bdep'):
                if 'name' not in bdep.attrib:
                    continue
                b = bdep.attrib['name']
                if b not in self.bin2src:
                    print("{} not found in bin2src".format(b))
                    continue
                b2 = self.bin2src[b]
                self.pkgdeps[b2] = 'MYdvd:{}'.format(b)
            break

    def check_buildconfig(self, project):
        url = makeurl(self.api.apiurl, ['build', project, 'standard', '_buildconfig'])
        for line in http_GET(url).read().splitlines():
            line = line.decode('utf-8')
            if line.startswith('Preinstall:') or line.startswith('Support:'):
                for prein in line.split(':')[1].split():
                    if prein not in self.bin2src:
                        continue
                    b = self.bin2src[prein]
                    self.pkgdeps[b] = 'MYinstall'

    def check_requiredby(self, project, package):
        # Prioritize x86_64 bit.
        arch='x86_64'
        for fileinfo in fileinfo_ext_all(self.api.apiurl, project, 'standard', arch, package):
            for requiredby in fileinfo.findall('provides_ext/requiredby[@name]'):
                b = self.bin2src[requiredby.get('name')]
                if b == package:
                    # A subpackage depending on self.
                    continue
                print('# {} is required by {} {}'.format(package, b, requiredby.get('name')))
                self.pkgdeps[package] = b
                return True
        return False

    def check_depinfo_ring(self, prj, nextprj):
        self.fill_pkgdeps(prj, 'standard', 'x86_64')
        self.check_image_bdeps(prj, 'x86_64')

        for source in sorted(self.sources):
            print('# - {} - {} {}'.format(source, self.pkgdeps.get(source, 'no pkgdeps'), self.links.get(source, 'no link')))
            if (source not in self.pkgdeps and
                source not in self.links and
                source not in self.whitelist):
                # Expensive check so left until last.
                if self.check_requiredby(prj, source):
                    print('# Checked required {}'.format(source))
                    continue

                print('# - {}'.format(source))
                self.commands.append(' osc rdelete -m cleanup {} {}'.format(prj, source))
                if nextprj:
                    self.commands.append('osc linkpac {} {} {}'.format(self.api.project, source, nextprj))

        # Only loop through sources once from their origin ring to ensure single
        # step moving to allow check_requiredby() to see result in each ring.
        self.sources = set()
