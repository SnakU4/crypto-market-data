"""Regression tests for exact, dated, zero-cost public software-release evidence."""
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"src"))
import coin_repository_releases as mod

NOW=dt.datetime.now(dt.timezone.utc)
PUB=(NOW-dt.timedelta(hours=15)).isoformat().replace("+00:00","Z")
FUTURE=(NOW+dt.timedelta(days=1)).isoformat().replace("+00:00","Z")
DETAIL=("A maintenance release for network node operators fixes a state sync "
    "consistency issue, documents validation controls for archive nodes, "
    "updates the verification routines for network messages, and provides "
    "migration steps for peers during an upgrade window with explicit "
    "operational steps and known limitations.")
def feed(date=PUB,repo="example-org/example-project",excerpt=DETAIL):
    return (f'<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
       f'<title>v1.2.7 network node maintenance release</title>'
       f'<link href="https://github.com/{repo}/releases/tag/v1.2.7"/>'
       f'<published>{date}</published>'
       f'<content type="html">{excerpt}</content>'
       f'</entry></feed>').encode("utf-8")

ASSET={"cmc_id":220,"name":"Example Project","symbol":"EXM"}
PROFILE={"220":{"has_substantive_descriptive_context":True,
    "primary_links_unverified":{"source_code":["https://github.com/example-org/example-project"]}}}

class ReleaseEvidenceTests(unittest.TestCase):
    def test_bounded_real_publisher_release_and_persistent_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            events,cache,audit=mod.collect(tmp,[ASSET],PROFILE,[],NOW,network=True,
                download=lambda url:(feed(),"OK"))
            self.assertEqual(audit["repositories_probed"],1)
            self.assertEqual(audit["new_substantive_release_events"],1)
            self.assertEqual(audit["newly_supported_coins"],1)
            self.assertEqual(events[0]["candidate_cmc_ids"],[220])
            self.assertEqual(events[0]["claim_status"],
                "PROJECT_SOFTWARE_RELEASE_NOT_VERIFIED_PRICE_CATALYST")
            self.assertEqual(events[0]["observed_source_repo"],
                "https://github.com/example-org/example-project")
            p=pathlib.Path(tmp)/mod.HISTORY
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(json.dumps(cache),encoding="utf-8")
            replay,_,replay_audit=mod.collect(tmp,[ASSET],PROFILE,[],NOW+dt.timedelta(minutes=2),
                network=False)
            self.assertEqual(replay_audit["repositories_probed"],0)
            self.assertEqual(len(replay),1)
            older,_,_=mod.collect(tmp,[ASSET],PROFILE,NOW-dt.timedelta(days=4),
                network=False)
            self.assertEqual(older,[])


    def test_official_rest_api_keyless_validation(self):
        published=PUB
        class Response:
            def __init__(self,url,records):
                self.url=url
                self.buf=json.dumps(records).encode("utf8")
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def geturl(self):return self.url
            def read(self,n):return self.buf[:n]
        def fake_opener(req,timeout):
            self.assertEqual(req.get_header("Accept"),"application/vnd.github+json")
            self.assertFalse(req.has_header("Authorization"))
            self.assertIn("api.github.com/repos/example-org/example-project/releases",req.full_url)
            return Response(req.full_url,[{
              "name":"v1.2.7","body":DETAIL,"draft":False,
              "published_at":published,
              "html_url":"https://github.com/example-org/example-project/releases/tag/v1.2.7"
            }])
        records,status=mod.api_releases("example-org/example-project",opener=fake_opener)
        self.assertEqual(status,"OK")
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["body"],DETAIL)

    def test_prevent_unrelated_beam_ticker_collision(self):
        coin={"cmc_id":28298,"name":"Beam","symbol":"BEAM"}
        prof={"28298":{"has_substantive_descriptive_context":True,
            "primary_links_unverified":{"source_code":["https://github.com/BeamMW/beam"]}}}
        with tempfile.TemporaryDirectory() as tmp:
            events,_,audit=mod.collect(tmp,[coin],prof,[],NOW,network=True,
                download=lambda u:(_ for _ in ()).throw(AssertionError("Should quarantine")))
            self.assertFalse(events)
            self.assertEqual(audit["repositories_probed"],0)
            self.assertIn("OTHER_PROJECT_BEAM",audit["source_identity_quarantine"][0]["reason"])

    def test_reject_wrong_repo_and_undated_headline_only(self):
        self.assertIsNone(mod.valid_repo("https://github.com/orgs/something/"))
        self.assertIsNone(mod.valid_repo("https://github.com/x/y/blob/main"))
        bad={"headline":"v1.2","excerpt":"An update","published_utc":PUB,
             "url":"https://github.com/another/repo/releases/tag/v1.2"}
        self.assertIsNone(mod.release_event(ASSET,"example-org/example-project",bad,NOW,
                            mod.stamp(NOW),{}))
        with tempfile.TemporaryDirectory() as tmp:
            events,_,audit=mod.collect(tmp,[ASSET],PROFILE,NOW,network=True,
                download=lambda u:(feed(date=FUTURE),"OK"))
            self.assertFalse(events)
            self.assertEqual(audit["new_substantive_release_events"],0)

if __name__=="__main__":
    unittest.main()
