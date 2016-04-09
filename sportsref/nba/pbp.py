import re

import numpy as np
import pandas as pd

import sportsref

@sportsref.decorators.memoized
def parsePlay(details, hm, aw, is_hm):
    """Parse play details from a play-by-play string describing a play; returns
    structured data in a dictionary.

    :details: detail string for the play
    :hm: the ID of the home team (for identifying team w/ possession)
    :aw: the ID of the away team (for identifying team w/ possession)
    :is_hm: bool indicating whether it is a home play (for possession)
    :returns: dictionary of play attributes
    """
    # if input isn't a string, return None
    if not isinstance(details, basestring):
        return None

    p = {}
    p['detail'] = details
    p['home'] = hm
    p['away'] = aw
    p['isHomePlay'] = is_hm

    playerRE = r'\w{0,7}\d{2}'

    # parsing field goal attempts
    shotRE = (r'(?P<shooter>{0}) (?P<isFGM>makes|misses) (?P<isThree>2|3)\-pt'
              r' shot').format(playerRE)
    distRE = r' (?:from (?P<shotDist>\d+) ft|at rim)'
    assistRE = r' \(assist by (?P<assister>{0})\)'.format(playerRE)
    blockRE = r' \(block by (?P<blocker>{0})\)'.format(playerRE)
    shotRE = r'{0}{1}(?:{2}|{3})?'.format(shotRE, distRE, assistRE, blockRE)
    m = re.match(shotRE, details, re.IGNORECASE)
    if m:
        p['isFGA'] = True
        p.update(m.groupdict())
        p['shotDist'] = p['shotDist'] if p['shotDist'] is not None else 0
        p['shotDist'] = int(p['shotDist'])
        p['isFGM'] = p['isFGM'] == 'makes'
        p['isThree'] = p['isThree'] == '3'
        p['isAssist'] = pd.notnull(p.get('assister'))
        p['isBlock'] = pd.notnull(p.get('blocker'))
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
        return p

    # parsing jump balls
    jumpRE = (r'Jump ball: (?P<awayJumper>{0}) vs\. (?P<homeJumper>{0})'
              r'(?: \((?P<gainsPos>{0}) gains possession\))?').format(playerRE)
    m = re.match(jumpRE, details, re.IGNORECASE)
    if m:
        p['isJumpBall'] = True
        p.update(m.groupdict())
        return p

    # parsing rebounds
    rebRE = (r'(?P<isOReb>Offensive|Defensive) rebound'
             r' by (?P<rebounder>{0}|Team)').format(playerRE)
    m = re.match(rebRE, details, re.I)
    if m:
        p['isReb'] = True
        p.update(m.groupdict())
        p['isOReb'] = p['isOReb'] == 'Offensive'
        p['isDReb'] = not p['isOReb']
        p['rebTeam'], other = (hm,aw) if is_hm else (aw,hm)
        p['team'] = p['rebTeam'] if p['isOReb'] else other
        p['opp'] = p['rebTeam'] if p['isDReb'] else other
        return p

    # parsing shooting fouls
    shotFoulRE = (r'Shooting(?P<isBlockFoul> block)? foul by (?P<fouler>{0}) '
                  r'\(drawn by (?P<drewFoul>{0})\)').format(playerRE)
    m = re.match(shotFoulRE, details, re.I)
    if m:
        p['isShotFoul'] = True
        p.update(m.groupdict())
        p['isBlockFoul'] = p['isBlockFoul'] == ' block'
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
        return p

    # parsing free throws
    ftRE = (r'(?P<ftShooter>{}) (?P<isFTM>makes|misses) '
            r'(?P<isTechFT>technical )?(?P<isFlagFT>flagrant )?'
            r'(?P<isClearPathFT>clear path )?free throw'
            r'(?: (?P<ftNum>\d+) of (?P<numAtt>\d+))?').format(playerRE)
    m = re.match(ftRE, details, re.I)
    if m:
        p['isFTA'] = True
        p.update(m.groupdict())
        p['isTechFT'] = p['isTechFT'] == 'technical '
        p['isFlagFT'] = p['isFlagFT'] == 'flagrant '
        p['isClearPathFT'] = p['isClearPathFT'] == 'clear path '
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
        return p

    # parsing substitutions
    subRE = (r'(?P<subIn>{0}) enters the game for '
             r'(?P<subOut>{0})').format(playerRE)
    m = re.match(subRE, details, re.I)
    if m:
        p['isSub'] = True
        p.update(m.groupdict())
        p['subTeam'] = hm if is_hm else aw
        return p

    # parsing turnovers
    toReasons = []
    toReasons.append(r'(?P<shotClockViol>shot clock)')
    toReasons.append(r'(?P<isTravel>traveling)')
    toReasons.append(r'(?P<isOffFoul>offensive foul)')
    toReasons.append((r'(?P<stealType>[^;]+)(?:; steal by '
                      r'(?P<stealer>{0}))?').format(playerRE))
    toReasons = r'|'.join(r'(?:{})'.format(tre) for tre in toReasons)
    toRE = (r'Turnover by (?P<turnoverBy>{}|Team) '
            r'\((?:{})\)').format(playerRE, toReasons)
    m = re.match(toRE, details, re.I)
    if m:
        p['isTO'] = True
        p.update(m.groupdict())
        if p['isOffFoul']:
            return None
        p['isTravel'] = p['isTravel'] == 'traveling'
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
        return p

    # parsing offensive fouls
    offFoulRE = (r'Offensive(?P<isCharge> charge)? foul '
                 r'by (?P<turnoverBy>{0})'
                 r'(?: \(drawn by (?P<drewFoul>{0})\))?').format(playerRE)
    m = re.match(offFoulRE, details, re.I)
    if m:
        p['isFoul'] = True
        p['isOffFoul'] = True
        p['isTO'] = True
        p.update(m.groupdict())
        p['isCharge'] = p['isCharge'] == ' charge'
        p['fouler'] = p['turnoverBy']
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
        p['foulTeam'] = p['team']
        return p

    # parsing personal fouls
    foulRE = (r'Personal (?P<isTakeFoul>take )?(?P<isBlockFoul>block )?foul by'
              r' (?P<fouler>{0})(?: \(drawn by '
              r'(?P<drewFoul>{0})\))?').format(playerRE)
    m = re.match(foulRE, details, re.I)
    if m:
        p['isFoul'] = True
        p.update(m.groupdict())
        p['isTakeFoul'] = p['isTakeFoul'] == 'take '
        p['isBlockFoul'] = p['isBlockFoul'] == 'block '
        p['team'] = aw if is_hm else hm
        p['opp'] = hm if is_hm else aw
        p['foulTeam'] = p['opp']
        return p

    # parsing loose ball fouls
    looseBallRE = (r'Loose ball foul by (?P<fouler>{0})'
                   r'(?: \(drawn by (?P<drewFoul>{0})\))?').format(playerRE)
    m = re.match(looseBallRE, details, re.I)
    if m:
        p['isFoul'] = True
        p['isLooseBallFoul'] = True
        p.update(m.groupdict())
        p['foulTeam'] = hm if is_hm else aw
        return p

    # parsing away from play fouls
    awayFromBallRE = (r'Away from play foul by (?P<fouler>{0})'
                      r'(?: \(drawn by (?P<drewFoul>{0})\))?').format(playerRE)
    m = re.match(awayFromBallRE, details, re.I)
    if m:
        p['isFoul'] = True
        p['isAwayFromBallFoul'] = True
        p.update(m.groupdict())
        p['team'] = aw if is_hm else hm
        p['opp'] = hm if is_hm else aw
        p['foulTeam'] = p['opp']
        return p

    # parsing inbound fouls
    inboundRE = (r'Inbound foul by (?P<fouler>{0})'
                 r'(?: \(drawn by (?P<drewFoul>{0})\))?').format(playerRE)
    m = re.match(inboundRE, details, re.I)
    if m:
        p['isFoul'] = True
        p['isInboundFoul'] = True
        p.update(m.groupdict())
        p['team'] = aw if is_hm else hm
        p['opp'] = hm if is_hm else aw
        p['foulTeam'] = p['opp']
        return p

    # parsing flagrant fouls
    flagrantRE = (r'Flagrant foul type (?P<flagType>1|2) by (?P<fouler>{0})'
                  r'(?: \(drawn by (?P<drewFoul>{0})\))?').format(playerRE)
    m = re.match(flagrantRE, details, re.I)
    if m:
        p['isFoul'] = True
        p['isFlagrant'] = True
        p.update(m.groupdict())
        p['foulTeam'] = hm if is_hm else aw
        return p

    # parsing clear path fouls
    clearPathRE = (r'Clear path foul by (?P<fouler>{0})'
                   r'(?: \(drawn by (?P<drewFoul>{0})\))?').format(playerRE)
    m = re.match(clearPathRE, details, re.I)
    if m:
        p['isFoul'] = True
        p['isClearPathFoul'] = True
        p.update(m.groupdict())
        p['team'] = aw if is_hm else hm
        p['opp'] = hm if is_hm else aw
        p['foulTeam'] = p['opp']
        return p

    # parsing timeouts
    timeoutRE = r'(?P<timeoutTeam>.*?) (?:full )?timeout'
    m = re.match(timeoutRE, details, re.I)
    if m:
        p['isTimeout'] = True
        p.update(m.groupdict())
        p['team'] = hm if is_hm else aw
        p['opp'] = aw if is_hm else hm
        isOfficialTO = p['timeoutTeam'] == 'Official'
        p['timeoutTeam'] = \
            'Official' if isOfficialTO else \
            sportsref.nba.teams.teamIDs().get(p['team'], p['team'])
        return p

    # parsing technical fouls
    techRE = r'Technical foul by (?P<fouler>{}|Team)'.format(playerRE)
    m = re.match(techRE, details, re.I)
    if m:
        p['isFoul'] = True
        p['isTechFoul'] = True
        p.update(m.groupdict())
        p['foulTeam'] = hm if is_hm else aw
        return p

    # parsing defensive 3 seconds techs
    def3TechRE = r'Def 3 sec tech foul by (?P<fouler>{})'.format(playerRE)
    m = re.match(def3TechRE, details, re.I)
    if m:
        p['isFoul'] = True
        p['isTechFoul'] = True
        p['isDefThreeSecs'] = True
        p.update(m.groupdict())
        p['foulTeam'] = hm if is_hm else aw
        return p

    # parsing violations
    violRE = (r'Violation by (?P<violator>{0}|Team) '
              r'\((?P<violType>.*)\)').format(playerRE)
    m = re.match(violRE, details, re.I)
    if m:
        p['isViolation'] = True
        p.update(m.groupdict())
        p['violTeam'] = hm if is_hm else aw
        return p

    print 'couldn\'t parse: %s' % details
    return p
