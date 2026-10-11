import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dotenv import dotenv_values
from configure_table_tennis import configure,verify_history

class SetupTests(unittest.TestCase):
    def test_saves_only_after_verified_preserves_other_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'.env';path.write_text('ODDS_API_KEY=existing-test-key\nOTHER=value\n')
            with patch('configure_table_tennis.verify_history',return_value={'status':'VERIFIED'}):
                configure('new-test-token',path)
            values=dotenv_values(path)
            self.assertEqual(values['ODDS_API_KEY'],'existing-test-key')
            self.assertEqual(values['BETSAPI_KEY'],'new-test-token');self.assertEqual(values['OTHER'],'value')

    def test_failed_access_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'.env';path.write_text('ODDS_API_KEY=existing-test-key\n');before=path.read_bytes()
            with patch('configure_table_tennis.verify_history',side_effect=ValueError('no access')):
                with self.assertRaises(ValueError):configure('new-test-token',path)
            self.assertEqual(path.read_bytes(),before)
            with self.assertRaises(ValueError):configure('existing-test-key',path)

    def test_verification_uses_completed_point_scores(self):
        raw=dict(id='1',sport_id='92',league={'name':'Czech Liga Pro','cc':'cz'},time_status='3',
                 time='1767225600',home={'id':'a','name':'A'},away={'id':'b','name':'B'},
                 scores={str(i):{'home':'11','away':'9'} for i in (1,2,3)})
        with patch('configure_table_tennis.BetsApiAdapter') as adapter:
            feed=adapter.return_value;feed.get.return_value={'results':[raw]};feed.details.return_value=[raw]
            self.assertEqual(verify_history('test-token')['completed_games'],3)
            feed.close.assert_called_once()

    def test_missing_game_scores_not_accepted(self):
        with patch('configure_table_tennis.BetsApiAdapter') as adapter:
            feed=adapter.return_value;feed.get.return_value={'results':[]};feed.details.return_value=[]
            with self.assertRaises(ValueError):verify_history('test-token')
            feed.close.assert_called_once()

if __name__=='__main__':unittest.main()
