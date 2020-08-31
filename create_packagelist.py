#! /usr/bin/python3

import os
import re
import sys
import subprocess
import libarchive
import rpmfile
import tempfile

def read_csv_list(filename):
   result=[]
   with open(filename, 'r') as csv:
       for line in csv.readlines():
          result.append(line.strip().split(';'))
   return result

def inject_csv_list(csvlist, packages, tag):
  for pname, disturl, license in csvlist:
    if pname.startswith('gpg-pubkey'):
        continue
    match = re.match(r'.*/[^-/]*-([^/]*)$', disturl)
    if match is None:
        print('IGNORE', pname)
        continue
    disturl = match.group(1)
    match = re.match(r'(.*)-([^-]*)-([^-]*)$', pname)
    if match is None:
        continue
    if match.group(1) in packages: # do not overwrite
        continue
    packages[match.group(1)] = { 'version': match.group(2), 'source': disturl, 'license': license, 'needed': tag }


packages=dict()
inject_csv_list(read_csv_list(sys.argv[1]), packages, 'installed base')
inject_csv_list(read_csv_list(sys.argv[2]), packages, 'installed overlay')

def check_build_require(pname, packages, tag):
   output = subprocess.check_output(f"osc -A https://api.suse.de buildinfo -d SUSE:Carwos:1 {pname} standard x86_64", shell=True, text=True)
   for line in output.split('\n'):
     match = re.search(r'<bdep name="([^"]*)".*version="([^"]*)"', line)
     if match:
        pname = match.group(1)
        version = match.group(2)
        if not pname in packages:
           packages[pname] = {'version': version, 'needed': tag, 'source': None, 'license': None}

check_build_require('base-image', packages, 'build base-image')
check_build_require('sdk-image', packages, 'build sdk-image')

with tempfile.NamedTemporaryFile(mode='wb', suffix='.rpm') as temp:
   output=subprocess.check_output('osc -A https://api.suse.de api /build/SUSE:Carwos:1/standard/x86_64/_repository?view=cpioheaders', shell=True)
   with libarchive.memory_reader(output) as a:
    for entry in a:
        temp.seek(0)
        for block in entry.get_blocks():
           temp.write(block)
        temp.flush()
        with rpmfile.open(temp.name) as rpm:
           pname = rpm.headers.get('name').decode('utf-8')
           packages.setdefault(pname, { 'needed': 'unknown' })
           source = rpm.headers['sourcerpm'].decode('utf-8')
           match = re.match(r'(.*)-([^-]*)-([^-]*)\.src\.rpm$', source)
           if match:
              source = match.group(1)
           packages[pname]['source'] = source
           packages[pname]['version'] = rpm.headers.get('version').decode('utf-8')
           packages[pname]['license'] = rpm.headers.get('copyright').decode('utf-8')


print("Binary;Source;Version;Needed;License")
for package in sorted(packages):
   info = packages[package]
   print(f"{package};{info['source']};{info['version']};{info['needed']};{info['license']}")

