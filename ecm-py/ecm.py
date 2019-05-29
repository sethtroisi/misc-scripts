#!/usr/bin/env python3

# ecm.py - A Python driver for GMP-ECM
#
# Copyright (c) 2011-2016 David Cleaver
# Copyright (c) 2019 Seth Troisi
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with
# or without modification, are permitted provided that the
# following conditions are met:
#
#    Redistributions of source code must retain the above
#    copyright notice, this list of conditions and the
#    following disclaimer.
#
#    Redistributions in binary form must reproduce the
#    above copyright notice, this list of conditions and
#    the following disclaimer in the documentation and/or
#    other materials provided with the distribution.
#
#    The names of its contributors may not be used to
#    endorse or promote products derived from this
#    software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
# THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# This code is a conversion of the script factmsieve.py
# which is Copyright 2010, Brian Gladman. His contribution
# is acknowledged, as are those of all who contributed to
# the original Perl script.


import os, random, re, socket, signal, smtplib
import time, subprocess, gzip, glob, math, datetime, sys
import atexit

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x



# ###############################################################
# User Defined Variables, set before using...
# ###############################################################
# Set binary directory paths
# NOTE: A path that starts with the period character is called a relative path.
#       Which means we will try to find the ecm binary starting in the ecm.py current path and add in the rest of the path given by ECM_PATH
#       For example, if the ecm.py script is located in '/home/user/ecm_py/ecm.py':
#       If ECM_PATH = './', then we will look for the ecm binary in '/home/user/ecm_py/<ecm-binary>'
#       If ECM_PATH = './usr/local/bin/', then we will look for the ecm binary in '/home/user/ecm_py/usr/local/bin/<ecm-binary>'
#     If the ECM_PATH does not start with the period character, that is called a fixed path.
#       With that, we will look in the given location for the ecm binary.  ie:
#       If ECM_PATH = '/usr/local/bin/', then we will look for the ecm binary in '/usr/local/bin/<ecm-binary>'
#       If ECM_PATH = 'd:/math/ecm_py/', then we will look for the ecm binary in 'd:/math/ecm_py/<ecm-binary>'
ECM_PATH = './'

# Default number of ecm threads to launch
# Can be overidden on the command line with -threads N
ECM_THREADS = 2


# If we encounter a composite factor and/or cofactor, should we continue
# doing the rest of the requested curves, or stop when we find one factor
# 0 to keep factoring composites, 1 to stop work after finding a factor
find_one_factor_and_stop = 1


# This controls how often (in seconds) python reads in job files from the hard drive
# Can be overidden on the command line with -pollfiles N
# --- Recommended settings ---
# For quick jobs (less than a couple of hours): between 3 and 15 seconds
# For small jobs (less than a day): between 15 and 45 seconds
# For medium jobs (less than a week): between 45 and 120 seconds
# For large jobs (less than a month): between 120 and 360 seconds
poll_file_delay = 15


# This controls how often we print runtime info to our log file
# The following two lines are examples of what is printed out at each interval:
# Mon 2014/12/01 00:55:44 UTC     32 of    100 | Stg1 11.04s | Stg2 6.090s |   0d 00:05:00 |   0d 00:09:42
# Mon 2014/12/01 01:00:44 UTC     68 of    100 | Stg1 11.03s | Stg2 6.075s |   0d 00:10:00 |   0d 00:04:33
# 300 = 5 minutes
# 3600 = 1 hour
# 86400 = 1 day
# 604800 = 1 week
log_interval_seconds = 86400


# This controls how to print runtime and eta information...
# The eta is the estimated time until completion
# It is calculated based on the average stage1+stage2 time, so
#   the job may finish earlier or later based on system usage
# FYI, eta is recomputed every 60 seconds...
#     runtime    eta
# 0 = seconds,   none
# 1 = seconds, seconds
# 2 = seconds,  mixed
# 3 = seconds,   dhms
# 4 =  mixed ,   none
# 5 =  mixed , seconds
# 6 =  mixed ,  mixed
# 7 =  mixed ,   dhms
# 8 =   dhms ,   none
# 9 =   dhms , seconds
#10 =   dhms ,  mixed
#11 =   dhms ,   dhms
time_info = 11
# Examples of how you can mix and match Runtime and ETA outputs:
#____________________________________________________________________________
# Curves Complete |   Average seconds/curve   |    Runtime    |      ETA
#-----------------|---------------------------|---------------|--------------
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |      1945628s |  41d 08:37:51
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |       22.518d |  41d 08:37:51
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |      3573471s
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |       41.359d
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |  41d 08:37:51


# #####################################
# Options for sending email reports...
email_results = 0
# How often, in minutes, to send an email progress report...
# Set to 999999 if you do not want progress reports, but only a final report.
email_interval_minutes = 1440 # 360 minutes = 6 hours, 1440 minutes = 1 day
# Account details to log on to email server that will send this email
em_srv  = 'smtp.gmail.com:587'
em_usr  = ''
em_pwd  = ''
# Who this email is addressed to, and cc'ed to
em_to   = [''] # needs to be a list of names
em_cc   = [''] # needs to be a list of names

# Set global flags to control operation

CHECK_BINARIES = True
VERBOSE = 1 #set to 0, 1, 2, or 3 for quiet, normal, verbose, or very verbose
AUTORESUME = True

# ###############################################################
# End of User Defined Variables...
# ###############################################################

# Make sure our ECM_PATH variable ends with a forward slash
if ECM_PATH[-1] != '/': ECM_PATH = ECM_PATH + '/'

# gmp-ecm executable file name
ECM = 'ecm'

if sys.platform.startswith('win'):
  EXE_SUFFIX = '.exe'
else:
  EXE_SUFFIX = ''
  NICE_PATH = ''

# global variables

v_quiet = 0
v_normal = 1
v_verbose = 2
vv_verbose = 3
ecm_args = '' # original arguments passed in to ecm
ecm_args1 = '' # modified arguments for ecm to spread work out
ecm_args2 = '' # modified arguments for ecm to spread work out
intNumThreads = ECM_THREADS # default number of instances of gmp-ecm to run...
ecm_job = '' # name of the job file we are currently working on...
ecm_c = 1 # default number of curves to run...
ecm_n = 0 # the current number we are factoring (we only factor one at a time)
ecm_c_completed = 0 # total number of curves completed on this job
tt_stg1 = 0 # total time spent in stage 1
tt_stg2 = 0 # total time spent in stage 2
prev_ecm_c_completed = 0 # amount curves previously completed
prev_tt_stg1 = 0 # total time previously spent in stage 1
prev_tt_stg2 = 0 # total time previously spent in stage 2
ecm_s1_completed = 0
prev_ecm_s1_completed = 0
intResume = 0
output_file = ''
save_to_file = False
number_list = []
resume_file = ''
job_start = time.time()
factor_found = False
factor_value = ''
factor_data = ''
remaining_composites = ''
job_complete = False
ecm_c_has_changed = False
need_using_line = True
using_line = ''
need_version_info = True
version_info = ''
time_str = ''
# create a file sizes dictionary to store how large each of our in-progress output files are
# this will help us to reduce the number of times we read in the whole file for processing
file_sizes = {}
first_getsizes = True
actual_num_threads = 1
ecm_c_completed_per_file = {}
ecm_s1_completed_per_file = {}
tt_stg1_per_file = {}
tt_stg2_per_file = {}
e_total = -1.0
next_email_interval = 60*email_interval_minutes
LOGNAME = 'ecm_py.log'
next_log_interval = log_interval_seconds # log progress info once per day...
inp_file = '' # used with the -inp option...
ecm_resume_finished_file = '' # will be set to a filename when using the -resume option...
ecm_resume_file = '' # will be set to a filename when using the -resume option...
ecm_resume_job = False # will be set to True when using the -resume option
threadList = [] # used to keep track of -resume work...
files_c = [] # total amount of curves completed in each of our files...
files_t2 = [] # total amount of Step 2 time in each of our files...
files_sizes = [] # size each of our files, used to detect when there is a change...
num_resume_lines = 0
tot_c_completed = 0
prev_c_completed = 0
job_start = 0

# Utillity Routines

# return a number, abbreviated if the number is long and we're quiet
def abbreviate(s, length = 42):
    return s if (VERBOSE >= v_verbose or len(s) <= length) else s[:18] + "..." + s[-18:]

# print an error message and exit

def die(x, rv = -1):
  output(x)
  sys.exit(rv)

def sig_exit(x, y):
  print('\n')
  die('Signal caught. Terminating...')

# obtain a float or an int from a string

def get_nbr(s):
  m = re.match('[+-]?([0-9]*\.)?[0-9]+([eE][+-]?[0-9]+)?', s)
  return float(s) if m else int(s)

def is_nbr(s):
  try:
    float(s)
    return True
  except:
    return False

def is_nbr_range(s):
  try:
    ss = s.split('-')
    float(ss[0])
    float(ss[1])
    return True
  except:
    return False

# check for command to gmp-ecm or ecm.py that require numeric arguments...
def is_ecm_cmd(s):
  if s in ['-x0', '-y0', '-param', '-sigma', '-A', '-torsion', '-k',
           '-power', '-dickson', '-c', '-base2', '-maxmem', '-stage1time',
           '-i', '-I', '-ve', '-B2scale', '-go', '-threads', '-pollfiles']:
    return True
  else:
    return False

# delete a file (unlink equivalent)

def delete_file(fn):
  if os.path.exists(fn):
    try:
      os.unlink(fn)
    except WindowsError:
      pass

# GREP on a list of text lines

def grep_l(pat, lines):
  r = []
  for l in lines:
    if re.search(pat, l):
      r += [re.sub('\r|\n', ' ', l)]
  return r

# GREP on a named file

def grep_f(pat, file_path):
  if not os.path.exists(file_path):
    raise IOError
  else:
    r = []
    with open(file_path, 'r') as in_file:
      for l in in_file:
        if re.search(pat, l):
          r += [re.sub('\r|\n', ' ', l)]
    return r

# concatenate file 'app' to file 'to'

def cat_f(app, to):
  if os.path.exists(app):
    if VERBOSE >= v_verbose:
      print('-> appending {0:s} to {1:s}'.format(app, to))
    with open(to, 'ab') as out_file:
      with open(app, 'rb') as in_file:
        buf = in_file.read(8192)
        while buf:
          out_file.write(buf)
          buf = in_file.read(8192)

# compress file 'fr' to file 'to'

def gzip_f(fr, to):
  if not os.path.exists(fr):
    raise IOError
  else:
    if VERBOSE >= v_verbose:
      print('compressing {0:s} to {1:s}'.format(fr, to))
    with open(fr, 'rb') as in_file:
      out_file = gzip.open(to, 'ab')
      out_file.writelines(in_file)
      out_file.close()

# remove end of line characters from a line

def chomp(s):
  p  = len(s)
  while p and (s[p - 1] == '\r' or s[p - 1] == '\n'):
    p -= 1
  return s[0:p]

# remove comment lines

def chomp_comment(s):
  return re.sub('#.*', '', s)

# remove all white space in a line

def remove_ws(s):
  return re.sub('\s', '', s)

# normalize paths so that they all have '/', and no '\' or '\\'...
def npath(str):
  new_str = str.replace('\\', '/')
  while '//' in new_str: new_str = new_str.replace('//', '/')
  return new_str

# produce date/time string for log

# Thu May 29 09:05:25 2014
def date_time_string() :
  dt = datetime.datetime.today()
  return dt.strftime('%a %b %d %H:%M:%S %Y ')

# Thu 2014/05/29 09:05:25 UTC
def time_utc_string():
  return time.strftime("%a %Y/%m/%d %H:%M:%S UTC ", time.gmtime())


# write string to log(s):

def write_string_to_log(s):
  with open(LOGNAME, 'a') as out_f:
    list = s.split('\n')
    for line in list:
      print(time_utc_string() + line, file = out_f)

def output(s, console = True, log = True):
  if console and VERBOSE >= v_normal:
    print(s)
  if log:
    write_string_to_log(s)

# find processor speed

def proc_speed():
  if os.sys.platform.startswith('win'):
    if sys.version_info[0] == 2:
      from _winreg import OpenKey, QueryValueEx, HKEY_LOCAL_MACHINE
    else:
      from winreg import OpenKey, QueryValueEx, HKEY_LOCAL_MACHINE
    h = OpenKey(HKEY_LOCAL_MACHINE,
                'HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0')
    mhz = float(QueryValueEx(h, '~MHz')[0])
  else:
    tmp = grep_f('cpu MHz\s+:\s+', '/proc/cpuinfo')
    m = re.search('\s*cpu MHz\s+:\s+([0-9]+)', tmp[0])
    mhz = float(m.group(1)) if m else 0.0
  return 1e-3 * mhz

# check that an executable file exists

