from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import http.client
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from source_trail.core import InputError, build_note, fingerprint, markdown, parse_json, validate_packet, verify_report
from source_trail.http_api import make_server
from source_trail.provider import Fixture, Otari, ProviderError, configured
from source_trail.service import Conflict, Service

ROOT = Path(__file__).resolve().parents[1]
def packet(): return parse_json((ROOT/'examples/notes.json').read_bytes())
def choose(*ids): return {'anchor_ids': list(ids or ['opening'])}


class SpanTests(unittest.TestCase):
    def test_extractive_claim_is_exact_and_source_manifest_binds_the_full_context(self):
        original = packet(); before = deepcopy(original)
        report = build_note(original, choose('opening', 'quiet'))
        self.assertEqual(report['claims'][0]['text'], original['anchors'][0]['quote'])
        self.assertEqual(report['claims'][0]['text'], original['sources'][0]['text'][0:28])
        self.assertTrue(verify_report(report)); self.assertEqual(original, before)
        original['sources'][0]['text'] += ' Additional context.'
        self.assertNotEqual(build_note(original, choose())['packet_sha256'], report['packet_sha256'])

    def test_user_labeled_disagreement_blocks_even_when_model_omits_the_opposing_anchor(self):
        value = parse_json((ROOT/'examples/disagreement.json').read_bytes())
        report = build_note(value, choose('opening', 'charger_host'))
        self.assertEqual(report['status'], 'blocked_disagreement'); self.assertEqual(report['claims'], [])
        self.assertTrue(any('charger_volunteer' in ids for group in report['conflicts'] for ids in group['positions'].values()))
        self.assertIn('No accepted claims', markdown(report))

    def test_unknown_ids_paraphrases_and_forged_claim_fields_cannot_be_accepted(self):
        for selected in [{'anchor_ids':['missing']}, {'anchor_ids':['opening','opening']}, {'anchor_ids':[]}, {'anchor_ids':['opening'],'claim':'A false paraphrase'}, {'anchor_ids':[True]}]:
            with self.subTest(selected=selected), self.assertRaises(InputError): build_note(packet(), selected)

    def test_wrong_source_offsets_quote_and_duplicate_span_are_rejected(self):
        for change in [{'source_id':'unknown'}, {'start':-1}, {'start':True}, {'end':99999}, {'quote':'Different claim'}]:
            value=packet(); value['anchors'][0].update(change)
            with self.subTest(change=change), self.assertRaises(InputError): validate_packet(value)
        value=packet(); value['anchors'].append(value['anchors'][0] | {'id':'duplicate'})
        with self.assertRaises(InputError): validate_packet(value)

    def test_unicode_offsets_are_codepoints_and_unpaired_surrogates_fail(self):
        value=packet(); value['sources'][0]['text']='🍵准备好充电器。'; value['sources']=value['sources'][:1]
        value['anchors']=[{'id':'a','source_id':'host','start':1,'end':8,'quote':'准备好充电器。','topic':'charger','position':'bring-own'}]
        self.assertEqual(build_note(value,choose('a'))['claims'][0]['text'],'准备好充电器。')
        value['sources'][0]['text']='\ud800'
        with self.assertRaises(InputError): validate_packet(value)

    def test_json_duplicate_fields_nonfinite_limits_and_unknown_fields_fail(self):
        for content in ['{"a":1,"a":2}','{"a":NaN}','x'*1_000_001]:
            with self.assertRaises(InputError): parse_json(content)
        value=packet();value['sources'][0]['text']='x'*20001
        with self.assertRaises(InputError): validate_packet(value)
        value=packet();value['sources'][0]['url']='http://127.0.0.1/private'
        with self.assertRaises(InputError): validate_packet(value)

    def test_report_hash_detects_content_changes_and_is_not_treated_as_a_signature(self):
        report=build_note(packet(),choose());report['claims'][0]['text']='tampered'
        self.assertFalse(verify_report(report))
        for value in [None,[],{},'invalid']: self.assertFalse(verify_report(value))

    def test_deeply_nested_report_is_rejected_and_cli_exits_two_without_traceback(self):
        report=build_note(packet(),choose()); nested=0
        for _ in range(600): nested=[nested]
        report['extra']=nested
        raw=json.dumps(report)
        self.assertLess(len(raw),1_000_000)
        self.assertIsInstance(parse_json(raw),dict)
        self.assertFalse(verify_report(report))
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'report.json'
            for content in [raw,'[]']:
                path.write_text(content,encoding='utf-8')
                result=subprocess.run([sys.executable,'-m','source_trail','verify',str(path)],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(result.returncode,2,result.stderr)
                self.assertEqual(json.loads(result.stdout),{'content_hash_valid':False,'digital_signature':False})
                self.assertEqual(result.stderr,'')
            path.write_text('{',encoding='utf-8')
            result=subprocess.run([sys.executable,'-m','source_trail','verify',str(path)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertEqual(json.loads(result.stderr)['error'],'InputError')
            self.assertNotIn('Traceback',result.stderr)


class Response(io.BytesIO):
    headers={'Otari-Request-ID':'req-contract-123'}
def response(output=None, **extra):
    return Response(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(output or choose())}}], 'usage':{'cost_usd':'0.000123'}, **extra}).encode())


