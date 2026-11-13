"""Publishing must produce installable roots and never replace a released tag."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name)
        shutil.copytree(ROOT/'packages',self.repo/'packages')
        shutil.copytree(ROOT/'scripts',self.repo/'scripts')
        self.git('init','-b','main')
        self.git('config','user.name','Synthetic Test')
        self.git('config','user.email','test@example.invalid')
        self.git('add','.')
        self.git('commit','-m','Synthetic fixture')

    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.repo,check=True,text=True,capture_output=True).stdout.strip()

    def export(self,version='1.0.0'):
        return subprocess.run([sys.executable,str(self.repo/'scripts/export-tags.py'),'--version',version],
                              cwd=self.repo,text=True,capture_output=True,timeout=10)

    def test_install_roots_and_repeat_refusal_preserve_tags(self):
        result=self.export();self.assertEqual(result.returncode,0,result.stderr)
        tags=self.git('show-ref','--tags')
        self.assertEqual(len(tags.splitlines()),5)
        for family in ['skills','subagents','hooks','workflows','connection']:
            tag='demo-'+family+'-v1.0.0'
            name='connection.yaml' if family=='connection' else 'package.yaml'
            self.assertIn(name,self.git('ls-tree','--name-only',tag).splitlines())
            self.assertEqual(self.git('rev-parse',tag+'^{tree}'),
                             self.git('rev-parse','main:packages/demo/'+family))
        self.assertNotEqual(self.export().returncode,0)
        self.assertEqual(tags,self.git('show-ref','--tags'))

    def test_mismatched_manifest_version_creates_no_tags(self):
        self.assertNotEqual(self.export('1.1.0').returncode,0)
        self.assertEqual(self.git('tag','--list'),'')

    def test_dirty_tree_creates_no_tags(self):
        (self.repo/'unreviewed.txt').write_text('not committed')
        self.assertNotEqual(self.export().returncode,0)
        self.assertEqual(self.git('tag','--list'),'')
