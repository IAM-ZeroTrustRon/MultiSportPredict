import unittest
from bs4 import BeautifulSoup
from tennis_package_source import parse_odds, parse_history, decimal_american


class TennisPackageTests(unittest.TestCase):
    def test_current_price_not_nested_old_price_and_swapped_spread(self):
        soup=BeautifulSoup('''<div id="oddsMenu-3-data"><table><tbody>
        <tr class="odds-type"><td>Asian Handicap -1.5 sets</td></tr>
        <tr><td class="first"><span class="t">Book</span></td><td class="value">-1.5</td>
        <td class="k1"><div class="odds-in">1.80<div class="odds-change-div"><table><tr><td>09.10. 10:00</td><td>9.99</td></tr></table></div></div></td>
        <td class="k2"><div class="odds-in">2.10</div></td></tr>
        </tbody></table></div>''','html.parser')
        _,rows=parse_odds(soup,swapped=True)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['kind'],'sets_spread')
        self.assertEqual((rows[0]['line'],rows[0]['price_a'],rows[0]['price_b']),(1.5,110,-125))

    def test_incomplete_and_quarter_lines_not_priced(self):
        soup=BeautifulSoup('''<div id="oddsMenu-2-data"><table><tbody>
        <tr class="odds-type"><td>Over/Under 21.25 games</td></tr>
        <tr><td class="first"><span class="t">Book</span></td><td class="value">21.25</td>
        <td class="k1"><div class="odds-in">1.9</div></td><td class="k2"><div class="odds-in">1.9</div></td></tr>
        <tr><td class="first"><span class="t">Book</span></td><td class="value">22.5</td>
        <td class="k1"><div class="odds-in">1.9</div></td><td class="k2"></td></tr>
        </tbody></table></div>''','html.parser')
        self.assertEqual(parse_odds(soup),( [],[] ))

    def test_only_completed_singles_before_fixture(self):
        row='''<tr><td class="time">{date}</td><td class="s-color"><span title="clay"></span></td>
        <td class="t-name"><a href="/player/a/">A A.</a><a href="/player/b/">B B.</a></td>
        <td class="round">R16</td><td><a href="/match-detail/?id={id}">{score}</a></td></tr>'''
        html='<table class="result balance"><tbody><tr class="head"><td class="t-name"><a>Tournament</a></td></tr>'
        html+=row.format(date='07.10.',id=1,score='6-3, 6-3')
        html+=row.format(date='09.10.',id=2,score='6-3, 6-3')
        html+=row.format(date='06.10.',id=3,score='6-3, 1-0 ret.')
        html+='</tbody></table>'
        rows=parse_history(BeautifulSoup(html,'html.parser'),2026,'2026-10-09')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['games'],18)
        self.assertEqual(rows[0]['winner_path'],'/player/a/')

    def test_decimal_validation(self):
        self.assertEqual(decimal_american(1.5),-200)
        with self.assertRaises(ValueError):decimal_american(1)


if __name__=='__main__':unittest.main()
