import collections
from copy import deepcopy
import json
import os
from pprint import pprint
import requests
import time

import bs4

from pfr import decorators
from pfr import utils

PLAYER_SEASON_URL = ('http://www.pro-football-reference.com/'
                     'play-index/psl_finder.cgi')

CONSTANTS_FN = 'PSFConstants.json'

def PlayerSeasonFinder(**kwargs):
    """ Docstring will be filled in by __init__.py """

    if 'offset' not in kwargs:
        kwargs['offset'] = 0
    
    playerseasons = []
    while True:
        querystring = kwArgsToQS(**kwargs)
        url = '{}?{}'.format(PLAYER_SEASON_URL, querystring)
        if kwargs.get('verbose', False):
            print url
        html = utils.getHTML(url)
        soup = bs4.BeautifulSoup(html, 'lxml')
        yearTh = soup.select_one(
            'table#stats thead tr[class=""] th[data-stat="year_id"]'
        )
        yearIdx = soup.select('table#stats thead tr[class=""] th').index(yearTh)
        for row in soup.select('table#stats tbody tr[class=""]'):
            player_url = row.select_one('a[href*="/players/"]').get('href')
            playerID = utils.relURLToPlayerID(player_url)
            year = int(row.find_all('td')[yearIdx].string)
            playerseasons.append((playerID, year))

        if soup.find(string='Next page'):
            kwargs['offset'] += 100
        else:
            break

    return playerseasons

def kwArgsToQS(**kwargs):
    """Converts kwargs given to PSF to a querystring.

    :returns: the querystring.
    """
    # start with defaults
    inpOptDef = getInputsOptionsDefaults()
    opts = {
        name: dct['value']
        for name, dct in inpOptDef.iteritems()
    }
    
    # clean up keys and values
    for k, v in kwargs.items():
        # bool => 'Y'|'N'
        if isinstance(v, bool):
            kwargs[k] = 'Y' if v else 'N'
        # tm, team => team_id
        if k.lower() in ('tm', 'team'):
            del kwargs[k]
            kwargs['team_id'] = v
        # yr, year, yrs, years => year_min, year_max
        if k.lower() in ('yr', 'year', 'yrs', 'years'):
            del kwargs[k]
            if isinstance(v, collections.Iterable):
                lst = list(v)
                kwargs['year_min'] = min(lst)
                kwargs['year_max'] = max(lst)
            elif isinstance(v, basestring):
                v = map(int, v.split(','))
                kwargs['year_min'] = min(v)
                kwargs['year_max'] = max(v)
            else:
                kwargs['year_min'] = v
                kwargs['year_max'] = v
        # pos, position, positions => pos_is_X
        if k.lower() in ('pos', 'position', 'positions'):
            del kwargs[k]
            # make sure value is list, splitting strings on commas
            if isinstance(v, basestring):
                v = v.split(',')
            if not isinstance(v, collections.Iterable):
                v = [v]
            for pos in v:
                kwargs['pos_is_' + pos] = 'Y'
        # draft_pos, ... => draft_pos_is_X
        if k.lower() in ('draftpos', 'draftposition', 'draftpositions',
                         'draft_pos', 'draft_position', 'draft_positions'):
            del kwargs[k]
            # make sure value is list, splitting strings on commas
            if isinstance(v, basestring):
                v = v.split(',')
            if not isinstance(v, collections.Iterable):
                v = [v]
            for pos in v:
                kwargs['draft_pos_is_' + pos] = 'Y'

    # reset values to blank for defined kwargs
    for k in kwargs:
        # for regular keys
        if k in opts:
            opts[k] = []

    # update based on kwargs
    for k, v in kwargs.iteritems():
        # if overwriting a default, overwrite it
        if k in opts:
            # if multiple values separated by commas, split em
            if isinstance(v, basestring):
                v = v.split(',')
            elif not isinstance(v, collections.Iterable):
                v = [v]
            for val in v:
                opts[k].append(val)

    opts['request'] = [1]

    qs = '&'.join('{}={}'.format(name, val)
                  for name, vals in opts.iteritems() for val in vals)

    return qs

@decorators.switchToDir(os.path.dirname(os.path.realpath(__file__)))
def getInputsOptionsDefaults():
    """Handles scraping options for player-season finder form.

    :returns: {'name1': {'value': val, 'options': [opt1, ...] }, ... }
    """
    # set time variables
    if os.path.isfile(CONSTANTS_FN):
        modtime = os.path.getmtime(CONSTANTS_FN)
        curtime = time.time()
    # if file not found or it's been >= a day, generate new constants
    if not (os.path.isfile(CONSTANTS_FN) and
            int(curtime) - int(modtime) <= 24*60*60):

        # must generate the file
        print 'Regenerating constants file'

        html = utils.getHTML(PLAYER_SEASON_URL)
        soup = bs4.BeautifulSoup(html, 'lxml')

        def_dict = {}
        # start with input elements
        for inp in soup.select('form#psl_finder input[name]'):
            name = inp['name']
            # add blank dict if not present
            if name not in def_dict:
                def_dict[name] = {
                    'value': set(),
                    'options': set(),
                    'type': inp['type']
                }

            # handle checkboxes and radio buttons
            if inp['type'] in ('checkbox', 'radio'):
                # deal with default value
                if 'checked' in inp.attrs:
                    def_dict[name]['value'].add(inp['value'])
                # add to options
                def_dict[name]['options'].add(inp['value'])
            # handle other types of inputs (only other type is hidden?)
            else:
                def_dict[name]['value'].add(inp.get('value', ''))

        # deal with dropdowns (select elements)
        for sel in soup.select('form#psl_finder select[name]'):
            name = sel['name']
            # add blank dict if not present
            if name not in def_dict:
                def_dict[name] = {
                    'value': set(),
                    'options': set(),
                    'type': inp['type']
                }

            # deal with default value
            defaultOpt = sel.select_one('option[selected]')
            if defaultOpt:
                def_dict[name]['value'].add(defaultOpt.get('value', ''))
            else:
                def_dict[name]['value'].add(
                    sel.select_one('option').get('value', '')
                )
                
            # deal with options
            def_dict[name]['options'] = {opt['value']
                                         for opt in sel.select('option')
                                         if opt.get('value')}

        def_dict.pop('request', None)
        def_dict.pop('use_favorites', None)

        with open(CONSTANTS_FN, 'w+') as f:
            for k in def_dict:
                try:
                    def_dict[k]['value'] = sorted(
                        list(def_dict[k]['value']), key=int
                    )
                    def_dict[k]['options'] = sorted(
                        list(def_dict[k]['options']), key=int
                    )
                except:
                    def_dict[k]['value'] = sorted(list(def_dict[k]['value']))
                    def_dict[k]['options'] = sorted(list(def_dict[k]['options']))
            json.dump(def_dict, f)
    
    # else, just read variable from cached file
    else:
        with open(CONSTANTS_FN, 'r') as const_f:
            def_dict = json.load(const_f)

    return def_dict

# testing
if __name__ == "__main__":
    psf = PlayerSeasonFinder(**{
        'pos': 'rb', 'year_min': '2003', 'c1comp': 'gt', 'c1stat': 'rush_att', 'c1val': 50, 'order_by': 'av'
    })
    print psf
