"""Exercise interactive onboarding with fake radio tools, never real networking."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WifiWizardTests(unittest.TestCase):
    def run_wizard(self, answers, existing=True):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'bin').mkdir(); (p/'run').mkdir()
            commands={
                'iw':'printf "Interface wlan0\\n"',
                'ip':'exit 0', 'sleep':'exit 0', 'stty':'exit 0', 'udhcpc':'exit 0',
                'wpa_supplicant':'''for arg in "$@"; do [ "$arg" != -f ] || exit 2; done
printf started > "$WIZARD_TEST/started"''',
                'wpa_passphrase': '''read -r password
printf '%s\\n' "$#:$1" > "$WIZARD_TEST/arguments"
[ "$password" = secret-test-password ] || exit 1
printf 'network={\\n psk=%064d\\n}\\n' 0''',
                'wpa_cli': '''shift 2
case "${1:-}" in
 ping) [ "$WIZARD_EXISTING" = 1 ] && echo PONG;;
 scan_results) printf 'bssid / frequency / signal level / flags / ssid\\n01:23:45:67:89:ab\\t2412\\t-42\\t[WPA2-PSK-CCMP][ESS]\\tMy Network\\n';;
 add_network) echo 7;;
 status) echo wpa_state=COMPLETED;;
 '') read -r line; if [ "$line" = "set_network 7 psk $WIZARD_PSK" ]; then echo '> OK'; else echo FAIL; fi;;
 *) echo OK;;
esac''',
            }
            for name,body in commands.items():
                f=p/'bin'/name;f.write_text('#!/bin/sh\n'+body+'\n');f.chmod(0o755)
            script=(ROOT/'phone/pmos-connect').read_text()
            script=script.replace('export PATH=', 'export PATH='+str(p/'bin')+':',1)
            script=script.replace('/run/',str(p/'run')+'/')
            password = answers.splitlines()[-1]
            expected_psk = password if len(password) == 64 else '"'+password.replace('\\', '\\\\').replace('"', '\\"')+'"'
            env=dict(os.environ,WIZARD_TEST=str(p),WIZARD_EXISTING="1" if existing else "0",WIZARD_PSK=expected_psk)
            result=subprocess.run(['sh','-c',script],input=answers,text=True,capture_output=True,env=env,timeout=10)
            if not existing:
                self.assertTrue((p/'started').exists(),result.stderr)
            args=(p/'arguments').read_text() if (p/'arguments').exists() else ''
            return result,args

    def test_number_password_and_connection(self):
        result,args=self.run_wizard('1\nsecret-test-password\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('1) My Network',result.stdout)
        self.assertIn('Wi-Fi connected',result.stdout)
        self.assertNotIn('secret-test-password',result.stdout+result.stderr)
        self.assertEqual(args,'')

    def test_skip(self):
        result,args=self.run_wizard('0\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(args,'')

    def test_invalid_selection_then_skip(self):
        result,_=self.run_wizard('99\n0\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('No such network',result.stdout)

    def test_start_supplicant_without_debug_file_option(self):
        result,_=self.run_wizard('1\nsecret-test-password\n',existing=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Wi-Fi connected',result.stdout)

    def test_eight_character_password(self):
        result,_=self.run_wizard('1\n12345678\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Wi-Fi connected',result.stdout)

    def test_short_password_then_retry(self):
        result,_=self.run_wizard('1\nshort\n1\n12345678\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('8–63 bytes',result.stdout)
        self.assertIn('Wi-Fi connected',result.stdout)

    def test_quotes_and_backslashes(self):
        result,_=self.run_wizard('1\nabc"def\\ghi\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('abc"def',result.stdout+result.stderr)

    def test_hex_psk(self):
        result,_=self.run_wizard('1\n'+'ab'*32+'\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Wi-Fi connected',result.stdout)
