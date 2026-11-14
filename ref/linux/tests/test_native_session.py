"""Native session shutdown must reach Phoc descendants, not only D-Bus."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('setsid'), 'setsid required')
class NativeSessionTests(unittest.TestCase):
    def exercise_session(self, early_exit):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            ready = path/'ready.json'
            command = path/'dbus-run-session'
            command.write_text('''#!/bin/sh
shift
"$@" &
child=$!
if [ "$EARLY_EXIT" = 1 ]; then
 while [ ! -s "$PROBE_READY" ]; do sleep 0.02; done
 exit 0
fi
wait "$child"
''')
            command.chmod(0o755)
            phoc = path/'phoc'
            phoc.write_text('#!'+sys.executable+'''
import json, os, pathlib, subprocess, sys, time
child_ready = os.environ['PROBE_READY'] + '.child'
child = subprocess.Popen([sys.executable, '-c',
 'import pathlib,sys,time; pathlib.Path(sys.argv[1]).touch(); time.sleep(60)',
 child_ready])
while not pathlib.Path(child_ready).exists(): time.sleep(0.01)
pathlib.Path(os.environ['PROBE_READY']).write_text(json.dumps(
 {'phoc': os.getpid(), 'child': child.pid, 'group': os.getpgrp()}))
time.sleep(60)
''')
            phoc.chmod(0o755)
            source = (ROOT/'native/phosh').read_text()
            launch = source[source.index('# Supervise the session group'):]
            env = dict(os.environ, PATH=str(path)+':'+os.environ['PATH'],
                       XDG_RUNTIME_DIR=str(path), PROBE_READY=str(ready),
                       EARLY_EXIT=str(int(early_exit)))
            proc = subprocess.Popen(['sh', '-c', launch], env=env,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            pids = None
            try:
                deadline = time.monotonic()+5
                while time.monotonic() < deadline:
                    if ready.exists():
                        try:
                            pids = json.loads(ready.read_text())
                            break
                        except json.JSONDecodeError:
                            pass
                    time.sleep(0.02)
                self.assertIsNotNone(pids, 'mock session did not start')
                self.assertNotEqual(pids['group'], os.getpgrp())
                if not early_exit:
                    proc.terminate()
                self.assertEqual(proc.wait(timeout=5), 0 if early_exit else 143)
                for key in ('phoc', 'child'):
                    deadline = time.monotonic()+3
                    while time.monotonic() < deadline:
                        stat = Path('/proc')/str(pids[key])/'stat'
                        try:
                            if stat.read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                                break
                        except FileNotFoundError:
                            break
                        time.sleep(0.02)
                    else:
                        self.fail(key+' survived session cleanup')
            finally:
                if pids and pids['group'] != os.getpgrp():
                    try:
                        os.killpg(pids['group'], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=5)

    def test_service_term_stops_compositor_and_descendant(self):
        self.exercise_session(False)

    def test_wrapper_exit_also_cleans_up_descendants(self):
        self.exercise_session(True)