def check_binary(exe):
  if CHECK_BINARIES:
    if not os.path.exists(ECM_PATH + exe + EXE_SUFFIX):
      print('-> Could not find the program: {0:s}'.format(ECM_PATH + exe + EXE_SUFFIX))
      print('-> Did you set the path properly in this script?')
      print('-> It is currently set to:')
      print('-> ECM_PATH = {0:s}'.format(ECM_PATH))
      sys.exit(-1)
    if not os.path.isfile(ECM_PATH + exe + EXE_SUFFIX):
      print('-> The following is not a file: {0:s}'.format(ECM_PATH + exe + EXE_SUFFIX))
      print('-> Did you set the path properly in this script?')
      print('-> It is currently set to:')
      print('-> ECM_PATH = {0:s}'.format(ECM_PATH))
      sys.exit(-1)

# run an executable file

def run_exe(exe, args, inp = '', in_file = None, out_file = None,
            log = True, display = VERBOSE, wait = True, resume = 0):
  al = {} if VERBOSE else {'creationflags' : 0x08000000 }
  if sys.platform.startswith('win'):
#   priority_high = 0x00000080
#   priority_normal = 0x00000020
#   priority_idle = 0x00000040
    al['creationflags'] = al.get('creationflags', 0) | 0x00000040
  else:
    if NICE_PATH:
      al['preexec_fn'] = NICE_PATH

  if in_file and os.path.exists(in_file):
    al['stdin'] = open(in_file, 'r')

  if out_file:
    if out_file == subprocess.PIPE:
      md = ' > PIPE'
      al['stdout'] = subprocess.PIPE
    elif os.path.exists(out_file):
      md = ' >> ' + out_file
      al['stdout'] = open(out_file, 'a')
    else:
      md = ' > ' + out_file
      al['stdout'] = open(out_file, 'w')

  cs = '{0:s}{1:s}'.format(exe, args)
  if in_file:
    cs += ' < {0:s}'.format(in_file)
  if out_file:
    cs += md

  if resume == 0:
    output('-> ' + cs, console = display >= v_normal, log = log)
  else:
    output('-> ' + cs + '  (' + str(resume) + ' resume line{0:s})'.format('s' if resume > 1 else ''), console = display >= v_normal, log = log)

  ex = (ECM_PATH + exe + EXE_SUFFIX)
  al['executable'] = ex

  if VERBOSE >= vv_verbose:
    print('-> ecm args: {0:s}'.format(args))
    print('-> ecm   al: {0:s}'.format(al))

  p = subprocess.Popen(args.split(' '), **al)
  #p = subprocess.Popen([ex] + args.split(' '), **al)
  #p = subprocess.Popen(cs.split(' '), **al)

  if not wait:
    return p

  if out_file == subprocess.PIPE:
    if sys.version_info[0] == 3:
      res = p.communicate(inp.encode())[0].decode()
    else:
      res = p.communicate(inp)[0]
    if res:
      res = re.split('(?:\r|\n)*', res)
    ret = p.poll()
    return (ret, res)
  else:
    return p.wait()

# generate a list of primes

def prime_list(n):
  sieve = [False, False] + [True] * (n - 1)
  for i in range(2, int(n ** 0.5) + 1):
    if sieve[i]:
      m = n // i - i
      sieve[i * i : n + 1 : i] = [False] * (m + 1)
  return [i for i in range(n + 1) if sieve[i]]

# greatest common divisor

def gcd(x, y):
  if x == 0:
    return y
  elif y == 0:
    return x
  else:
    return gcd(y % x, x)

# Miller Rabin 'probable prime' test
#
# returns 'False' if 'n' is definitely composite
# returns 'True' if 'n' is prime or probably prime
#
# 'r' is the number of trials performed

def miller_rabin(n, r = 10):
  t = n - 1
  s = 0
  while not t & 1:
    t >>= 1
    s += 1
  for i in range(r):
    a = random.randint(2, n - 1)
    x = pow(a, t, n)
    if x != 1 and x != n - 1:
      for j in range(s - 1):
        x = (x * x) % n
        if x == 1:
          return False
        if x == n - 1:
          break
      else:
        return False
  return True

# determine if n is probably prime - return
#    0 if n is 0, 1 or composite
#    1 if n is probably prime
#    2 if n is definitely prime

def probable_prime_p(nn, r):
  n = abs(nn)
  if n <= 2:
    return 2 if n == 2 else 0

  # trial division
  for p in prime_list(1000):
    if not n % p:
      return 2 if n == p else 0
    if p * p > n:
      return 2

  # Fermat test
  if pow(random.randint(2, n - 1), n - 1, n) != 1:
    return 0

  # Miller-Rabin test
  return 1 if miller_rabin(n, r) else 0

# count the number of lines in a file

def linecount(file_path):
  count = 0
  if not os.path.exists(file_path):
    die('can\'t open {0:s}'.format(file_path))
  with open(file_path, 'r') as in_file:
    for l in in_file:
      count += 1
  return count

# Read the log file to see if we've found all the prime
# divisors of N yet.

