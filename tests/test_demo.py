"""Runtime checks require only the Python standard library, no account or model."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'packages/demo'

class DemoTests(unittest.TestCase):
    def server(self, messages):
        source = (ROOT / 'sources/mcp_server.py').read_text()
        result = subprocess.run([sys.executable, '-u', '-c', source],
                                input=''.join(json.dumps(m)+'\n' for m in messages),
                                text=True, capture_output=True, timeout=5, check=True)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_mcp_initialize_list_call_and_notification(self):
        replies = self.server([
            {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26'}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/list'},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'demo.ping','arguments':{}}}])
        self.assertEqual(len(replies),3)
        self.assertEqual(replies[0]['result']['protocolVersion'],'2025-03-26')
        self.assertEqual(replies[1]['result']['tools'][0]['name'],'demo.ping')
        self.assertEqual(replies[2]['result']['content'],[{'type':'text','text':'FLINT_DEMO_OK'}])

    def test_mcp_unknown_tool_and_nonempty_arguments_are_rejected(self):
        for name,args in [('other.tool',{}),('demo.ping',{'path':'secret'})]:
            result=self.server([{'jsonrpc':'2.0','id':1,'method':'tools/call',
                                 'params':{'name':name,'arguments':args}}])
            self.assertIn('error',result[0])
            self.assertNotIn('FLINT_DEMO_OK',json.dumps(result))

    def test_embedded_server_matches_readable_source(self):
        # The inline Python literal is JSON-encoded in YAML: no YAML dependency needed.
        text=(DEMO/'connection/connection.yaml').read_text()
        arg=next(line.strip()[2:] for line in text.splitlines() if line.strip().startswith('- "exec('))
        code=json.loads(arg)
        expression=ast.parse(code,mode='eval').body
        self.assertEqual(expression.func.id,'exec')
        self.assertEqual(ast.literal_eval(expression.args[0]),(ROOT/'sources/mcp_server.py').read_text())
        self.assertFalse(any(ord(c)<32 for c in code))
        self.assertLessEqual(len(code),4096)

    def test_hook_exact_event_and_no_persistence(self):
        script=DEMO/'hooks/hooks/flint-demo-note/hook.py'
        with tempfile.TemporaryDirectory() as directory:
            reply=subprocess.run([sys.executable,str(script)],input=json.dumps({'hook_event_name':'UserPromptSubmit'}),
                                 cwd=directory,text=True,capture_output=True,timeout=5,check=True)
            context=json.loads(reply.stdout)['hookSpecificOutput']['additionalContext']
            self.assertIn('FLINT_DEMO_HOOK',context)
            self.assertEqual(list(Path(directory).iterdir()),[])
            wrong=subprocess.run([sys.executable,str(script)],input=json.dumps({'hook_event_name':'Stop'}),
                                 cwd=directory,text=True,capture_output=True,timeout=5)
            self.assertNotEqual(wrong.returncode,0)
            self.assertEqual(wrong.stdout,'')

    def test_workflow_reports_missing_then_present_instructions_without_writes(self):
        script=DEMO/'workflows/workflows/flint-demo-check/scripts/check.py'
        with tempfile.TemporaryDirectory() as directory:
            def run():
                return subprocess.run([sys.executable,str(script)],cwd=directory,text=True,
                                      capture_output=True,timeout=5,check=True)
            self.assertEqual(json.loads(run().stdout),{'status':'FAIL'})
            self.assertEqual(list(Path(directory).iterdir()),[])
            (Path(directory)/'AGENTS.md').write_text('Synthetic rules.\n')
            self.assertEqual(json.loads(run().stdout),{'status':'PASS'})
            self.assertEqual(len(list(Path(directory).iterdir())),1)

if __name__=='__main__':
    unittest.main()
