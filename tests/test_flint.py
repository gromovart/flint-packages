"""Optional real Flint integration. Install flint-harness to enable these tests."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

try:
    from harness_core.registry import Registry
    from harness_core.git_packages import _source, stores
    from harness_core import workflow_runner
    from harness_core.connection_catalog import descriptor
    from harness_core.connection_transport import TransportBackend
except ImportError:
    raise unittest.SkipTest('Install Flint to run integration checks')

DEMO = Path(__file__).resolve().parents[1] / 'packages/demo'

class FlintTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve()
        self.project=self.base/'project';self.project.mkdir()
        self.registry=Registry(self.base/'flint')
        self.change_registry('init',{})
        self.change_registry('workspace.add',{'document':{
            'id':'demo','aliases':['demo'],'title':'Synthetic demo','context_id':'demo',
            'sources':[],'connections':[],'policy':{'allow_project_sources':True},
            'agents':[{'id':'codex','executable':str(Path(shutil.which('true')).resolve()),'version':'0.169.0'}]}})
        profile={'apiVersion':'harness/v2','kind':'ExecutionProfile','id':'default',
                 'workspace_id':'demo','project_id':'sample','agent':'codex',
                 'provider':{'mode':'native'},'runtime':[],'permissions':[],'status':'draft'}
        self.change_registry('project.add',{'workspace':'demo','document':{
            'id':'sample','aliases':['sample'],'root':str(self.project),
            'profiles':{'default':profile},'default_profile':'default'}})

    def change_registry(self,action,payload):
        plan=self.registry.plan(action,payload)
        return self.registry.apply(action,payload,plan['plan_digest'])

    def store(self,family):
        kind,source=_source(DEMO/family)
        return stores()[kind](self.registry,'demo'),source

    def install(self,family,activate=True):
        store,source=self.store(family)
        args={'source':source}
        if activate:
            args['project']='sample'
            if family!='workflows': args['agent']='codex'
        plan=store.plan('add',**args)
        return store,store.apply('add',plan['plan_digest'],**args)

    def test_all_five_formats_and_supported_project_bindings(self):
        for family in ['skills','subagents','workflows','connection','hooks']:
            self.install(family,activate=family!='hooks')
        self.assertTrue((self.project/'.agents/skills/flint-demo/SKILL.md').is_file())
        self.assertTrue((self.project/'.codex/agents/flint-demo-reviewer.toml').is_file())
        self.assertTrue((self.project/'.flint/workflows/flint-demo-check/workflow.yaml').is_file())
        self.assertIn('flint-demo-ping',(self.project/'.codex/config.toml').read_text())
        self.assertFalse((self.project/'.codex/hooks.json').exists())

    def test_codex_169_hook_activation_is_rejected_before_writes(self):
        store,source=self.store('hooks')
        before=sorted(str(p) for p in self.base.rglob('*'))
        with self.assertRaisesRegex(ValueError,'0.167'):
            store.plan('add',source=source,project='sample',agent='codex')
        self.assertEqual(before,sorted(str(p) for p in self.base.rglob('*')))

    def test_codex_167_hook_can_be_registered_and_removed(self):
        self.change_registry('workspace.edit',{'workspace':'demo','document':{'agents':[{
            'id':'codex','executable':str(Path(shutil.which('true')).resolve()),'version':'0.167.1'}]}})
        store,_=self.install('hooks')
        plan=store.plan('remove',identity='flint/demo-hooks')
        store.apply('remove',plan['plan_digest'],identity='flint/demo-hooks')
        self.assertEqual(store.inventory()['hooks'],[])

    def test_workflow_waits_then_records_manual_approval(self):
        self.install('workflows')
        (self.project/'AGENTS.md').write_text('Synthetic instructions.\n')
        plan=workflow_runner.plan_run(self.registry,'demo','flint/demo-workflows','sample')
        result=workflow_runner.start_run(self.registry,'demo','flint/demo-workflows','sample',approved_plan_digest=plan['plan_digest'])
        self.assertEqual(result['status'],'WAITING_USER')
        self.assertEqual(result['steps'][0]['outcome'],'PASS')
        result=workflow_runner.resume_run(self.registry,'demo',result['run_id'],decision='approve')
        self.assertEqual(result['status'],'COMPLETED')
        self.assertEqual(result['steps'][1]['outcome'],'MANUAL_APPROVED')

    def test_connection_uses_real_stdio_transport(self):
        spec=descriptor({'connection.yaml':(DEMO/'connection/connection.yaml').read_bytes()})
        backend=TransportBackend(spec,environment={'PATH':__import__('os').environ['PATH']},headers={},timeout=5)
        self.addCleanup(backend.close)
        backend.initialize()
        self.assertEqual(backend.tools()[0]['name'],'demo.ping')
        self.assertEqual(backend.call_tool('demo.ping',{})['content'][0]['text'],'FLINT_DEMO_OK')

    def test_remove_then_rollback_restores_exact_skill(self):
        store,_=self.install('skills')
        path=self.project/'.agents/skills/flint-demo/SKILL.md'
        original=path.read_bytes()
        plan=store.plan('remove',identity='flint/demo-skills')
        result=store.apply('remove',plan['plan_digest'],identity='flint/demo-skills')
        self.assertFalse(path.exists())
        plan=store.plan('rollback',transaction=result['transaction_id'])
        store.apply('rollback',plan['plan_digest'],transaction=result['transaction_id'])
        self.assertEqual(path.read_bytes(),original)