def get_primes(fact_p):

  with open(LOGNAME, 'r') as in_f:
    for l in in_f:
      l = chomp(l)
      m1 = re.search('r\d+=(\d+)\s+', l)
      if m1:
        val = int(m1.group(1))
        if len(val) > 1 and  len(val) < len(fact_p['ndivfree']):
          # Is this a prime divisor or composite?
          m2 = re.search('\(pp(\d+)\)', l)
          if m2:
            # If this is a prime we don't already have, add it.
            found = False
            for p in fact_p['primes']:
              if val == p:
                found = True
            if not found:
              fact_p['primes'].append(val)
          else:
            fact_p['comps'].append(val)

  # Now, try to figure out if we have all the prime factors:
  x = itertools.reduce(lambda x,y : x * y, fact_p['primes'], 1)
  if x == fact_p['ndivfree'] or probab_prime_p(fact_p['ndivfree'] // x, 10):
    if x != fact_p['ndivfree']:
      fact_p['primes'].append(fact_p['ndivfree'] // x)
    for p in fact_p['primes']:
      cs = '-> p: {0:s} (pp{1:d})'.format(val, len(val))
      output(cs)
    return True
  # Here, we could try to recover other factors by division,
  # but until we have a primality test available, this would
  # be pointless since we couldn't really know if we're done.
  return False

def sendemail(from_addr, to_addr_list, cc_addr_list,
              subject, message,
              login, password,
              smtpserver='smtp.gmail.com:587', one_line = False):
  header  = 'From: {0:s}\n'.format(from_addr)
  header += 'To: {0:s}\n'.format(','.join(to_addr_list))
  header += 'Cc: {0:s}\n'.format(','.join(cc_addr_list))
  header += 'Subject: {0:s}\n\n'.format(subject)
  message = header + message

  try:
    if VERBOSE >= v_normal:
      if one_line:
        print('-> Logging in to email server.'.ljust(78), end='\r')
      else:
        print('\n-> Logging in to email server.')
    write_string_to_log('-> Logging in to email server.')
    server = smtplib.SMTP(smtpserver)
    server.ehlo()
    server.starttls()
    server.login(login,password)
    if VERBOSE >= v_normal:
      if one_line:
        print('-> Sending email message.'.ljust(78), end='\r')
      else:
        print('-> Sending email message.')
    write_string_to_log('-> Sending email message with subject line: ' + subject)
    problems = server.sendmail(from_addr, to_addr_list, message)
    if VERBOSE >= v_normal:
      if one_line:
        print('-> Email message successfully sent.'.ljust(78), end='\r')
      else:
        print('-> Email message successfully sent.')
    write_string_to_log('-> Email message successfully sent.')
    server.quit()
  except:
    e = sys.exc_info()[0]
    print('\n *** ERROR: problem sending email results.  Error message was: ')
    print(str(e) + '\n')
    write_string_to_log(' *** ERROR: problem sending email results.  Error message was: ')
    write_string_to_log(str(e))

procs = []  # list of thread popen instances

def terminate_ecm_threads():
  global procs
  if procs:
    for p in procs:
      if p.poll() == None:
        try:
          p.terminate()
        except:
          pass
          #print('-> *** WARNING *** WARNING *** WARNING *** Termination exception! ***')
        time.sleep(0.1)
    del procs[:]
    #print('-> ecm terminated')

def start_ecm_threads():
  global procs, ecm_c, intNumThreads, ecm_job, actual_num_threads

  #make sure there are no other ecm processes running or stored in procs...
  terminate_ecm_threads()

  ecm_job_prefix = ecm_job.split('.')[0]

  old_handler = signal.signal(signal.SIGINT, terminate_ecm_threads)

  if ecm_c == 0:
    num = intNumThreads
  else:
    num = ecm_c if (ecm_c < intNumThreads) else intNumThreads

  actual_num_threads = num
  if VERBOSE >= v_normal:
    print('-> Starting {0:d} instance{1:s} of GMP-ECM...'
        .format(num, '' if (num == 1) else 's'))
  write_string_to_log('-> Starting {0:d} instance{1:s} of GMP-ECM...'.format(num, '' if (num == 1) else 's'))

  i = 0
  if intNumThreads == 1:
    file_name = ecm_job_prefix + '_t' + str(i).zfill(2) + '.txt'
    procs.append(run_exe(ECM, ecm_args1, in_file = ecm_job, out_file = file_name, wait = False))
  else:
    if ecm_c == 0:
      while i < intNumThreads:
        file_name = ecm_job_prefix + '_t' + str(i).zfill(2) + '.txt'
        procs.append(run_exe(ECM, ecm_args1, in_file = ecm_job, out_file = file_name, wait = False))
        i += 1
    elif ecm_c < intNumThreads:
      remainder = ecm_c%intNumThreads
      while i < remainder:
        file_name = ecm_job_prefix + '_t' + str(i).zfill(2) + '.txt'
        procs.append(run_exe(ECM, ecm_args2, in_file = ecm_job, out_file = file_name, wait = False))
        i += 1
    else:
      remainder = ecm_c%intNumThreads
      while i < remainder:
        file_name = ecm_job_prefix + '_t' + str(i).zfill(2) + '.txt'
        procs.append(run_exe(ECM, ecm_args2, in_file = ecm_job, out_file = file_name, wait = False))
        i += 1
      while i < intNumThreads:
        file_name = ecm_job_prefix + '_t' + str(i).zfill(2) + '.txt'
        procs.append(run_exe(ECM, ecm_args1, in_file = ecm_job, out_file = file_name, wait = False))
        i += 1

  print(' ')
  signal.signal(signal.SIGINT, old_handler)

def compare_ecm_args(test_args):
  global ecm_args

  # To see if two job command lines are the same
  # Make sure they are for the same job type
  # Make sure they are for the same number of curves
  # Make sure they are for the same B1
  data1 = ecm_args.split(' ')
  data2 = test_args.split(' ')
  type1 = 'ecm'
  type2 = 'ecm'
  count1 = 0
  count2 = 0

  i = 0
  while i < len(data1):
    if data1[i] == '-pm1':
      type1 = 'pm1'
    elif data1[i] == '-pp1':
      type1 = 'pp1'
    elif data1[i] == '-c':
      count1 = int(data1[i+1])
      i += 1
    i += 1

  i = 0
  while i < len(data2):
    if data2[i] == '-pm1':
      type2 = 'pm1'
    elif data2[i] == '-pp1':
      type2 = 'pp1'
    elif data2[i] == '-c':
      count2 = int(data2[i+1])
      i += 1
    i += 1

  if type1 != type2:
    return False
  if count1 != count2:
    return False
  if data1[-1] != data2[-1]:
    return False

  return True


# Perform some very basic input checking to make sure we don't
# evaluate python code that might do bad things to a users system.
def is_valid_input(instr):
  mystr = str(instr)

  if len(mystr) == 0:
    return False

  if mystr[0] == '#':
    return False

  for i in range(len(mystr)):
    if mystr[i] not in ['0','1','2','3','4','5','6','7','8','9','a','b','c','d','e','f','x',
                        ' ','+','-','*','/','^','%','!','#','.','(',')','{','}','[',']','"']:
      return False
  # If we get down here, all the characters must have been valid...
  return True


# (old) Function to count number of decimal digits of an input number
def num_digits_old(n):
  n = eval(n.replace('^', '**').replace('/', '//'))
  if n > 0:
    digits = int(math.log10(n))+1
  elif n == 0:
    digits = 1
  else:
    digits = int(math.log10(-n))+2 # +1 if you don't count the '-'
  return digits

# We will run a throwaway curve to have the ecm binary tell us how many digits are in the number...
# This is useful because the ecm binary already handles everything, including ^, !, and #
def num_digits(n):
  cmd = [ECM_PATH + ECM + EXE_SUFFIX, '10']
  p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
  if sys.version_info[0] == 3:
    out, res = p.communicate(n.encode())
    out = out.decode()
  else:
    out, err = p.communicate(n)
  # print('out = ' + out)
  # print('err = ' + err)
  for line in out.split('\n'):
    if 'digits' in line:
      j = line.rfind("(")
      k = line.rfind(" ")
      return int(line[j+1:k])
  # if we don't find the digits line, we'll just report -1...
  return -1



def read_resume_file(res_file):
  global prev_ecm_c_completed, prev_tt_stg1, prev_tt_stg2, prev_ecm_s1_completed, ecm_job, number_list
  global factor_found, factor_value, factor_data, ecm_c, job_complete, ecm_c_has_changed, ecm_args

  if not os.path.exists(res_file):
    output('-> *** Error: resume file {0:s} does not exist.'.format(res_file))
    return False

  ecm_job = res_file
  with open(ecm_job, 'r') as in_file:
    data = in_file.readline() # line 1 should be the number to factor
    data = data.strip()
    if is_valid_input(data):
      number_list.append(data)
    data = in_file.readline().strip().split('#')[1] # line 2 should be the command line
    data_args = data.strip()
    data = in_file.readline().split(' ') # line 3 should be the curves previously completed, tt_stg1, tt_stg2...
    prev_ecm_c_completed = int(data[1])
    prev_ecm_s1_completed = prev_ecm_c_completed
    prev_tt_stg1 = float(data[2])
    prev_tt_stg2 = float(data[3])

  job_file_prefix = ecm_job.split('.')[0]
  for f in glob.iglob(job_file_prefix + '_t*'):
    with open(f, 'r') as in_file:
      # the number of curves completed = the number of "Step 2" lines in the file
      for line in in_file:
        line = line.strip()
        if line.startswith('Step 1'):
          this_time = (float(line.split(' took ')[1][:-2])/1000.0)
          if this_time >= 0: # make sure we don't average in the rare negative time reported by ecm...
            prev_tt_stg1 += this_time
          prev_ecm_s1_completed += 1
        elif line.startswith('Step 2'):
          this_time = (float(line.split(' took ')[1][:-2])/1000.0)
          if this_time >= 0: # make sure we don't average in the rare negative time reported by ecm...
            prev_tt_stg2 += this_time
          prev_ecm_c_completed += 1
        elif line.startswith('Using'):
          factor_data = line # if a factor was found, this will contain its B1, B2, and sigma...
        elif line.find('Factor found') >= 0:
          factor_found = True
          factor_value = line
        elif factor_found and not line.startswith('Run'):
          factor_value += '\n' + line
      if factor_found:
        return True

    delete_file(f)

  parse_ecm_options(data_args.split(), set_args = True, quiet = True)

  output('-> *** Already completed {0:d} curves on this number...'.format(prev_ecm_c_completed))
  if ecm_c > 0:
    if prev_ecm_c_completed >= ecm_c:
      job_complete = True
      output('-> *** No more curves needed. Closing this job.')
    else:
      ecm_c -= prev_ecm_c_completed
      ecm_c_has_changed = True
      output('-> *** Will run {0:d} more curves.'.format(ecm_c))

  parse_ecm_options(data_args.split(), quiet = True)

  return True


# This controls how to print runtime and eta information...
# FYI, eta is recomputed every 60 seconds...
#     runtime    eta
# 0 = seconds,   none
# 1 = seconds, seconds
# 2 = seconds,  mixed
# 3 = seconds,   dhms
# 4 =  mixed ,   none
# 5 =  mixed , seconds
# 6 =  mixed ,  mixed
# 7 =  mixed ,   dhms
# 8 =   dhms ,   none
# 9 =   dhms , seconds
#10 =   dhms ,  mixed
#11 =   dhms ,   dhms

# seconds = just the total number of seconds of runtime or eta left.
# mixed = decimal form of days, or hours, or minutes, or seconds left.
# dhms = split form of days and hours and minutes and seconds left.
#
# Here are some examples of these types of outputs:
#
# Time to disply    seconds      mixed           dhms
#       45s             45s        45s   0d 00:00:45s
#      320s            320s      5.33m   0d 00:05:20s
#     3063s           3063s     51.05m   0d 00:51:03s
#     4511s           4511s     1.253h   0d 01:15:11s
#    67531s          67531s    18.758h   0d 18:45:31s
#    93421s          93421s     1.081d   1d 01:57:01s
#   193779s         193779s     2.242d   2d 05:49:39s
#  2039147s        2039147s    23.601d  23d 14:25:47s
#
# Examples of how you can mix and match Runtime and ETA outputs:
#____________________________________________________________________________
# Curves Complete |   Average seconds/curve   |    Runtime    |      ETA
#-----------------|---------------------------|---------------|--------------
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |      1945628s |  41d 08:37:51
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |       22.518d |  41d 08:37:51
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |      3573471s
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |       41.359d
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |  41d 08:37:51

def get_runtime(t_total):
  global time_info
  rt = ''

  if time_info < 4: # seconds format
    rt = '{0:.0f}s'.format(t_total).rjust(13)
  elif time_info < 8: # mixed format
    if t_total <= 60:
      rt = '{0:.0f}s'.format(t_total).rjust(13)
    elif t_total <= 3600:
      rt = '{0:.2f}m'.format(t_total/60.0).rjust(13)
    elif t_total <= 86400:
      rt = '{0:.3f}h'.format(t_total/3600.0).rjust(13)
    else:
      rt = '{0:.3f}d'.format(t_total/86400.0).rjust(13)
  else: # dhms format
    zd = '{0:.0f}'.format(math.floor(t_total/86400.0)).rjust(3) + 'd '
    zh = '{0:.0f}'.format(math.floor((t_total%86400)/3600.0)).zfill(2) + ':'
    zm = '{0:.0f}'.format(math.floor((t_total%3600)/60.0)).zfill(2) + ':'
    zs = '{0:.0f}'.format(math.floor(t_total%60.0)).zfill(2)
    rt = zd + zh + zm + zs

  return rt

def get_eta(c_complete, c_total, t_stg1, t_stg2, t_total):
  global time_info, e_total, intNumThreads
  eta = ''

  c_avg_time = t_stg1 + t_stg2

  if c_avg_time <= 0 or c_complete == 0: return '     n/a'

  # total runtime so far (for a single continuous run) should be close to (c_complete * c_avg_time) ~= t_total
  # total job runtime (for a single continuous run) should be close to (c_total * c_avg_time) ~= t_full
  # total runtime left should be close to (c_total-c_complete)*c_avg_time
  if t_total%60 < 1.0 or e_total < 0:
    e_total = ((c_total-c_complete)*c_avg_time)/intNumThreads + t_total

  e_left = e_total - t_total
  if e_left <= 0: e_left = 0.0;

# Examples of how you can mix and match Runtime and ETA outputs:
#____________________________________________________________________________
# Curves Complete |   Average seconds/curve   |    Runtime    |      ETA
#-----------------|---------------------------|---------------|--------------
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |      1945628s |  41d 08:37:51
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |       22.518d |  41d 08:37:51
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |      3573471s
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |       41.359d
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |  41d 08:37:51
  if time_info%4 == 0: return ''
  if time_info%4 == 1: # seconds format
    eta = '{0:.0f}s'.format(e_left).rjust(13)
  if time_info%4 == 2: # mixed format
    if e_left <= 60:
      eta = '{0:.0f}s'.format(e_left).rjust(13)
    elif e_left <= 3600:
      eta = '{0:.2f}m'.format(e_left/60.0).rjust(13)
    elif e_left <= 86400:
      eta = '{0:.3f}h'.format(e_left/3600.0).rjust(13)
    else:
      eta = '{0:.3f}d'.format(e_left/86400.0).rjust(13)
  else: # dhms format
    zd = '{0:.0f}'.format(math.floor(e_left/86400.0)).rjust(3) + 'd '
    zh = '{0:.0f}'.format(math.floor((e_left%86400)/3600.0)).zfill(2) + ':'
    zm = '{0:.0f}'.format(math.floor((e_left%3600)/60.0)).zfill(2) + ':'
    zs = '{0:.0f}'.format(math.floor(e_left%60.0)).zfill(2)
    eta = zd + zh + zm + zs

  return eta

def get_avg_str(c_completed, tt):
  if c_completed == 0:
    t_stg = 0
    str_stg = ' n/a s'
  else:
    t_stg = tt/c_completed
    if t_stg < 10:
      str_stg = '{0:.3f}s'.format(t_stg)
    elif t_stg < 100:
      str_stg = '{0:.2f}s'.format(t_stg)
    elif t_stg < 1000:
      str_stg = '{0:.1f}s'.format(t_stg)
    elif t_stg < 10000:
      str_stg = ' {0:.0f}s'.format(t_stg)
    else:
      str_stg = '{0:.0f}s'.format(t_stg)
  return str_stg, t_stg

def print_work_done():
  global ecm_c_completed, tt_stg1, tt_stg2, job_start, ecm_c, ecm_s1_completed, need_using_line
  global prev_ecm_s1_completed, prev_ecm_c_completed, prev_tt_stg1, prev_tt_stg2
  global ecm_s1_completed_per_file, ecm_c_completed_per_file, tt_stg1_per_file, tt_stg2_per_file
  global email_results, next_email_interval, email_interval_minutes, using_line
  global em_usr, em_to, em_cc, em_usr, em_pwd, em_srv, next_log_interval, log_interval_seconds

  t_total = time.time() - job_start

  ecm_s1_completed = prev_ecm_s1_completed
  ecm_c_completed = prev_ecm_c_completed
  tt_stg1 = prev_tt_stg1
  tt_stg2 = prev_tt_stg2

  for f in ecm_s1_completed_per_file:
    ecm_s1_completed += ecm_s1_completed_per_file[f]
  for f in ecm_c_completed_per_file:
    ecm_c_completed += ecm_c_completed_per_file[f]
  for f in tt_stg1_per_file:
    tt_stg1 += tt_stg1_per_file[f]
  for f in tt_stg2_per_file:
    tt_stg2 += tt_stg2_per_file[f]

  str_stg1, t_stg1 = get_avg_str(ecm_s1_completed, tt_stg1)
  str_stg2, t_stg2 = get_avg_str(ecm_c_completed, tt_stg2)

  rt = get_runtime(t_total)
  eta = get_eta(ecm_c_completed, ecm_c+prev_ecm_c_completed, t_stg1, t_stg2, t_total)

#____________________________________________________________________________
# Curves Complete |   Average seconds/curve   |    Runtime    |      ETA
#-----------------|---------------------------|---------------|--------------
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |  41d 08:37:51

  if not need_using_line:
    print('{0:6d} of {1:6d} | Stg1 {2:s} | Stg2 {3:s} | {4:s} | {5:s}\r'
               .format(ecm_c_completed, ecm_c+prev_ecm_c_completed, str_stg1, str_stg2, rt, eta), end='')
    sys.stdout.flush()

  if t_total > next_log_interval:
    next_log_interval = next_log_interval + log_interval_seconds # log this info once per interval...
    write_string_to_log('{0:6d} of {1:6d} | Stg1 {2:s} | Stg2 {3:s} | {4:s} | {5:s}'.format(ecm_c_completed, ecm_c+prev_ecm_c_completed, str_stg1, str_stg2, rt, eta))

  if email_results:
    if t_total > next_email_interval:
      next_email_interval = next_email_interval + 60*email_interval_minutes # convert email_interval_minutes into seconds
      my_msg = ''
      my_msg = my_msg + 'Computer: ' + socket.gethostname() + '\n'
      my_msg = my_msg + 'Report Time: ' + time.strftime('%Y/%m/%d %H:%M:%S UTC', time.gmtime()) + '\n\n'
      my_msg = my_msg + '{0:s}\n'.format(version_info)
      my_msg = my_msg + '{0:s}\n'.format(using_line)
      my_msg = my_msg + 'Input number is {0} ({1} digits)\n'.format(ecm_n, num_digits(ecm_n))
      my_msg = my_msg + '____________________________________________________________________________\n'
      my_msg = my_msg + ' Curves Complete |   Average seconds/curve   |    Runtime    |      ETA\n'
      my_msg = my_msg + '-----------------|---------------------------|---------------|--------------\n'
      my_msg = my_msg + '{0:6d} of {1:6d} | Stg1 {2:s} | Stg2 {3:s} | {4:s} | {5:s}\r'.format(ecm_c_completed, ecm_c+prev_ecm_c_completed, str_stg1, str_stg2, rt, eta)

      sendemail(from_addr    = em_usr,
                to_addr_list = em_to,
                cc_addr_list = em_cc,
                subject      = '[Ecm.py] Progress report...',
                message      = my_msg,
                login        = em_usr,
                password     = em_pwd,
                smtpserver   = em_srv,
                one_line     = True)

def gather_work_done(job_file):
  global need_using_line, factor_found, factor_value, factor_data, file_sizes, first_getsizes
  global ecm_s1_completed_per_file, ecm_c_completed_per_file, tt_stg1_per_file, tt_stg2_per_file
  global need_version_info, version_info, time_str, using_line, remaining_composites

  if not os.path.exists(job_file):
    return
  job_file_prefix = job_file.split('.')[0]
  for f in glob.iglob(job_file_prefix + '_t*'):
    if first_getsizes:
      file_sizes[f] = os.path.getsize(f)

    # using file sizes to reduce the number of times we read in the whole file for processing
    if file_sizes[f] != os.path.getsize(f) or first_getsizes:
      file_sizes[f] = os.path.getsize(f) #update the file size...
      ecm_c_completed_per_file[f] = 0
      ecm_s1_completed_per_file[f] = 0
      tt_stg1_per_file[f] = 0.0
      tt_stg2_per_file[f] = 0.0
      with open(f, 'r') as in_file:
        first_file_with_factor = False
        # the number of curves completed = the number of "Step 2" lines in the file (or +1 if a factor was found in Step 1)
        for line in in_file:
          line = line.strip()
          if need_version_info and line.startswith('GMP-ECM'):
            version_info = line
            need_version_info = False
            output('{0:s}'.format(version_info))
          elif line.startswith('Step 1'):
            this_time = (float(line.split(' took ')[1][:-2])/1000.0)
            if this_time >= 0: # make sure we don't average in the rare negative time reported by ecm...
              tt_stg1_per_file[f] += this_time
            ecm_s1_completed_per_file[f] += 1
            time_str = line
          elif line.startswith('Step 2'):
            this_time = (float(line.split(' took ')[1][:-2])/1000.0)
            if this_time >= 0: # make sure we don't average in the rare negative time reported by ecm...
              tt_stg2_per_file[f] += this_time
            ecm_c_completed_per_file[f] += 1
            time_str += '\n' + line
          elif line.startswith('Using'):
            if not factor_found:
              factor_data = line # if a factor was found, this will contain its B1, B2, and sigma...
            if need_using_line:
              ud = line.split(',')
              if len(ud) < 3: continue
              using_line = '{0:s},{1:s},{2:s}, {3:d} thread{4:s}'.format(ud[0],ud[1],ud[2],actual_num_threads, '' if (actual_num_threads == 1) else 's')
              output(using_line)

#____________________________________________________________________________
# Curves Complete |   Average seconds/curve   |    Runtime    |      ETA
#-----------------|---------------------------|---------------|--------------
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |  41d 08:37:51

              output('____________________________________________________________________________')
              output(' Curves Complete |   Average seconds/curve   |    Runtime    |      ETA')
              output('-----------------|---------------------------|---------------|--------------')
              need_using_line = False
          elif not first_file_with_factor and not factor_found and line.find('Factor found') >= 0:
            factor_found = True
            first_file_with_factor = True
            factor_value = line
            if ecm_s1_completed_per_file[f] != ecm_c_completed_per_file[f]:
              # output(' *** Step 1 count != Step 2 count, but a factor was found.  Incrementing ecm_c_completed.')
              ecm_c_completed_per_file[f] += 1
          elif first_file_with_factor and not line.startswith('Run'):
            # If either of the factor or cofactor were reported to be composite, and
            # we have find_one_factor_and_stop=0, then we'll add the composite number(s)
            # to our list and continue with the remaining number of curves on the number(s)
# ********** Factor found in step 1: 214497496343260938348887
# Found prime factor of 24 digits: 214497496343260938348887
# Composite cofactor ((637#+1)/601751640263)/214497496343260938348887 has 227 digits
            if find_one_factor_and_stop == 0 and 'composite factor' in line.lower():
              remaining_composites += '~' + line.split(' ')[-1]
            if find_one_factor_and_stop == 0 and 'composite cofactor' in line.lower():
              remaining_composites += '~' + line.split(' ')[2]
            factor_value += '\n' + line
            terminate_ecm_threads()
        #if factor_found:
        #  return

  first_getsizes = False


def monitor_ecm_threads():
  global procs, ecm_job, factor_found, ecm_c_completed, tt_stg1, tt_stg2, poll_file_delay
  global prev_ecm_c_completed, prev_tt_stg1, prev_tt_stg2, ecm_s1_completed, prev_ecm_s1_completed
  ret = 0
  running = True
  first_time = True
  fin_set = set()

  while running:
    if not first_time:
      gather_work_done(ecm_job)
      print_work_done()
      if factor_found:
        terminate_ecm_threads()
        return 0

      i = 0
      while i < poll_file_delay:
        i += 1
        time.sleep(1.0)
        print_work_done()
    else:
      time.sleep(1)
      first_time = False

    running = False
    for i, p in enumerate(procs):
      retc = p.poll()
      if retc == None:
        running = True
      else:
        ret |= retc
        fin_set = fin_set | set((i,))
  for i in reversed(sorted(list(fin_set))):
    del procs[i]
  return ret

def update_job_file():
  global ecm_job, ecm_n, ecm_args, prev_ecm_c_completed, prev_tt_stg1, prev_tt_stg2

  with open(ecm_job, 'w') as out_file:
    out_file.write('{0:s}\n'.format(ecm_n))
    out_file.write('# {0:s}\n'.format(ecm_args))
    out_file.write('# {0:d} {1:.3f} {2:.3f}\n'.format(prev_ecm_c_completed, prev_tt_stg1, prev_tt_stg2))

def find_work_done():
  global prev_ecm_c_completed, prev_tt_stg1, prev_tt_stg2, prev_ecm_s1_completed, time_str
  global factor_found, factor_value, factor_data, ecm_job, ecm_c, job_complete
  global ecm_c_has_changed, save_to_file, output_file, intResume, remaining_composites

  if not os.path.exists(ecm_job):
    return

  with open(ecm_job, 'r') as in_file:
    data = in_file.readline() # line 1 should be the number to factor
    data = in_file.readline() # line 2 should be the command line
    data = in_file.readline().split(' ') # line 3 should be the curves previously completed, tt_stg1, tt_stg2...
    prev_ecm_c_completed = int(data[1])
    prev_ecm_s1_completed = prev_ecm_c_completed
    prev_tt_stg1 = float(data[2])
    prev_tt_stg2 = float(data[3])

  job_file_prefix = ecm_job.split('.')[0]
  for f in glob.iglob(job_file_prefix + '_t*'):
    with open(f, 'r') as in_file:
      first_file_with_factor = False
      # the number of curves completed = the number of "Step 2" lines in the file
      for line in in_file:
        line = line.strip()
        if line.startswith('Step 1'):
          this_time = (float(line.split(' took ')[1][:-2])/1000.0)
          if this_time >= 0: # make sure we don't average in the rare negative time reported by ecm...
            prev_tt_stg1 += this_time
          prev_ecm_s1_completed += 1
          time_str = line
        elif line.startswith('Step 2'):
          this_time = (float(line.split(' took ')[1][:-2])/1000.0)
          if this_time >= 0: # make sure we don't average in the rare negative time reported by ecm...
            prev_tt_stg2 += this_time
          prev_ecm_c_completed += 1
          time_str += '\n' + line
        elif line.startswith('Using'):
          if not factor_found:
            factor_data = line # if a factor was found, this will contain its B1, B2, and sigma...
        elif not first_file_with_factor and not factor_found and line.find('Factor found') >= 0:
          factor_found = True
          first_file_with_factor = True
          factor_value = line
          if prev_ecm_s1_completed != prev_ecm_c_completed:
            prev_ecm_c_completed += 1
        elif first_file_with_factor and not line.startswith('Run'):
          # If either of the factor or cofactor were reported to be composite, and
          # we have find_one_factor_and_stop=0, then we'll add the composite number(s)
          # to our list and continue with the remaining number of curves on the number(s)
# ********** Factor found in step 1: 214497496343260938348887
# Found prime factor of 24 digits: 214497496343260938348887
# Composite cofactor ((637#+1)/601751640263)/214497496343260938348887 has 227 digits
          if find_one_factor_and_stop == 0 and 'composite factor' in line.lower():
            remaining_composites += '~' + line.split(' ')[-1]
          if find_one_factor_and_stop == 0 and 'composite cofactor' in line.lower():
            remaining_composites += '~' + line.split(' ')[2]
          factor_value += '\n' + line
      # comment out the following two lines so that we can make sure to count all curves run in all files...
      #if factor_found:
      #  return

    if save_to_file:
      cat_f(f, output_file)

    delete_file(f)

  if intResume == 0:
    output('-> *** Already completed {0:d} curves on this number...'.format(prev_ecm_c_completed))
  if ecm_c > 0:
    if prev_ecm_c_completed >= ecm_c:
      job_complete = True
      output('-> *** No more curves needed. Closing this job.')
    else:
      ecm_c -= prev_ecm_c_completed
      ecm_c_has_changed = True
      output('-> *** Will run {0:d} more curves.'.format(ecm_c))

  update_job_file()

# Our job file has one format:
# number to factor on line 1
# commented out command line arguments on line 2 (commented with the # symbol)
# int(number of curves previously completed) float(total time in stg1) float(total time in stg2)
def find_job_file():
  global ecm_n, ecm_job

  for f in glob.iglob('job*'):
    with open(f, 'r') as in_file:
      input1 = in_file.readline().strip()
      if input1 == ecm_n:
        input2 = in_file.readline().strip()
        if compare_ecm_args(input2):
          output('-> Found previous job file {0:s}, will resume work...'.format(f))
          ecm_job = f
          return True
        else:
          return False
  return False

def create_job_file():
  global ecm_job, ecm_n, ecm_args
  global prev_ecm_c_completed, prev_tt_stg1, prev_tt_stg2, prev_ecm_s1_completed

  # generate a new job file name with a random 4 digit number in it...
  name = 'job' + str(random.randint(0,9999)).zfill(4) + '.txt'
  while os.path.exists(name):
    name = 'job' + str(random.randint(0,9999)).zfill(4) + '.txt'

  ecm_job = name
  with open(ecm_job, 'w') as out_file:
    out_file.write('{0:s}\n'.format(ecm_n))
    out_file.write('# {0:s}\n'.format(ecm_args))
    out_file.write('# {0:d} {1:.3f} {2:.3f}\n'.format(prev_ecm_c_completed, prev_tt_stg1, prev_tt_stg2))



# Look inside an output file to find out what values GMP-ECM is using...
def get_version_info(f):
  global need_version_info, version_info

  if not os.path.exists(f): return

  with open(f, 'r') as in_file:
    for line in in_file:
      line = line.strip()
      if need_version_info and line.startswith('GMP-ECM'):
        version_info = line
        need_version_info = False
        output('{0:s}'.format(version_info))
        return

# Look inside an output file to find out what values GMP-ECM is using...
def get_using_line(f):
  global need_using_line, using_line, intNumThreads

  if not os.path.exists(f): return

  with open(f, 'r') as in_file:
    for line in in_file:
      line = line.strip()
      if line.startswith('Using'):
        if need_using_line:
          ud = line.split(',')
          if len(ud) < 3: continue
          using_line = '{0:s},{1:s},{2:s}, {3:d} thread{4:s}'.format(ud[0],ud[1],ud[2],intNumThreads, '' if (intNumThreads == 1) else 's')
          output(using_line)

#____________________________________________________________________________
# Curves Complete |   Average seconds/curve   |    Runtime    |      ETA
#-----------------|---------------------------|---------------|--------------
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |  41d 08:37:51

          output('____________________________________________________________________________')
          output(' Curves Complete |   Average seconds/curve   |    Runtime    |      ETA')
          output('-----------------|---------------------------|---------------|--------------')
          need_using_line = False
          return

# Look inside an output file to find out how much time it took to run Step 2...
# This method will only work when there is a single curve completed in the given file.
# Or, in other words, it will only return the Step 2 time from the first curve complete in a file...
# return -1.0 if the file does not exist...
def get_step2_time(f):
  if not os.path.exists(f): return -1.0

  t2_time = 0.0

  with open(f, 'r') as in_file:
    for line in in_file:
      line = line.strip()
      if line.startswith('Step 2'):
        this_time = (float(line.split(' took ')[1][:-2])/1000.0)
        if this_time >= 0: # make sure we don't average in the rare negative time reported by ecm...
          t2_time += this_time

  return t2_time


# this function will return a list of each 'B1:param:sigma' that it finds in an output file
def get_out_fin(f):
  if not os.path.exists(f):
    return []

  mylist = []
  f_found = False # did we find a factor in one of our output files...
  f_info = ''

  with open(f, 'r') as in_file:
    for line in in_file:
      line = line.strip()
# Using B1=1000000-1000000, B2=124681746, polynomial Dickson(3), sigma=3697736388
# Using B1=250000-250000, B2=124681746, polynomial Dickson(3), sigma=1:3697736388
      if line.startswith('Using'):
        ls = line.split(',')
        B1 = '0'
        param = '0'
        sigma = '0'
        for entry in ls:
          if 'B1=' in entry:
            try:
              B1 = entry.split('=')[1].split('-')[0]
            except:
              pass
          if 'sigma=' in entry:
            try:
              if ':' in entry:
                param,sigma = entry.split('=')[1].split(':')
              else:
                sigma = entry.split('=')[1]
            except:
              pass
      # We will only add entries to our list when we know that the work on this entry was completed
      # We will know it was completed if either the Step 2 time was printed out, and/or when a factor was found (in step 1 or step 2)
      # If there was an error getting the info, then we will not add this entry to our list
      if 'Step 2' in line or 'Factor found' in line:
        if 'Factor found' in line:
          f_found, f_info = find_factor_info(f)
        if B1 == '0' or sigma == '0': continue
        fin = B1 + ':' + param + ':' + sigma
        if fin not in mylist:
          mylist.append(fin)
        B1 = '0'
        param = '0'
        sigma = '0'

  return mylist, f_found, f_info


def find_factor_info(f):
  if not os.path.exists(f):
    return False, ''

  factor_found = False
  factor_data = ''
  with open(f, 'r') as in_file:
    all_lines = in_file.readlines()
  using_line = 0
  for i in range(len(all_lines)):
    line = all_lines[i]
    if 'Using' in line: using_line = i
    if 'Factor found' in line:
      factor_found = True
      break

  if factor_found:
    for line in all_lines[using_line:]:
      factor_data = factor_data + line.strip() + '\n'

  return factor_found, factor_data


def get_c_complete(f):
  if not os.path.exists(f):
    return 0

  count = 0

  with open(f, 'r') as in_file:
    for line in in_file:
      line = line.strip()
      if 'Step 2 took' in line:
        count += 1
  return count

# threadList is a list of worker threads.  Each entry keeps track of:
# [0] The index of this worker (integer)
# [1] The proc object if we are currently doing work (object)
# [2] The return code from when the executable finishes (integer)
# [3] Input file name that contains the line of work to resume (string)
# [4] Output file name where the GMP-ECM output will be stored (string)
# [5] The list of resume lines this tread is working on (list of strings)
# [6] Whether this thread is currently doing resume work (True or False)
def gather_resume_work_done():
  global threadList, intNumThreads, files_c, files_t2, files_sizes, ecm_resume_finished_file

  any_factor_found = False
  any_factor_info = ''

  for i in range(intNumThreads):
    factor_found = False
    factor_info = ''

    # if this thread isn't doing any work, there will be nothing to post process...
    if threadList[i][6] == False:
      continue

    if isinstance(threadList[i][1], int):
      retc = threadList[i][1]
    else:
      retc = threadList[i][1].poll()

    if retc == None:
      # use file sizes to reduce the number of times we read in the whole file for processing
      if files_sizes[i] != os.path.getsize(threadList[i][4]):
        files_sizes[i] = os.path.getsize(threadList[i][4]) #update the file size...
        # count how many curves are complete in this file...
        files_c[i] = get_c_complete(threadList[i][4])
        # get stage2 runtime for time estimate...
        files_t2[i] = get_step2_time(threadList[i][4])
    # if the program is done, then we can go ahead and wrap it up...
    else:
      # this thread is done working...
      # we'll post process its results one last time...
      threadList[i][6] = False
      files_c[i] = get_c_complete(threadList[i][4])
      # get stage2 runtime for time estimate
      files_t2[i] = get_step2_time(threadList[i][4])
      # write all of our resume lines (that we finished working on) to the finished file...
      # the total number of lines we finished working on is in files_c[i]...
      fin_out = ''
      for entry in threadList[i][5][:files_c[i]]:
        fin_out = fin_out + entry + '\n'
      with open(ecm_resume_finished_file, 'a') as f:
          f.write(fin_out)
      # Now that we've written the completed lines out to a file, we'll empty out the worktodo list
      # so nobody else also tries to write our completed work out to file...
      threadList[i][5] = []
      threadList[i][2] = retc

# Exit statuses returned by GMP-ECM:
# 0      Normal program termination, no factor found
# 1      Error
# 2      Composite factor found, cofactor is composite
# 6      (Probable) prime factor found, cofactor is composite
# 8      Input number found
# 10     Composite factor found, cofactor is a (probable) prime
# 14     (Probable) prime factor found, cofactor is a (probable) prime
      if retc == 0:
        factor_found, factor_info = find_factor_info(threadList[i][4])
        #factor_found = False
      elif retc < 0 or retc == 1:
        # an error occured... report that to the user...
        print('-> *** ERROR: Return code: ' + str(retc))
        die('-> *** Terminating all ecm work and quitting.')
      elif retc in [2,6,8,10,14]:
        # look for factor in output file
        factor_found, factor_info = find_factor_info(threadList[i][4])
      else:
        print('-> *** ERROR: Unknown return code: ' + str(retc))
        die('-> *** Terminating all ecm work and quitting.')

      if factor_found:
        any_factor_found = True
        any_factor_info = any_factor_info + '\n' + factor_info

      # if we were asked to save the output to a file...
      if save_to_file:
        cat_f(threadList[i][4], output_file)

      # when we're done with them, delete the temporary input and output files
      delete_file(threadList[i][3])
      delete_file(threadList[i][4])

  # If we have found a factor, then we are done and need to save our output (if asked to do so)
  # and delete all of our temporary files
  if any_factor_found:
    for worker in threadList:
      if not isinstance(worker[1], (int, str)):
        if worker[1].poll() == None:
          try:
            worker[1].terminate()
          except:
            pass
      time.sleep(0.1)

    for i in range(intNumThreads):
      # if we were asked to save the output to a file...
      if save_to_file:
        cat_f(threadList[i][4], output_file)

      # when we're done with them, delete the temporary input and output files
      delete_file(threadList[i][3])
      delete_file(threadList[i][4])


  return any_factor_found, any_factor_info


def print_resume_work_done():
  global intNumThreads, files_c, files_t2, job_start, num_resume_lines, need_using_line
  global next_log_interval, log_interval_seconds, prev_c_completed
#____________________________________________________________________________
# Curves Complete |   Average seconds/curve   |    Runtime    |      ETA
#-----------------|---------------------------|---------------|--------------
#  2114 of   6000 | Stg1  2983s | Stg2 693.5s |  22d 12:27:08 |  41d 08:37:51

  cur_c_completed = 0
  for i in range(intNumThreads):
    cur_c_completed += files_c[i]
  tot_c_completed = prev_c_completed + cur_c_completed

  t2_time = 0.0
  for i in range(intNumThreads):
    t2_time += files_t2[i]

  t_total = time.time() - job_start
  str_stg2, t_stg2 = get_avg_str(cur_c_completed, t2_time)

  # rt = get_runtime(t_total)
  rt = get_runtime(t_total)
  eta = get_eta(tot_c_completed, num_resume_lines, 0, t_stg2, t_total)

  if not need_using_line:
    print('{0:6d} of {1:6d} | Stg1 {2:s} | Stg2 {3:s} | {4:s} | {5:s}\r'
             .format(tot_c_completed, num_resume_lines, '0.000s', str_stg2, rt, eta), end='')
    sys.stdout.flush()

  if t_total > next_log_interval:
    next_log_interval = next_log_interval + log_interval_seconds # log this info once per interval...
    write_string_to_log('{0:6d} of {1:6d} | Stg1 {2:s} | Stg2 {3:s} | {4:s} | {5:s}'.format(tot_c_completed, num_resume_lines, '0.000s', str_stg2, rt, eta))


# If we are using the "-resume" feature of gmp-ecm, we will make some assumptions about the job...
# 1) This is designed to be a _simple_ way to speed up resuming ecm by running several resume jobs in parallel.
#      ie, we will not try to replicate all resume capabilities of gmp-ecm
# 2) If we find identical lines in our resume file, we will only resume one of them and skip the others
#      - If this happens, we will print out a notice to the user (if VERBOSE >= v_normal) so they know what is going on
# 3) We will use the B1 value in the resume file, and not resume with higher values of B1
# 4) We will let gmp-ecm determine which B2 value to use, which can be affected by "-maxmem" and "-k"
# 5) We will try to split up the resume work evenly between the threads.
#     - We will put total/num_threads resume lines into each file, and total%num_threads files will each get one extra line.
#      At the end of a job or when restarting a job, we will write any completed resume lines out to a "finished file"
#      This "finished file" will be used to help us keep track of work done, in case we are interrupted and need to (re)resume later
#      We will query the output files once every poll_file_delay seconds.
#    resume_job_<filename>_inp_t00.txt # input resume file for use by gmp-ecm in thread 0
#    resume_job_<filename>_inp_t01.txt # input resume file for use by gmp-ecm in thread 1
#    ...etc...
#    resume_job_<filename>_out_t00.txt # output file for resume job of gmp-ecm in thread 0
#    resume_job_<filename>_out_t01.txt # output file for resume job of gmp-ecm in thread 1
#    ...etc...
#    resume_job_<filename>_finished.txt # file where we write out each resume line that we have finished with gmp-ecm
#    where <filename> is based on the resume file name, but with any "." characters replaced by a dash.
# 6) Update so we can pass B1 values to gmp-ecm when resuming Prime95 resume files, which don't include B1 info in the resume line...
#    * Important note: Pass in the B1 value you used as a range, if you used B1=43e6 in Prime95, then pass in 43e6-43e6 as B1 here.
#    * If you only pass in 43e6, then gmp-ecm will run all of B1 again for each resume line.
def run_ecm_resume_job(p95_b1):
  global intNumThreads, ecm_args, ecm_resume_file, save_to_file, output_file, poll_file_delay
  global em_usr, em_to, em_cc, em_usr, em_pwd, em_srv, next_log_interval, log_interval_seconds
  global need_using_line, need_version_info, using_line, version_info, threadList, prev_c_completed
  global files_c, files_t2, files_sizes, num_resume_lines, tot_c_completed, job_start, ecm_resume_finished_file


  job_start = time.time()
  cur_c_completed = 0 # this keeps track of how many curves we have completed during this run of our resume job
  tot_c_completed = 0 # this keeps track of how many curves we have completed during all runs of our resume job
  # since these are resume jobs, all step 1 times will be 0.
  tt_stg2 = 0.0 # This keeps track of the total amount of time spent on Step 2 from each resume line
  any_factor_found = False # keeps track if any thread has found a factor
  any_factor_info = ''
  factor_found = False # reports if a single thread has found a factor
  factor_info = ''

  # 1) read in all resume lines of work to be done from file ecm_resume_file...
  # 2) read in all "finished" lines of work from file "resume_job_<ecm_resume_file>_finished.txt"...
  # 3) remove each finished line from our list of resume lines...
  # 4) delete any temporary files from previous resumed work that wasn't completed, ie "resume_job_<ecm_resume_file>_t00.txt" etc...
  # 5) print info on how many previous resume lines were finished (if any) and how many we have to work on...
  # 6)

  # resume file must exist for us to do any work...
  if not os.path.exists(ecm_resume_file):
    die('-> *** Error: Resume file does not appear to exist: ' + ecm_resume_file)

  all_resume_lines = []
  all_resume_lines1 = []
  all_finished_lines = []
  all_finished_lines1 = []
  num_resume_lines = 0
  num_resume_lines1 = 0
  num_finished_lines = 0
  prev_c_completed = 0

  with open(ecm_resume_file, 'r') as f:
    all_resume_lines1 = f.readlines()
  # make sure each line in all_resume_lines is unique...
  for line in all_resume_lines1:
    line = line.strip()
    if len(line) == 0: continue
    # Prime95 resume files might have extra lines that are for information purposes only.
    # We will skip those lines and not add them to our list of work to do...
    if '[' in line or 'We4:' in line: continue
    if line not in all_resume_lines:
      all_resume_lines.append(line)
  num_resume_lines = len(all_resume_lines) # total number of unique lines
  num_resume_lines1 = len(all_resume_lines1) # total number of lines

  output('->=============================================================================')
  output('-> Working on the number(s) in the resume file: ' + ecm_resume_file)
  output('-> Using up to ' + str(intNumThreads) + ' instances of GMP-ECM...')

  if num_resume_lines != num_resume_lines1:
    output('-> * Notice: Duplicate entries found in resume file: ' + ecm_resume_file)
    output('-> * Notice: Total lines = ' + str(num_resume_lines1) + ', unique lines = ' + str(num_resume_lines))
    output('-> * Notice: Will only work on the unique lines.')

  # we can't have a forward slash (/) or a backslash (\) in our file name,
  # so if our ecm_resume_file contains one of those characters, we'll use the last part for our fname
  # also, we'll replace each dot in the file name with a dash
  # ie, if ecm_resume_file = './project1/resume.txt', then our fname = 'resume-txt'
  fname = ecm_resume_file
  if '\\' in ecm_resume_file:
    fname = ecm_resume_file[ecm_resume_file.rfind('\\')+1:]
  if '/' in ecm_resume_file:
    fname = ecm_resume_file[ecm_resume_file.rfind('/')+1:]
  fname = fname.replace('.', '-')

  # Delete any old input files from previous work on this resume job
  for f in glob.iglob('resume_job_' + fname + '_inp_t*.txt'):
    delete_file(f)

  output_finished = []

  # Gather up the work done in the output files from this resume job, and then delete the old output files...
  for f in glob.iglob('resume_job_' + fname + '_out_t*.txt'):
    # if we were asked to save the output to a file...
    if save_to_file:
      cat_f(f, output_file)

    # this function will return a list of each 'B1:param:sigma' that it finds in an output file
    # we will later use these values to try to match up to the lines in our resume file...
    # also check to see if a factor was found in this output file...
    out_fin, factor_found, factor_info = get_out_fin(f)
    for entry in out_fin:
      if entry not in output_finished:
        output_finished.append(entry)

    tot_c_completed += get_c_complete(f)
    if factor_found:
      any_factor_found = True
      any_factor_info = any_factor_info + '\n' + factor_info

    # now that we've saved the work done from the output file, we can delete it...
    delete_file(f)

  ecm_resume_finished_file = 'resume_job_' + fname + '_finished.txt'
  if os.path.exists(ecm_resume_finished_file):
    with open(ecm_resume_finished_file, 'r') as f:
      all_finished_lines1 = f.readlines()
    # make sure each line in all_finished_lines is unique...
    for line in all_finished_lines1:
      line = line.strip()
      if len(line) == 0: continue
      if line not in all_finished_lines:
        all_finished_lines.append(line)
    num_finished_lines = len(all_finished_lines)

  # if our output_finished list contains entries not in our all_finished_lines,
  # then we will need to add those entries to the ecm_resume_finished_file
  for entry in output_finished:
    # first, find the resume line that corresponds to our entry, each entry looks like: 'B1:param:sigma'
    # which can be matched to a resume line like so:  if entry = '250000:1:3697736388'
    # and if resume line = METHOD=ECM; PARAM=1; SIGMA=3697736388; B1=250000; N=<num>; X=...;<snip>
    # then we will declare that we have found a match and
    # 1) if that line is not in our all_finished_lines, we'll add it to the ecm_resume_finished_file
    # 2) and then we'll add it to our all_finished_lines
    # =====
    # Note: A Prime95 resume line can/will look like:
    # N=0x...; QX=0x...; SIGMA=...
    # No B1 information is passed in, so we use p95_b1 which should be passed in via the command line when this script is called
    for rline in all_resume_lines:
      rs = rline.strip().split(';')
      B1 = '0'
      param = '0'
      sigma = '0'
      found_b1 = False
      for re in rs:
        re = re.strip()
        if 'b1=' in re.lower():
          try:
            B1 = re.split('=')[1]
            found_b1 = True
          except:
            pass
        if 'sigma=' in re.lower():
          try: sigma = re.split('=')[1]
          except: pass
        if 'param=' in re.lower():
          try: param = re.split('=')[1]
          except: pass
      if not found_b1:
        B1 = p95_b1
      rline_entry = B1 + ':' + param + ':' + sigma
      # if we have found a match, now we have to see if this resume line is in our all_finished_lines
      if entry == rline_entry:
        if rline not in all_finished_lines:
          # write it out to file...
          with open(ecm_resume_finished_file, 'a') as f:
            f.write(rline + '\n')
          # append it to our all_finished_lines list...
          all_finished_lines.append(rline)
          break


# ################################################
# If we found a factor in one, or more, of our old output files, we'll wrap up our program here...
# ################################################
  my_msg = ''
  t_total = time.time() - job_start
  if any_factor_found:
    line1 = 'Computer: ' + socket.gethostname()
    line2 = 'Report Time: ' + time.strftime('%Y/%m/%d %H:%M:%S UTC', time.gmtime())
    line3 = 'Resume line {0:d} out of {1:d}:'.format(tot_c_completed, num_resume_lines)
    line4 = any_factor_info

    my_msg = my_msg + line1 + '\n'
    my_msg = my_msg + line2 + '\n\n'
    my_msg = my_msg + line3 + '\n'
    my_msg = my_msg + line4 + '\n'

    rt = get_runtime(t_total)
    write_string_to_log('{0:6d} of {1:6d} | Stg1 {2:s} | Stg2 {3:s} | {4:s} |   0d 00:00:00'
                         .format(tot_c_completed, num_resume_lines, '0.000s', '0.000s', rt))

    write_string_to_log(line3)
    write_string_to_log(line4)

    if VERBOSE >= v_normal:
      print('Resume line {0:d} out of {1:d}:'.format(tot_c_completed, num_resume_lines))
      print(any_factor_info)

    if save_to_file:
      with open(output_file, 'a') as out_f:
        out_f.write(my_msg)
    if email_results:
      sendemail(from_addr    = em_usr,
                to_addr_list = em_to,
                cc_addr_list = em_cc,
                subject      = '[Ecm.py] Report: Factor found!',
                message      = my_msg,
                login        = em_usr,
                password     = em_pwd,
                smtpserver   = em_srv)

    # If we found a factor in our old output files, then we don't have to do any more work, so we'll quit here...
    sys.exit(0)
# ################################################


  # Now, move each of our resume lines into our workTodo list, unless a resume line is in our all_finished_lines...
  workTodo = []
  num_workTodo = 0
  for rline in all_resume_lines:
    if rline not in all_finished_lines:
      workTodo.append(rline)
  num_workTodo = len(workTodo)

  if num_workTodo == 0:
    die('-> *** All resume lines have already been finished.  Quitting.')

  output('-> Found ' + str(num_resume_lines) + ' unique resume lines to work on.')
  if num_workTodo != num_resume_lines:
    prev_c_completed = num_resume_lines - num_workTodo
    tot_c_completed = prev_c_completed
    output('-> Already finished ' + str(prev_c_completed) + ' resume lines.')
    output('-> Will continue working on the remaining ' + str(num_workTodo) + ' resume lines.')
  else:
    output('-> Will start working on the ' + str(num_workTodo) + ' resume lines.')


  # This is a list of worker threads.  Each entry keeps track of:
  # [0] The index of this worker (integer)
  # [1] The proc object if we are currently doing work (object)
  # [2] The return code from when the executable finishes (integer)
  # [3] Input file name that contains the line of work to resume (string)
  # [4] Output file name where the GMP-ECM output will be stored (string)
  # [5] The list of resume lines this tread is working on (list of strings)
  # [6] Whether this thread is currently doing resume work (True or False)
  threadList = [[i, '', 0, '', '', [], False] for i in range(intNumThreads)]


  # prepare and then start each of our gmp-ecm instances...
  resumeIndex = 0
  batch = num_workTodo//intNumThreads
  batch_remain = num_workTodo%intNumThreads
  for i in range(intNumThreads):
    start = resumeIndex
    end = resumeIndex+batch
    if i < batch_remain: end += 1
    resumeIndex = end
    threadList[i][3] = 'resume_job_' + fname + '_inp_t' + str(threadList[i][0]).zfill(2) + '.txt'
    threadList[i][4] = 'resume_job_' + fname + '_out_t' + str(threadList[i][0]).zfill(2) + '.txt'
    with open(threadList[i][3], 'w') as f:
      for j in range(start, end):
        threadList[i][5].append(workTodo[j])
        f.write(workTodo[j] + '\n')
    if len(threadList[i][5]) > 0:
      threadList[i][6] = True
      # Grab the B1 value from the first entry in our work todo list...
      wSplit = threadList[i][5][0].split(';')
      found_b1 = False
      for entry in wSplit:
        if 'B1=' in entry:
          B1 = entry.split('=')[-1]
          found_b1 = True
      if not found_b1:
        B1 = p95_b1
      my_ecm_args = ecm_args + ' -resume ' + threadList[i][3] + ' ' + B1
      threadList[i][1] = run_exe(ECM, my_ecm_args, display = v_normal, log = True,
                                 out_file = threadList[i][4], wait = False, resume = len(threadList[i][5]))
      # try not to start "too many" jobs at once.  sleep for a bit and then start another.
      time.sleep(0.1)

  ret = 0
  running = True
  first_time = True
  files_c = [0 for i in range(intNumThreads)] # total amount of curves completed in each of our files...
  files_t2 = [0 for i in range(intNumThreads)] # total amount of Step 2 time in each of our files...
  files_sizes = [0 for i in range(intNumThreads)] # size each of our files, used to detect when there is a change...

  while running:
    if first_time:
      time.sleep(1)
      first_time = False
      continue

    if need_version_info: get_version_info(threadList[0][4])
    if need_using_line:   get_using_line(threadList[0][4])

    factor_found, factor_info = gather_resume_work_done()
    print_resume_work_done()

    running = False
    for i in range(intNumThreads):
      if not threadList[i][6]: continue
      else: running = True

    if factor_found or not running:
      break

    i = 0
    while i < poll_file_delay:
      i += 1
      time.sleep(1.0)
      print_resume_work_done()



  cur_c_completed = 0
  for i in range(intNumThreads):
    cur_c_completed += files_c[i]
  tot_c_completed = prev_c_completed + cur_c_completed


  # write all of our completed lines out to the completed file...
  # make sure the entries we want to write out, aren't already in the finished file...
  fin_output = ''
  for i in range(intNumThreads):
    for entry in threadList[i][5][:files_c[i]]:
      if entry not in all_finished_lines:
        fin_output = fin_output + entry + '\n'
  if len(fin_output) > 0:
    with open(ecm_resume_finished_file, 'a') as f:
      f.write(fin_output)


  print('\n')
  my_msg = ''
  t_total = time.time() - job_start
  if factor_found:
# ################################################
    line1 = 'Computer: ' + socket.gethostname()
    line2 = 'Report Time: ' + time.strftime('%Y/%m/%d %H:%M:%S UTC', time.gmtime())
    line3 = 'Resume line {0:d} out of {1:d}:'.format(tot_c_completed, num_resume_lines)
    line4 = factor_info

    my_msg = my_msg + line1 + '\n'
    my_msg = my_msg + line2 + '\n\n'
    my_msg = my_msg + line3 + '\n'
    my_msg = my_msg + line4 + '\n'

    rt = get_runtime(t_total)
    str_stg2, t_stg2 = get_avg_str(cur_c_completed, t_total)
    write_string_to_log('{0:6d} of {1:6d} | Stg1 {2:s} | Stg2 {3:s} | {4:s} |   0d 00:00:00'
                         .format(tot_c_completed, num_resume_lines, '0.000s', str_stg2, rt))

    write_string_to_log(line3)
    write_string_to_log(line4)
# ################################################
    if VERBOSE >= v_normal:
      print('Resume line {0:d} out of {1:d}:'.format(tot_c_completed, num_resume_lines))
      print(factor_info)

    if save_to_file:
      with open(output_file, 'a') as out_f:
        out_f.write(my_msg)
    if email_results:
      sendemail(from_addr    = em_usr,
                to_addr_list = em_to,
                cc_addr_list = em_cc,
                subject      = '[Ecm.py] Report: Factor found!',
                message      = my_msg,
                login        = em_usr,
                password     = em_pwd,
                smtpserver   = em_srv)

  else:
# ################################################
    # ud = factor_info.split(',')
    # b1b2_info = '{0:s},{1:s},{2:s}, {3:d} thread{4:s}'.format(ud[0],ud[1],ud[2],intNumThreads, '' if (intNumThreads == 1) else 's')
    t_total = time.time() - job_start
    zd = '{0:.0f}'.format(math.floor(t_total/86400.0)).rjust(3) + 'd '
    zh = '{0:.0f}'.format(math.floor((t_total%86400)/3600.0)).zfill(2) + 'h '
    zm = '{0:.0f}'.format(math.floor((t_total%3600)/60.0)).zfill(2) + 'm '
    zs = '{0:.0f}'.format(math.floor(t_total%60.0)).zfill(2) + 's'
    rt = zd + zh + zm + zs

    line1 = 'Computer: ' + socket.gethostname()
    line2 = 'Report Time: ' + time.strftime('%Y/%m/%d %H:%M:%S UTC', time.gmtime())
    line3 = '{0:s}'.format(version_info)
    line4 = 'Input number(s) from resume file: ' + ecm_resume_file
    line5 = using_line #b1b2_info
    line6 = 'Finished {0:d} of {1:d} curves'.format(tot_c_completed, num_resume_lines)
    line7 = 'Average time per curve, Stage 1: {0:.3f}s, Stage 2: {1:.3f}s'.format(0, t_total/cur_c_completed)
    line8 = 'Total runtime = ' + rt
    line9 = 'No factor was found.'

    my_msg = my_msg + line1 + '\n'
    my_msg = my_msg + line2 + '\n\n'
    my_msg = my_msg + line3 + '\n'
    my_msg = my_msg + line4 + '\n'
    my_msg = my_msg + line5 + '\n'
    my_msg = my_msg + line6 + '\n'
    my_msg = my_msg + line7 + '\n'
    my_msg = my_msg + line8 + '\n'
    my_msg = my_msg + line9 + '\n'

    rt = get_runtime(t_total)
    str_stg2, t_stg2 = get_avg_str(cur_c_completed, t_total)
    write_string_to_log('{0:6d} of {1:6d} | Stg1 {2:s} | Stg2 {3:s} | {4:s} |   0d 00:00:00'
                         .format(tot_c_completed, num_resume_lines, '0.000s', str_stg2, rt))

    write_string_to_log(line9)
# ################################################
    if VERBOSE >= v_normal:
      print('-> *** No factor found.\n')

    if email_results:
      sendemail(from_addr    = em_usr,
                to_addr_list = em_to,
                cc_addr_list = em_cc,
                subject      = '[Ecm.py] Report: All curves complete, no factor found.',
                message      = my_msg,
                login        = em_usr,
                password     = em_pwd,
                smtpserver   = em_srv)

  # when we are done, make sure to quit...
  sys.exit(0)


# Parse the command line options, we'll change values as necessary
# set_args should only be true the first time the program is called
# we don't want to override the default args with the args from a resumed job
def parse_ecm_options(sargv, new_curves = 0, set_args = False, first = False, quiet = False):
  global ecm_c, intNumThreads, ecm_args, ecm_args1, ecm_args2, ecm_c_has_changed
  global intResume, output_file, number_list, resume_file, save_to_file, poll_file_delay, inp_file
  global ecm_resume_file, ecm_resume_job
  ecm_maxmem = 0
  ecm_k = 0
  opt_c = ''

  #if set_args and intResume == 0:
  #  i = 1
  #else:
  i = 0
  if 'ecm.py' in sargv[0]: sargv = sargv[1:]

  if set_args and intResume == 0:
    ecm_args = ''

  ecm_args1 = ''
  ecm_args2 = ''

  while i < len(sargv)-1:
    myString = sargv[i]
    if myString == '-c':
      try:
        if not ecm_c_has_changed: ecm_c = int(sargv[i+1])
        if new_curves > 0: ecm_c = new_curves
        if set_args: ecm_args += ' -c ' + str(ecm_c)
        i = i+1
      except:
        die('-> *** Error: invalid option for -c: {0:s}'
            .format(sargv[i+1]))
    elif myString == '-maxmem':
      try:
        ecm_maxmem = int(sargv[i+1])
        if set_args: ecm_args += ' -maxmem ' + str(ecm_maxmem)
        i = i+1
      except:
        die('-> *** Error: invalid option for -maxmem: {0:s}'
            .format(sargv[i+1]))
    elif myString == '-threads':
      try:
        intNumThreads = int(sargv[i+1])
        i = i+1
      except:
        die('-> *** Error: invalid option for -threads: {0:s}'
            .format(sargv[i+1]))
    elif myString == '-one':
      # The design of this script is to only find one factor per job
      # We put this here for the sake of completeness
      if set_args: ecm_args += ' -one'
      ecm_args1 += ' -one'
      ecm_args2 += ' -one'
    elif myString == '-x0':
      if set_args: ecm_args += ' -x0 ' + sargv[i+1]
      ecm_args1 += ' -x0 ' + sargv[i+1]
      ecm_args2 += ' -x0 ' + sargv[i+1]
      i = i+1
    elif myString == '-sigma':
      if set_args: ecm_args += ' -sigma ' + sargv[i+1]
      ecm_args1 += ' -sigma ' + sargv[i+1]
      ecm_args2 += ' -sigma ' + sargv[i+1]
      i = i+1
    elif myString == '-A':
      if set_args: ecm_args += ' -A ' + sargv[i+1]
      ecm_args1 += ' -A ' + sargv[i+1]
      ecm_args2 += ' -A ' + sargv[i+1]
      i = i+1
    elif myString == '-k':
      if set_args: ecm_args += ' -k ' + sargv[i]
      ecm_args1 += ' -k ' + sargv[i+1]
      ecm_args2 += ' -k ' + sargv[i+1]
      try:
        ecm_k = int(sargv[i+1])
      except:
        die('-> *** Error: invalid option for -k: {0:s}'.format(sargv[i+1]))
      i = i+1
    elif myString == '-power':
      if set_args: ecm_args += ' -power ' + sargv[i+1]
      ecm_args1 += ' -power ' + sargv[i+1]
      ecm_args2 += ' -power ' + sargv[i+1]
      i = i+1
    elif myString == '-dickson':
      if set_args: ecm_args += ' -dickson ' + sargv[i+1]
      ecm_args1 += ' -dickson ' + sargv[i+1]
      ecm_args2 += ' -dickson ' + sargv[i+1]
      i = i+1
    elif myString == '-base2':
      if set_args: ecm_args += ' -base2 ' + sargv[i+1]
      ecm_args1 += ' -base2 ' + sargv[i+1]
      ecm_args2 += ' -base2 ' + sargv[i+1]
      i = i+1
    elif myString == '-stage1time':
      if set_args: ecm_args += ' -stage1time ' + sargv[i+1]
      ecm_args1 += ' -stage1time ' + sargv[i+1]
      ecm_args2 += ' -stage1time ' + sargv[i+1]
      i = i+1
    elif myString == '-i':
      if set_args: ecm_args += ' -i ' + sargv[i+1]
      ecm_args1 += ' -i ' + sargv[i+1]
      ecm_args2 += ' -i ' + sargv[i+1]
      i = i+1
    elif myString == '-I':
      if set_args: ecm_args += ' -I ' + sargv[i+1]
      ecm_args1 += ' -I ' + sargv[i+1]
      ecm_args2 += ' -I ' + sargv[i+1]
      i = i+1
    elif myString == '-t':
      if set_args: ecm_args += ' -t ' + sargv[i+1]
      ecm_args1 += ' -t ' + sargv[i+1]
      ecm_args2 += ' -t ' + sargv[i+1]
      i = i+1
    elif myString == '-ve':
      if set_args: ecm_args += ' -ve ' + sargv[i+1]
      ecm_args1 += ' -ve ' + sargv[i+1]
      ecm_args2 += ' -ve ' + sargv[i+1]
      i = i+1
    elif myString == '-B2scale':
      if set_args: ecm_args += ' -B2scale ' + sargv[i+1]
      ecm_args1 += ' -B2scale ' + sargv[i+1]
      ecm_args2 += ' -B2scale ' + sargv[i+1]
      i = i+1
    elif myString == '-go':
      if set_args: ecm_args += ' -go ' + sargv[i+1]
      ecm_args1 += ' -go ' + sargv[i+1]
      ecm_args2 += ' -go ' + sargv[i+1]
      i = i+1
    elif myString == '-inp':
      inp_file = sargv[i+1]
      i = i+1
    elif myString == '-r':
      intResume = 1
      resume_file = sargv[i+1]
      if not read_resume_file(resume_file):
        die('-> *** Error: resume file does not exist: {0:s}'.format(resume_file))
      if job_complete:
        die(' ')
      i = i+1
    elif myString == '-out':
      output_file = sargv[i+1]
      save_to_file = True
      i = i+1
    elif myString == '-resume':
      ecm_resume_file = sargv[i+1]
      ecm_resume_job = True
      i = i+1
    elif myString == '-pollfiles':
      try:
        poll_file_delay = int(sargv[i+1])
        if poll_file_delay < 1:
          die('-> *** Error: invalid option for -pollfiles: {0:s}'
              .format(sargv[i+1]))
        i = i+1
      except:
        die('-> *** Error: invalid option for -pollfiles: {0:s}'
            .format(sargv[i+1]))
    elif is_nbr(myString):
      # This should only match B1 and B2 options at the "end" of the ecm command line...
      # If we encounter a number by itself, do not append it to ecm_args here...
      pass
    elif i > 0:
      if set_args: ecm_args += ' ' + sargv[i]
      ecm_args1 += ' ' + sargv[i]
      ecm_args2 += ' ' + sargv[i]
    i = i+1

  if ecm_c < 0:
    die('-> *** Error: -c parameter less than zero, quitting.')
  if ecm_maxmem < 0:
    die('-> *** Error: -maxmem parameter less than zero, quitting.')
  if intNumThreads < 1:
    die('-> Less than one thread specified, quitting.')


  # If we are using the "-resume" feature of gmp-ecm, we will make some assumptions about the job...
  # 1) This is designed to be a _simple_ way to speed up resuming ecm by running several resume jobs in parallel.
  #      ie, we will not try to replicate all resume capabilities of gmp-ecm
  # 2) If we find identical lines in our resume file, we will only resume one of them and skip the others
  #      - If this happens, we will print out a notice to the user (if VERBOSE >= v_normal) so they know what is going on
  # 3) We will use the B1 value in the resume file, and not resume with higher values of B1
  # 4) We will let gmp-ecm determine which B2 value to use, which can be affected by "-maxmem" and "-k"
  # 5) We will try to split up the resume work evenly between the threads.
  #     - We will put total/num_threads resume lines into each file, and total%num_threads files will each get one extra line.
  #      At the end of a job or when restarting a job, we will write any completed resume lines out to a "finished file"
  #      This "finished file" will be used to help us keep track of work done, in case we are interrupted and need to (re)resume later
  #      We will query the output files once every poll_file_delay seconds.
  #    resume_job_<filename>_inp_t00.txt # input resume file for use by gmp-ecm in thread 0
  #    resume_job_<filename>_inp_t01.txt # input resume file for use by gmp-ecm in thread 1
  #    ...etc...
  #    resume_job_<filename>_out_t00.txt # output file for resume job of gmp-ecm in thread 0
  #    resume_job_<filename>_out_t01.txt # output file for resume job of gmp-ecm in thread 1
  #    ...etc...
  #    resume_job_<filename>_finished.txt # file where we write out each resume line that we have finished with gmp-ecm
  #    where <filename> is based on the resume file name, but with any "." characters replaced by a dash.
  # 6) Update so we can pass B1 values to gmp-ecm when resuming Prime95 resume files, which don't include B1 info in the resume line...
  #    * Important note: Pass in the B1 value you used as a range, if you used B1=43e6 in Prime95, then pass in 43e6-43e6 as B1 here.
  #    * If you only pass in 43e6, then gmp-ecm will run all of B1 again for each resume line.
  # If we are "-resume"ing, we'll go straight to that function, and not return to the original calling code...
  p95_b1 = ''
  if ecm_resume_job:
    ecm_args = ''
    if ecm_k > 0:
      ecm_args += ' -k {0:d}'.format(ecm_k)
    if ecm_maxmem > 0:
      ecm_args += ' -maxmem {0:d}'.format(ecm_maxmem//intNumThreads)
    if (is_nbr(sargv[-1]) or is_nbr_range(sargv[-1])) and sargv[-2] not in ['-k', '-maxmem', '-threads', '-pollfiles']:
      p95_b1 = sargv[-1]
    if VERBOSE >= v_normal:
      print('-> Resuming work from resume file: ' + ecm_resume_file)
      print('-> Spreading the work across ' + str(intNumThreads) + ' thread(s)')
    run_ecm_resume_job(p95_b1)


  # grab numbers to factor and save them for later...
  if intResume != 1 and not sys.stdin.isatty() and set_args:
    data = sys.stdin.readlines()
    if VERBOSE >= v_normal:
      print('-> Number(s) to factor:')
    for line in data:
      line = line.strip().strip('"')
      if is_valid_input(line):
        number_list.append(line)
        if VERBOSE >= v_normal:
          print('-> {0:s} ({1:d} digits)'.format(line, num_digits(line)))
      else:
        print('-> *** Skipping invalid input line: {0:s}'.format(line))
  elif intResume != 1 and sys.stdin.isatty() and set_args and inp_file != '':
    print("inp_file = " + inp_file)
    if VERBOSE >= v_normal:
      print('-> Number(s) to factor:')
    with open(inp_file, 'r') as f:
      for line in f:
        line = line.strip().strip('"')
        if is_valid_input(line):
          number_list.append(line)
          if VERBOSE >= v_normal:
            print('-> {0:s} ({1:d} digits)'.format(line, num_digits(line)))
        else:
          print('-> *** Skipping invalid input line: {0:s}'.format(line))
  elif intResume != 1 and sys.stdin.isatty() and inp_file == '':
    die('-> *** Error: no input numbers found, quitting.')

  if intNumThreads >= 1 and set_args == False:
    if ecm_c == 0:
      ecm_args1 += ' -c 0'
      ecm_args2 += ' -c 0'
    elif ecm_c != 1:
      ecm_args1 += ' -c {0:d}'.format(ecm_c//intNumThreads)
      ecm_args2 += ' -c {0:d}'.format((ecm_c//intNumThreads)+1)
    if ecm_maxmem > 0:
      ecm_args1 += ' -maxmem {0:d}'.format(ecm_maxmem//intNumThreads)
      ecm_args2 += ' -maxmem {0:d}'.format(ecm_maxmem//intNumThreads)

  if (intResume == 0) or (intResume == 1 and first == False):
    strB1 = ''
    strB2 = ''
    if len(sargv) == 1:
      # we can only have B1 in this case...
      #if is_nbr(sargv[1]):
      strB1 = ' ' + sargv[0]
      strB2 = ''
      #else:
      #  print('***** ERROR: Unknown B1 value: ' + sargv[1])
    elif len(sargv) >= 2:
      # Check for both B1 and B2 here...
      if is_nbr(sargv[-2]) and is_nbr(sargv[-1]):
        if len(sargv) == 2:
          strB1 = ' ' + sargv[-2]
          strB2 = ' ' + sargv[-1]
        elif is_nbr(sargv[-3]) or not is_ecm_cmd(sargv[-3]):
          strB1 = ' ' + sargv[-2]
          strB2 = ' ' + sargv[-1]
        else:
          strB1 = ' ' + sargv[-1]
          strB2 = ''
      elif is_nbr(sargv[-1]):
        strB1 = ' ' + sargv[-1]
        strB2 = ''
      else:
        print('***** ERROR: Unknown B1 value; ' + sargv[-1])

    # The last option should be B1, append that here...
    if strB1 + strB2 == '':
      die('***** ERROR: Unable to find valid B1/B2 values.')

    if set_args: ecm_args += (strB1 + strB2)
    ecm_args1 += (strB1 + strB2)
    ecm_args2 += (strB1 + strB2)

  if intResume == 1:
    ecm_args = ecm_args1

  if VERBOSE >= v_verbose and not quiet:
    print('-> Original command line was:')
    print('-> ' + ecm_args)
    if intNumThreads == 1:
      print('-> New command line will be:')
      print('-> ' + ecm_args1)
    if intNumThreads > 1:
      print('-> New command line(s) will be either:')
      print('-> ' + ecm_args1)
      print('-> ' + ecm_args2)
    print(' ')


# ###########################################
# ########## Begin execution here ###########
# ###########################################

# str_ver = '0.30'
# str_date = '30th Nov 2014'.rjust(13)
str_ver = '0.41'
str_date = '3rd Sep 2016'.rjust(13)

if VERBOSE >= v_normal:
  print('-> ___________________________________________________________________')
  print('-> | Running ecm.py, a Python driver for distributing GMP-ECM work   |')
  print('-> | on a single machine.  It is copyright, 2011-2016, David Cleaver |')
  print('-> | and is a conversion of factmsieve.py that is Copyright, 2010,   |')
  print('-> | Brian Gladman. Version {0:s} (Python 2.6 or later) {1:s} |'.format(str_ver, str_date))
  print('-> |_________________________________________________________________|')
  print(' ')
else:
  print()

write_string_to_log('->#############################################################################')
write_string_to_log('-> Running ecm.py, version {0:s} ({1:s}) on computer {2:s}'.format(str_ver, str_date, socket.gethostname()))
write_string_to_log('-> Command line: ' + npath(sys.executable) + ' ' + ' '.join(sys.argv))

if len(sys.argv) < 2:
  print('USAGE: python.exe ecm.py [gmp-ecm options] [ecm.py options] B1 [B2] < <in_file>')
  print('  or: echo <num> | python.exe ecm.py [gmp-ecm options] [ecm.py options] B1 [B2]')
  print('  or: ecm.py -inp <in_file> [gmp-ecm options] [ecm.py options] B1 [B2]')
  print('  or: ecm.py -resume <resume_file> [ecm.py options]')
  print('    where <in_file> is a file with the number(s) to factor (one per line)')
  print('    where <resume_file> is a resume file that can be accepted by GMP-ECM')
  print('  [ecm.py options]:')
  print('     -threads n         run n separate copies of gmp-ecm (defaults to 1)')
  print('     -r <file>          resume a previously interrupted job in <file>')
  print('     -out <out_file>    each gmp-ecm will output to a different file')
  print('                        thread N writes to tN_out_file.txt, etc')
  print('     -pollfiles n       Read data from job files every n seconds (default 15)')
  print('     # --- Recommended settings ---')
  print('     # For quick jobs (less than a couple of hours): between 3 and 15 seconds')
  print('     # For small jobs (less than a day): between 15 and 45 seconds')
  print('     # For medium jobs (less than a week): between 45 and 120 seconds')
  print('     # For large jobs (less than a month): between 120 and 360 seconds')
  print(' ')
  print('  For more details on [gmp-ecm options] please run:')
  print('  ecm.exe --help')
  print('  ')
  print('  Some gmp-ecm options will be modified to spread out the work.')
  print('  If the following options are specified, this is how they will change:')
  print('  -c n        Runs n curves on the input.')
  print('              Each instance of gmp-ecm will run (n/num_threads) curves')
  print('              In case of inexact division, the first n%num_threads')
  print('                instances will run one more curve than the rest.')
  print('  -maxmem n   Tells gmp-ecm to use at most n MB of memory in Stage 2')
  print('              Each instance of gmp-ecm will get -maxmem (n/num_threads)')
  print('  ')
  sys.exit(-1)

check_binary(ECM)

signal.signal(signal.SIGINT, sig_exit)

atexit.register(terminate_ecm_threads)

parse_ecm_options(sys.argv, set_args = True, first = True)

for ecm_n in number_list:

  factor_found = False
  factor_value = ''
  factor_data = ''
  job_complete = False
  ecm_c_has_changed = False
  prev_ecm_c_completed = 0
  prev_tt_stg1 = 0
  prev_tt_stg2 = 0
  prev_ecm_s1_completed = 0
  file_sizes.clear()
  ecm_c_completed_per_file.clear()
  ecm_s1_completed_per_file.clear()
  tt_stg1_per_file.clear()
  tt_stg2_per_file.clear()
  first_getsizes = True
  need_using_line = True
  need_version_info = True
  my_msg = ''
  continue_composite = 0
  tmp_info = []

  # check to see if this ecm_n is a job we should continue...
  if ':' in ecm_n:
    continue_composite = 1
    tmp_info = ecm_n.split(':')
    ecm_n = tmp_info[0]
    # since we tacked this "-c" option to the end, it should override any earlier value of "-c"

  my_str1 = '->============================================================================='
  my_str2 = '-> Working on number: {0:s} ({1:d} digits)'.format(abbreviate(ecm_n), num_digits(ecm_n))
  write_string_to_log(my_str1)
  write_string_to_log(my_str2)
  if VERBOSE >= v_normal:
    print(my_str1)
    print(my_str2)

  if continue_composite == 1:
    parse_ecm_options(ecm_args.split(), new_curves = int(tmp_info[1]), quiet = True)
    create_job_file()
    intResume = 1
  elif intResume == 1:
    output('-> Trying to resume job in file: {0:s}'.format(resume_file))
    find_work_done()
  elif AUTORESUME:
    # Try to find out if we have already done work on this job
    # If so, we'll pick up where we left off
    # If not, we'll start a new job
    parse_ecm_options(ecm_args.split(), quiet = True)
    if find_job_file():
      find_work_done()
    else:
      create_job_file()
  else:
    # If we are not manually or automatically resuming,
    # then just create a job file and start working on it.
    parse_ecm_options(ecm_args.split(), quiet = True)
    create_job_file()

  if not factor_found and not job_complete:
    my_str = '-> Currently working on: ' + ecm_job
    if VERBOSE >= v_normal:
      print(my_str)
    write_string_to_log(my_str)
    job_start = time.time()
    if intResume == 0:
      parse_ecm_options(ecm_args.split())
    start_ecm_threads()
    ret = monitor_ecm_threads()
    if not factor_found:
      gather_work_done(ecm_job)
      print_work_done()

    if ret != 0 and not factor_found:
      die('\n-> *** Error: unexpected return value: {0:d}'.format(ret))

  print('\n')

  t_total = time.time() - job_start
  if factor_found:
# ################################################
    line1 = 'Computer: ' + socket.gethostname()
    line2 = 'Report Time: ' + time.strftime('%Y/%m/%d %H:%M:%S UTC', time.gmtime())
    line3 = '{0:s}'.format(version_info)
    line4 = 'Input number is {0:s} ({1:d} digits)'.format(ecm_n, num_digits(ecm_n))
    line5 = 'Run {0:d} out of {1:d}:'.format(ecm_c_completed, ecm_c+prev_ecm_c_completed)
    line6 = '{0:s}'.format(factor_data)
    line7 = '{0:s}'.format(time_str)
    line8 = '{0:s}'.format(factor_value)

    my_msg = my_msg + line1 + '\n'
    my_msg = my_msg + line2 + '\n\n'
    my_msg = my_msg + line3 + '\n'
    my_msg = my_msg + line4 + '\n'
    my_msg = my_msg + line5 + '\n'
    my_msg = my_msg + line6 + '\n'
    my_msg = my_msg + line7 + '\n'
    my_msg = my_msg + line8 + '\n'

    rt = get_runtime(t_total)
    str_stg1, t_stg1 = get_avg_str(ecm_s1_completed, tt_stg1)
    str_stg2, t_stg2 = get_avg_str(ecm_c_completed, tt_stg2)
    write_string_to_log('{0:6d} of {1:6d} | Stg1 {2:s} | Stg2 {3:s} | {4:s} |   0d 00:00:00'
                         .format(ecm_c_completed, ecm_c+prev_ecm_c_completed, str_stg1, str_stg2, rt))

    write_string_to_log(line3)
    write_string_to_log(line4)
    write_string_to_log(line5)
    write_string_to_log(line6)
    write_string_to_log(line7)
    write_string_to_log(line8)
# ################################################
    if VERBOSE >= v_normal:
      print('Run {0:d} out of {1:d}:'.format(ecm_c_completed, ecm_c+prev_ecm_c_completed))
      print('{0:s}'.format(factor_data))
      print('{0:s}'.format(time_str))
      print('{0:s}'.format(factor_value))
#    print('\n---------------------------------------------------------------\n')
#    print(my_msg)
#    print('\n---------------------------------------------------------------\n\n')
    if save_to_file:
      with open(output_file, 'a') as out_f:
        out_f.write(my_msg)
    if email_results:
      sendemail(from_addr    = em_usr,
                to_addr_list = em_to,
                cc_addr_list = em_cc,
                subject      = '[Ecm.py] Report: Factor found!',
                message      = my_msg,
                login        = em_usr,
                password     = em_pwd,
                smtpserver   = em_srv)

    # if we were asked to keep working, make sure we have some composites to keep working with,
    # if so, then calculate the new number of curves to run on those numbers, and then append those
    # composite_num:new_curve to our number_list so we can finish the remaining number of curves on them...
    if find_one_factor_and_stop == 0 and remaining_composites != '':
      new_curves = ecm_c + prev_ecm_c_completed - ecm_c_completed
      for entry in remaining_composites.split('~'):
        if entry != '':
          print(' ')
          print('-> * Notice: Enqueuing composite number {0:s}'.format(abbreviate(entry, length = 40)))
          print('-> * Notice: Will run the remaining {0:d} curves on it'.format(new_curves))
          number_list.append(entry + ':' + str(new_curves))
      remaining_composites = ''
      new_curves = 0
  else:
# ################################################
    ud = factor_data.split(',')
    b1b2_info = '{0:s},{1:s},{2:s}, {3:d} thread{4:s}'.format(ud[0],ud[1],ud[2],actual_num_threads, '' if (actual_num_threads == 1) else 's')
    zd = '{0:.0f}'.format(math.floor(t_total/86400.0)).rjust(3) + 'd '
    zh = '{0:.0f}'.format(math.floor((t_total%86400)/3600.0)).zfill(2) + 'h '
    zm = '{0:.0f}'.format(math.floor((t_total%3600)/60.0)).zfill(2) + 'm '
    zs = '{0:.0f}'.format(math.floor(t_total%60.0)).zfill(2) + 's'
    rt = zd + zh + zm + zs

    line1 = 'Computer: ' + socket.gethostname()
    line2 = 'Report Time: ' + time.strftime('%Y/%m/%d %H:%M:%S UTC', time.gmtime())
    line3 = '{0:s}'.format(version_info)
    line4 = 'Input number is {0:s} ({1:d} digits)'.format(ecm_n, num_digits(ecm_n))
    line5 = b1b2_info
    line6 = 'Finished {0:d} of {1:d} curves'.format(ecm_c_completed, ecm_c+prev_ecm_c_completed)
    line7 = 'Average time per curve, Stage 1: {0:.3f}s, Stage 2: {1:.3f}s'.format(tt_stg1/ecm_s1_completed, tt_stg2/ecm_c_completed)
    line8 = 'Total runtime = ' + rt
    line9 = 'No factor was found.'

    my_msg = my_msg + line1 + '\n'
    my_msg = my_msg + line2 + '\n\n'
    my_msg = my_msg + line3 + '\n'
    my_msg = my_msg + line4 + '\n'
    my_msg = my_msg + line5 + '\n'
    my_msg = my_msg + line6 + '\n'
    my_msg = my_msg + line7 + '\n'
    my_msg = my_msg + line8 + '\n'
    my_msg = my_msg + line9 + '\n'

    rt = get_runtime(t_total)
    str_stg1, t_stg1 = get_avg_str(ecm_s1_completed, tt_stg1)
    str_stg2, t_stg2 = get_avg_str(ecm_c_completed, tt_stg2)
    write_string_to_log('{0:6d} of {1:6d} | Stg1 {2:s} | Stg2 {3:s} | {4:s} |   0d 00:00:00'
                         .format(ecm_c_completed, ecm_c+prev_ecm_c_completed, str_stg1, str_stg2, rt))

    write_string_to_log(line9)
# ################################################
    if VERBOSE >= v_normal:
      print('-> *** No factor found.\n')
#    print('\n---------------------------------------------------------------\n')
#    print(my_msg)
#    print('\n---------------------------------------------------------------\n\n')
    if save_to_file:
      ecm_job_prefix = ecm_job.split('.')[0]
      for f in glob.iglob(ecm_job_prefix + '_t*'):
        cat_f(f, output_file)
    if email_results:
      sendemail(from_addr    = em_usr,
                to_addr_list = em_to,
                cc_addr_list = em_cc,
                subject      = '[Ecm.py] Report: All curves complete, no factor found.',
                message      = my_msg,
                login        = em_usr,
                password     = em_pwd,
                smtpserver   = em_srv)

  #now that we are done with this job, delete associated files...
  ecm_job_prefix = ecm_job.split('.')[0]
  if len(ecm_job_prefix) > 0:
    for f in glob.iglob(ecm_job_prefix + '*'):
      delete_file(f)

  output(' ')