class ProviderTests(unittest.TestCase):
    def test_hosted_contract_uses_current_api_prefix_bearer_no_tools_and_records_safe_usage(self):
        def transport(request, timeout):
            self.assertEqual(request.full_url,'https://eu.api.otari.ai/api/v1/chat/completions')
            self.assertEqual(request.get_header('Authorization'),'Bearer contract-token-123')
            body=json.loads(request.data);self.assertFalse(body['stream']);self.assertNotIn('tools',body);self.assertNotIn('mcp_servers',body)
            self.assertEqual(body['max_tokens'],600);self.assertEqual(timeout,40)
            return response()
        selected, metadata=Otari('contract-token-123','provider/model','eu',transport).select(packet(),'Summarize the meeting plan')
        self.assertEqual(selected,choose());self.assertTrue(metadata['inference_performed'])
        self.assertEqual(metadata['cost_usd'],'0.000123');self.assertEqual(metadata['request_id'],'req-contract-123')
        self.assertEqual(len(metadata['request_sha256']),64)

    def test_configuration_missing_key_unknown_mode_region_and_token_as_model_fail_closed(self):
        self.assertIsInstance(configured({}),Fixture)
        for env in [{'SOURCE_TRAIL_MODE':'oops'}, {'SOURCE_TRAIL_MODE':'otari'}, {'SOURCE_TRAIL_MODE':'otari','OTARI_API_KEY':'abcdefgh','OTARI_MODEL':'model','OTARI_REGION':'local'}, {'SOURCE_TRAIL_MODE':'otari','OTARI_API_KEY':'abcdefgh','OTARI_MODEL':'abcdefgh'}]:
            with self.subTest(env=env),self.assertRaises(ProviderError): configured(env)

    def test_transport_exception_and_invalid_or_tool_reply_never_leak_upstream_details(self):
        secret='unit-secret-no-leak'
        for transport in [lambda *a,**k: (_ for _ in ()).throw(RuntimeError(secret)), lambda *a,**k: Response(b'not json'), lambda *a,**k: response(otari_tool_calls=[{'type':'web_fetch'}]),lambda *a,**k: Response(b'x'*200001)]:
            with self.subTest(transport=transport),self.assertRaises(ProviderError) as raised: Otari(secret,'test/model',transport=transport).select(packet(),'goal')
            self.assertNotIn(secret,str(raised.exception))

    def test_no_redirect_handler_refuses_before_a_redirected_request(self):
        from source_trail.provider import NoRedirect
        with self.assertRaises(ProviderError): NoRedirect().redirect_request(None,None,302,'',{},'http://127.0.0.1')


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.file=Path(self.temp.name)/'requests.sqlite3'

    def test_fixture_and_fresh_instance_replay_keep_inference_false(self):
        first=Service(self.file,Fixture()).suggest(packet(),'goal','fixture-request-123')
        second=Service(self.file,Fixture()).suggest(packet(),'goal','fixture-request-123')
        self.assertFalse(first['provider']['inference_performed']);self.assertTrue(second['replayed'])
        self.assertEqual(first['report'],second['report']);self.assertEqual(len(Service(self.file,Fixture()).audit()),1)

    def test_parallel_same_key_sends_at_most_one_provider_request(self):
        entered=threading.Event();release=threading.Event()
        class Slow(Fixture):
            calls=0
            def select(self,packet,goal): self.calls+=1;entered.set();release.wait(3);return super().select(packet,goal)
        provider=Slow();service=Service(self.file,provider)
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(service.suggest,packet(),'goal','concurrent-request-123');self.assertTrue(entered.wait(2))
            with self.assertRaises(ProviderError): service.suggest(packet(),'goal','concurrent-request-123')
            release.set();future.result()
        self.assertEqual(provider.calls,1)

    def test_failed_or_forged_output_is_audited_and_not_automatically_rebilled(self):
        class Bad(Fixture):
            calls=0
            def select(self,packet,goal): self.calls+=1;return {'anchor_ids':['fake-claim']},{'inference_performed':True}
        provider=Bad();service=Service(self.file,provider)
        for _ in range(2):
            with self.assertRaises(ProviderError):service.suggest(packet(),'private-goal','failed-request-123')
        self.assertEqual(provider.calls,1);audit=json.dumps(service.audit());self.assertNotIn('private-goal',audit);self.assertNotIn('The workshop',audit)
        self.assertIn('failed_or_rejected',audit)

    def test_reusing_key_with_different_input_or_provider_identity_conflicts(self):
        service=Service(self.file,Fixture());service.suggest(packet(),'goal','identity-request-123')
        with self.assertRaises(Conflict):service.suggest(packet(),'different goal','identity-request-123')
        provider=Fixture();provider.identity={'mode':'fixture','algorithm':'changed'}
        with self.assertRaises(Conflict):Service(self.file,provider).suggest(packet(),'goal','identity-request-123')

    def test_local_http_auth_schema_and_provider_failure_are_sanitized(self):
        class Bad(Fixture):
            def select(self,*_):raise RuntimeError('raw upstream key-secret-example')
        service=Service(self.file,Bad());server=make_server(('127.0.0.1',0),service,'a'*40)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),thread.join()))
        def call(path,body=None,auth=True):
            client=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            headers={'Content-Type':'application/json','Idempotency-Key':'http-request-123'}
            if auth:headers['Authorization']='Bearer '+'a'*40
            client.request('POST' if body is not None else 'GET',path,body=json.dumps(body) if body is not None else None,headers=headers)
            result=client.getresponse();raw=result.read();client.close();return result.status,raw
        self.assertEqual(call('/v1/audit',auth=False)[0],401)
        self.assertEqual(call('/v1/review',{'packet':packet(),'selection':choose(),'mode':'otari'})[0],400)
        status,raw=call('/v1/suggest',{'packet':packet(),'goal':'private goal'})
        self.assertEqual(status,503);self.assertNotIn(b'key-secret-example',raw);self.assertNotIn(b'private goal',call('/v1/audit')[1])

    def test_cli_writes_reviewable_outputs_and_conflict_exits_three(self):
        result=subprocess.run([sys.executable,'-m','source_trail','review','examples/disagreement.json','--selection','examples/selection.json','--out',str(Path(self.temp.name)/'output')],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,3,result.stderr)
        files=list((Path(self.temp.name)/'output').glob('*.json'));self.assertEqual(len(files),1)
        self.assertEqual(json.loads(files[0].read_text())['claims'],[])


if __name__=='__main__':unittest.main()
