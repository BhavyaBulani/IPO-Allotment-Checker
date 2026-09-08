"""Fixture tests for the live registrar response parsers.

These lock the response shapes documented in each registrar's docstring so a
site change — or a regression in the "never fabricate a verdict" rule — fails
loudly in CI instead of surfacing as a wrong allotment verdict to a user.

Run from ``IPO_Checker/backend`` with:

    venv\\Scripts\\python.exe -m unittest discover -s tests -t .
"""

import unittest

from db.models import ResultStatus
from registrar_services.live.base_live import labels_token_match, significant_tokens
from registrar_services.live.kfin import KFinLiveRegistrar
from registrar_services.live.link_intime import LinkIntimeLiveRegistrar
from registrar_services.live.bigshare import BigshareLiveRegistrar
from registrar_services.live.alankit import AlankitLiveRegistrar
from registrar_services.live.mas import MasLiveRegistrar
from registrar_services.live.purva import PurvaLiveRegistrar
from ipo_sync.reconcile import reconcile


PAN = "ABCDE1234F"


class TokenMatchTests(unittest.TestCase):
    def test_exact_like_legal_suffix_is_a_match(self):
        self.assertTrue(labels_token_match("NTPC Green Energy", "NTPC Green Energy Ltd"))
        self.assertTrue(labels_token_match("NTPC Green Energy Ltd", "NTPC Green Energy"))

    def test_sme_is_significant_not_a_filler(self):
        # "SME" disambiguates the SME-platform issue from the mainboard one.
        self.assertFalse(labels_token_match("ABC SME", "ABC"))

    def test_shared_word_only_is_not_enough(self):
        self.assertFalse(labels_token_match("NXT Digital", "NXT Telecom"))

    def test_significant_tokens_strips_fillers(self):
        self.assertEqual(
            significant_tokens("Tata Technologies Limited & Co."),
            {"TATA", "TECHNOLOGIES", "CO"},
        )


class KFinParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = KFinLiveRegistrar()

    def test_record_not_found_is_not_allotted(self):
        result = self.parser.parse_result_text(
            '{"error": "Record Not Found"}', PAN, None, "Test IPO"
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_unknown_error_is_not_a_verdict(self):
        # The portal's "unknown error" means data may not be available yet; it
        # must never be reported (and cached) as Not Allotted.
        result = self.parser.parse_result_text(
            '{"error": "unknown error"}', PAN, None, "Test IPO"
        )
        self.assertEqual(result.status, ResultStatus.Website_Error)

    def test_alloted_shares_positive(self):
        result = self.parser.parse_result_text(
            '{"Name":"X","Pan_No":"ABCDE1234F","All_Shares":"50"}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Allotted)

    def test_alloted_shares_zero(self):
        result = self.parser.parse_result_text(
            '{"Name":"X","Pan_No":"ABCDE1234F","All_Shares":0}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_data_envelope_zero_shares_is_not_allotted(self):
        result = self.parser.parse_result_text(
            '{"data":[{"Name":"X","Pan_No":"ABCDE1234F","All_Shares":"0",'
            '"App_Shares":"7169"}]}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_data_envelope_positive_shares_is_allotted(self):
        result = self.parser.parse_result_text(
            '{"data":[{"Name":"X","Pan_No":"ABCDE1234F","All_Shares":"50"}]}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Allotted)

    def test_data_envelope_single_dict_is_allotted(self):
        result = self.parser.parse_result_text(
            '{"data":{"Name":"X","Pan_No":"ABCDE1234F","All_Shares":"1"}}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Allotted)

    def test_data_envelope_mismatched_pan_is_not_a_verdict(self):
        result = self.parser.parse_result_text(
            '{"data":[{"Name":"X","Pan_No":"XXXXX0000X","All_Shares":"50"}]}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Website_Error)

    def test_data_envelope_empty_is_not_a_verdict(self):
        result = self.parser.parse_result_text(
            '{"data":[]}', PAN, None, "Test IPO"
        )
        self.assertEqual(result.status, ResultStatus.Website_Error)

    def test_data_envelope_multiple_ambiguous_is_not_a_verdict(self):
        result = self.parser.parse_result_text(
            '{"data":[{"Pan_No":"AAAAA0000A","All_Shares":"0"},'
            '{"Pan_No":"BBBBB0000B","All_Shares":"0"}]}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Website_Error)

    def test_different_pan_is_not_a_verdict(self):
        result = self.parser.parse_result_text(
            '{"Name":"X","Pan_No":"XXXXX0000X","All_Shares":"50"}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Website_Error)

    def test_non_json_is_a_website_error(self):
        result = self.parser.parse_result_text("not json", PAN, None, "Test IPO")
        self.assertEqual(result.status, ResultStatus.Website_Error)


class LinkIntimeParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = LinkIntimeLiveRegistrar()

    def test_empty_dataset_is_not_allotted(self):
        result = self.parser.parse_result_text(
            '{"d": "<NewDataSet />"}', PAN, None, "Test IPO"
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_allot_positive_is_allotted(self):
        result = self.parser.parse_result_text(
            '{"d": "<NewDataSet><Table><ALLOT>50</ALLOT></Table></NewDataSet>"}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Allotted)

    def test_allot_zero_is_not_allotted(self):
        result = self.parser.parse_result_text(
            '{"d": "<NewDataSet><Table><ALLOT>0</ALLOT></Table></NewDataSet>"}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_no_record_message_is_not_allotted(self):
        result = self.parser.parse_result_text(
            '{"d": "<NewDataSet><Table1><Msg>NO RECORD FOUND</Msg></Table1></NewDataSet>"}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_non_json_is_a_website_error(self):
        result = self.parser.parse_result_text("nope", PAN, None, "Test IPO")
        self.assertEqual(result.status, ResultStatus.Website_Error)


class BigshareParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = BigshareLiveRegistrar()

    def test_not_found_is_not_allotted(self):
        result = self.parser.parse_result_text(
            '{"d": {"Status": "NOTFOUND"}}', PAN, None, "Test IPO"
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_alloted_positive(self):
        result = self.parser.parse_result_text(
            '{"d": {"Status": "OK", "ALLOTED": 50, "APPLIED": 100}}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Allotted)

    def test_alloted_zero(self):
        result = self.parser.parse_result_text(
            '{"d": {"Status": "OK", "ALLOTED": 0, "APPLIED": 100}}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_captcha_rejection_is_a_website_error(self):
        result = self.parser.parse_result_text(
            '{"d": {"Status": "CAPTCHA", "Message": "bad captcha"}}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Website_Error)

    def test_rate_limit_is_server_busy(self):
        result = self.parser.parse_result_text(
            '{"d": {"Status": "RATELIMIT", "Message": "try later"}}',
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Server_Busy)


class AlankitParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = AlankitLiveRegistrar()

    def test_empty_list_is_not_allotted(self):
        result = self.parser.parse_result_text("[]", PAN, None, "Test IPO")
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_alloted_positive(self):
        result = self.parser.parse_result_text(
            '[{"PANNO":"ABCDE1234F","ALLOTED":50}]', PAN, None, "Test IPO"
        )
        self.assertEqual(result.status, ResultStatus.Allotted)

    def test_alloted_zero(self):
        result = self.parser.parse_result_text(
            '[{"PANNO":"ABCDE1234F","ALLOTED":0}]', PAN, None, "Test IPO"
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_non_json_is_a_website_error(self):
        result = self.parser.parse_result_text("nope", PAN, None, "Test IPO")
        self.assertEqual(result.status, ResultStatus.Website_Error)


class MasParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = MasLiveRegistrar()

    def test_no_record_marker_is_not_allotted(self):
        result = self.parser.parse_result_text(
            "PAN NO. ENTERED BY YOU IS NOT CORRECT. PLEASE CHECK THE PAN NO.",
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_unrecognized_shape_is_a_website_error(self):
        result = self.parser.parse_result_text(
            "<html>Congratulations you are allotted</html>", PAN, None, "Test IPO"
        )
        self.assertEqual(result.status, ResultStatus.Website_Error)

    def test_found_record_nil_is_not_allotted(self):
        html = (
            "<table><tr><td><b>Shares Applied</b></td><td><b>4000</b></td>"
            "<td><b>Shares Allotted</b></td><td><b>NIL</b></td></tr>"
            "<tr><td><b>PAN</b></td><td><b>ABCDE1234F</b></td></tr></table>"
        )
        result = self.parser.parse_result_text(html, PAN, None, "Test IPO")
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_found_record_positive_is_allotted(self):
        html = (
            "<table><tr><td><b>Shares Allotted</b></td><td><b>1606</b></td></tr>"
            "<tr><td><b>PAN</b></td><td><b>ABCDE1234F</b></td></tr></table>"
        )
        result = self.parser.parse_result_text(html, PAN, None, "Test IPO")
        self.assertEqual(result.status, ResultStatus.Allotted)

    def test_found_record_wrong_pan_is_not_a_verdict(self):
        html = (
            "<table><tr><td><b>Shares Allotted</b></td><td><b>50</b></td></tr>"
            "<tr><td><b>PAN</b></td><td><b>XXXXX0000X</b></td></tr></table>"
        )
        result = self.parser.parse_result_text(html, PAN, None, "Test IPO")
        self.assertEqual(result.status, ResultStatus.Website_Error)


class PurvaParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = PurvaLiveRegistrar()

    def test_no_record_marker_is_not_allotted(self):
        result = self.parser.parse_result_text(
            "No record found. Please re-check your Application Number or PAN Number.",
            PAN, None, "Test IPO",
        )
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_unrecognized_shape_is_a_website_error(self):
        result = self.parser.parse_result_text(
            "<html>Allotment details table</html>", PAN, None, "Test IPO"
        )
        self.assertEqual(result.status, ResultStatus.Website_Error)

    def test_found_record_zero_is_not_allotted(self):
        html = (
            '<table class="results-table"><thead><tr>'
            '<th>Name</th><th>Application Number</th><th>Pan No</th>'
            '<th>DPID - Client Id</th><th>Shares Applied</th>'
            '<th>Shares Allotted</th><th>Refund Amount</th>'
            '</tr></thead><tbody><tr>'
            '<td>X</td><td>123</td><td>ABCDE1234F</td>'
            '<td>IN303575-10401255</td><td>2400</td><td>0</td><td>283200.00</td>'
            '</tr></tbody></table>'
        )
        result = self.parser.parse_result_text(html, PAN, None, "Test IPO")
        self.assertEqual(result.status, ResultStatus.Not_Allotted)

    def test_found_record_positive_is_allotted(self):
        html = (
            '<table class="results-table"><thead><tr>'
            '<th>Name</th><th>Application Number</th><th>Pan No</th>'
            '<th>DPID - Client Id</th><th>Shares Applied</th>'
            '<th>Shares Allotted</th><th>Refund Amount</th>'
            '</tr></thead><tbody><tr>'
            '<td>X</td><td>123</td><td>ABCDE1234F</td>'
            '<td>IN303575-10401255</td><td>2400</td><td>1606</td><td>0</td>'
            '</tr></tbody></table>'
        )
        result = self.parser.parse_result_text(html, PAN, None, "Test IPO")
        self.assertEqual(result.status, ResultStatus.Allotted)

    def test_found_record_wrong_pan_is_not_a_verdict(self):
        html = (
            '<table class="results-table"><thead><tr>'
            '<th>Name</th><th>Application Number</th><th>Pan No</th>'
            '<th>DPID - Client Id</th><th>Shares Applied</th>'
            '<th>Shares Allotted</th><th>Refund Amount</th>'
            '</tr></thead><tbody><tr>'
            '<td>X</td><td>123</td><td>XXXXX0000X</td>'
            '<td>IN303575-10401255</td><td>2400</td><td>50</td><td>0</td>'
            '</tr></tbody></table>'
        )
        result = self.parser.parse_result_text(html, PAN, None, "Test IPO")
        self.assertEqual(result.status, ResultStatus.Website_Error)


class ReconcileTests(unittest.TestCase):
    def test_two_sources_agreeing_validate(self):
        nse = [{"name": "Test IPO Ltd", "status": "Closed", "open_date": None,
                "close_date": None, "registrar_name": "KFin Technologies Ltd."}]
        bse = [{"name": "Test IPO Ltd", "status": "Closed", "open_date": None,
                "close_date": None, "registrar_name": "KFin Technologies Ltd."}]
        rows = reconcile(nse, bse)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].validated)
        self.assertEqual(rows[0].registrar_name, "KFin Technologies")

    def test_single_non_authoritative_source_is_held(self):
        bse = [{"name": "Test IPO Ltd", "status": "Closed", "open_date": None,
                "close_date": None, "registrar_name": "KFin Technologies Ltd."}]
        rows = reconcile([], bse)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].validated)

    def test_disagreeing_statuses_are_held(self):
        nse = [{"name": "Test IPO Ltd", "status": "Open", "open_date": None,
                "close_date": None, "registrar_name": "KFin Technologies Ltd."}]
        bse = [{"name": "Test IPO Ltd", "status": "Closed", "open_date": None,
                "close_date": None, "registrar_name": "KFin Technologies Ltd."}]
        rows = reconcile(nse, bse)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].validated)

    def test_unmapped_registrar_is_held(self):
        nse = [{"name": "Test IPO Ltd", "status": "Closed", "open_date": None,
                "close_date": None, "registrar_name": "Totally Unknown Registrar"}]
        bse = [{"name": "Test IPO Ltd", "status": "Closed", "open_date": None,
                "close_date": None, "registrar_name": "Totally Unknown Registrar"}]
        rows = reconcile(nse, bse)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].validated)


if __name__ == "__main__":
    unittest.main()
