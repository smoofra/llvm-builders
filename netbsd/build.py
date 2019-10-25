#!/usr/bin/env python3

# some code copied from https://github.com/google/netbsd-gce

import subprocess
import ftplib
import os
import sys
import argparse

import pexpect.exceptions

# this doesn't appear to be on pypi
# https://github.com/gson1703/anita
import anita


parser = argparse.ArgumentParser()
parser.add_argument("--key")
parser.add_argument("--google-compute-engine", "--gce", action='store_true')
args = parser.parse_args()


def find_latest_release(branch, arch):
  """Find the latest NetBSD-current release for the given arch.

  Returns:
    the full path to the release.
  """
  conn = ftplib.FTP('nyftp.netbsd.org')
  conn.login()
  conn.cwd('/pub/NetBSD-daily/%s' % branch)
  releases = conn.nlst()
  releases.sort(reverse=True)
  for r in releases:
    archs = conn.nlst(r)
    if not archs:
      next
    has_arch = [a for a in archs if a.endswith(arch)]
    if has_arch:
      return "https://nycdn.netbsd.org/pub/NetBSD-daily/%s/%s/" % (branch, has_arch[0])

arch = 'amd64'
branch = 'netbsd-8'
disk_size = '24G'
version = '8.1'
pkg_path = f"http://cdn.NetBSD.org/pub/pkgsrc/packages/NetBSD/{arch}/{version}/All/"
pkgs = "cmake swig3 curl python37 vim ccache ninja-build mozilla-rootcerts git py37-pip"
workdir = f"work-{branch}-{arch}"

if args.google_compute_engine:
  out = subprocess.run(['tar', '--version'], stdout=subprocess.PIPE).stdout
  if b'GNU tar' in out:
    tar = 'tar'
  else:
    tar = 'gtar'

a = anita.Anita(
    anita.URL(find_latest_release(branch, arch)),
    workdir=workdir,
    disk_size=disk_size,
    memory_size="16G",
    persist=True)


def boot_and_run(commands):
  child = a.boot()
  anita.login(child)
  for cmd in commands:
    rc = anita.shell_cmd(child, cmd, 1200)
    if rc != 0:
      raise Exception("command failed")
  anita.shell_cmd(child, "sync; shutdown -hp now", 1200)
  try:
    a.halt()
  except pexpect.exceptions.EOF:
    pass

commands = [
    "grep -q dhcpcd /etc/rc.conf || echo dhcpcd=YES >>/etc/rc.conf",
    "grep -q ipv4only /etc/dhcpcd.conf || echo ipv4only >> /etc/dhcpcd.conf",
]

if args.key:
  with open(args.key, 'r') as f:
    key = f.read().strip()

  commands += [
    "grep -q sshd /etc/rc.conf || echo sshd=YES >>/etc/rc.conf",
    'echo "PermitRootLogin prohibit-password" >> /etc/ssh/sshd_config',
    'mkdir -p .ssh',
    'chmod 0700 .ssh',
    f"echo '{key}' >>.ssh/authorized_keys",
    'chmod 0600 .ssh/authorized_keys',
  ]

boot_and_run(commands)

boot_and_run([
    f'env PKG_PATH="{pkg_path}" pkg_add {pkgs}',
    "mozilla-rootcerts install",
])

gce_commands = [
    """cat > /etc/ifconfig.vioif0 << EOF
!dhcpcd vioif0
mtu 1460
EOF""",
    """ed /etc/fstab << EOF
H
%s/wd0/sd0/
wq
EOF""",
]

if args.google_compute_engine:
  boot_and_run(gce_commands)

  print("finished with qemu, tarring up for google compute engine ")

  tarball =  f'netbsd-{version}-gce.tar.gz'
  subprocess.run([tar, '-Szcf', tarball, '--transform', f's,{workdir}/wd0.img,disk.raw,', f'{workdir}/wd0.img'],
    check=True)
  print("tarball created:", tarball)

print("DONE.")

if not args.google_compute_engine:
  print()
  print(f"""
  To run the VM:
  qemu-system-x86_64 -m 16384 -drive file={workdir}/wd0.img,format=raw,media=disk,snapshot=off -nographic -nic user,hostfwd=tcp::2222-:22

  To convert the image:
  qemu-img convert -f raw  {workdir}/wd0.img  -O qcow2 netbsd-8.1.qcow

  """)

sys.exit(0)
