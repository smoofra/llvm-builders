#!/usr/bin/env python3

# some code copied from https://github.com/google/netbsd-gce

import ftplib
import sys

import pexpect.exceptions

# this doesn't appear to be on pypi
# https://github.com/gson1703/anita
import anita

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
pkg_path = "http://cdn.NetBSD.org/pub/pkgsrc/packages/NetBSD/amd64/8.1/All/"
pkgs = "cmake swig3 curl python37 vim ccache ninja-build mozilla-rootcerts git"

workdir = "work-%s-%s" % (branch, arch)

a = anita.Anita(
    anita.URL(find_latest_release(branch, arch)),
    workdir=workdir,
    disk_size=disk_size,
    memory_size="4G",
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

boot_and_run([
    "grep -q sshd /etc/rc.conf || echo sshd=YES >>/etc/rc.conf",
    "grep -q dhcpcd /etc/rc.conf || echo dhcpcd=YES >>/etc/rc.conf",
    "grep -q ipv4only /etc/dhcpcd.conf || echo ipv4only >> /etc/dhcpcd.conf",
])

boot_and_run([
    f'env PKG_PATH="{pkg_path}" pkg_add {pkgs}',
    "mozilla-rootcerts install",
])

boot_and_run(['true'])

print("DONE.")
print()
print(f"""
To run the VM:

qemu-system-x86_64 -m 4096 -drive file={workdir}/wd0.img,format=raw,media=disk,snapshot=off -nographic -nic user,hostfwd=tcp::2222-:22

To convert the image:

qemu-img convert -f raw  {workdir}/wd0.img  -O qcow2 netbsd-8.1.qcow

""")

sys.exit(0)
