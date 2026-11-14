"""Exercise history-rewrite guards with mocked Git; never mutate a repository."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('history_rewrite',ROOT/'tools/rewrite-history.py')
recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)


class HistoryRewriteTests(unittest.TestCase):
    def fixture(self,p):
        backup=p/'out/backup';backup.mkdir(parents=True)
        plan=backup/'plan.json'
        data={'head':'old-head','branch':'master','refs':'old-head refs/heads/master\ntag-head refs/tags/baseline\n',
              'files':{'README.md':'reviewed-hash'},'backup':'out/backup/history.bundle','message':recipe.MESSAGE}
        plan.write_text(json.dumps(data))
        return backup,plan,data

    def git_mock(self,data,calls,readonly=False):
        def run(*args,**kwargs):
            calls.append(args)
            if readonly and args[0]=='add':raise subprocess.CalledProcessError(128,['git',*args])
            value=data['head'] if args[0]=='rev-parse' else data['refs'] if args[0]=='show-ref' else ''
            return SimpleNamespace(stdout=value)
        return run

    def test_changed_sources_stop_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);backup,plan,data=self.fixture(p);calls=[]
            with patch.object(recipe,'ROOT',p),patch.object(recipe,'BACKUP',backup),patch.object(recipe,'PLAN',plan),patch.object(recipe,'files',return_value=[('README.md','changed')]),patch.object(recipe,'git',side_effect=self.git_mock(data,calls)):
                with self.assertRaisesRegex(RuntimeError,'sources changed'):recipe.apply()
            self.assertEqual([c[0] for c in calls],['rev-parse','show-ref'])

    def test_readonly_git_stops_before_orphan_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);backup,plan,data=self.fixture(p);calls=[]
            with patch.object(recipe,'ROOT',p),patch.object(recipe,'BACKUP',backup),patch.object(recipe,'PLAN',plan),patch.object(recipe,'files',return_value=list(data['files'].items())),patch.object(recipe,'git',side_effect=self.git_mock(data,calls,readonly=True)):
                with self.assertRaises(subprocess.CalledProcessError):recipe.apply()
            self.assertEqual(calls[-1],('add','--','.gitignore'))
            self.assertNotIn('checkout',[c[0] for c in calls])

    def test_rewrite_stages_only_reviewed_files_and_never_pushes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);backup,plan,data=self.fixture(p);calls=[]
            with patch.object(recipe,'ROOT',p),patch.object(recipe,'BACKUP',backup),patch.object(recipe,'PLAN',plan),patch.object(recipe,'files',return_value=list(data['files'].items())),patch.object(recipe,'git',side_effect=self.git_mock(data,calls)):
                recipe.apply()
            self.assertIn(('checkout','--orphan','pmos-munch-clean'),calls)
            self.assertIn(('add','--','README.md'),calls)
            self.assertIn(('update-ref','-d','refs/tags/baseline','tag-head'),calls)
            self.assertNotIn('push',[c[0] for c in calls])
            self.assertLess(next(i for i,c in enumerate(calls) if c[0]=='commit'),next(i for i,c in enumerate(calls) if c[0]=='update-ref'))
