"""Fixed native adapter dispatch, never selected from an untrusted rulepack."""
import json
from pathlib import Path
from .adapters import tic_tac_toe, tennis, reversi, table_tennis, badminton
PACKS = json.loads((Path(__file__).parent / 'data/profiles/builtin.json').read_text())
ADAPTERS = {'tic_tac_toe': tic_tac_toe, 'tennis': tennis, 'reversi': reversi, 'table_tennis': table_tennis, 'badminton': badminton}
from .adapters.scoring import Scoring
for pack in PACKS.values():
    if 'scoring_awards' in pack:
        ADAPTERS[pack['adapter']] = Scoring(pack['scoring_awards'])
from .adapters import football
ADAPTERS['football'] = football
from .adapters.connection import Connection
for pack in PACKS.values():
    if 'connection_rules' in pack:
        ADAPTERS[pack['adapter']] = Connection(pack['connection_rules'])
from .adapters import sudoku
ADAPTERS.update(sudoku=sudoku)
from .adapters import hangman
ADAPTERS.update(hangman=hangman)
from .adapters import minesweeper
ADAPTERS.update(minesweeper=minesweeper)
from .adapters import darts
ADAPTERS.update(darts=darts)
from .adapters import shut_box
ADAPTERS['shut_box'] = shut_box
from .adapters import domino
ADAPTERS['domino'] = domino
from .adapters import squash
ADAPTERS['squash'] = squash
from .adapters.ordered_race import OrderedRace
for pack in PACKS.values():
    if 'ordered_race_rules' in pack:
        ADAPTERS[pack['adapter']] = OrderedRace(pack['ordered_race_rules'])
from .adapters.race import Race
for pack in PACKS.values():
    if 'race_rules' in pack:
        ADAPTERS[pack['adapter']] = Race(pack['race_rules'])
from .adapters import boulder
ADAPTERS['boulder'] = boulder
from .adapters import nonogram
ADAPTERS['nonogram'] = nonogram
from .adapters import kakuro
ADAPTERS['kakuro'] = kakuro
from .adapters import field_distance
ADAPTERS['field_distance'] = field_distance
from .adapters import bowling, cornhole
ADAPTERS.update(bowling=bowling, cornhole=cornhole)
from .adapters import bingo
ADAPTERS['bingo'] = bingo
from .adapters import categories
ADAPTERS.update(categories=categories)
from .adapters import vertical_jump
ADAPTERS['vertical_jump'] = vertical_jump
from .adapters import morris
ADAPTERS.update(morris=morris)
from .adapters import roulette, baccarat
ADAPTERS.update(roulette=roulette, baccarat=baccarat)
from .adapters import sic_bo, keno
ADAPTERS.update(sic_bo=sic_bo, keno=keno)
from .adapters.mancala import Mancala
for pack in PACKS.values():
    if 'mancala_rules' in pack:
        ADAPTERS[pack['adapter']] = Mancala(pack['mancala_rules'])
from .adapters import briscola
ADAPTERS.update(briscola=briscola)
from .adapters import hearts
ADAPTERS['hearts'] = hearts
from .adapters import spades
ADAPTERS['spades'] = spades
from .adapters import chinese_checkers
ADAPTERS['chinese_checkers'] = chinese_checkers
from .adapters import sumo
ADAPTERS.update(sumo=sumo)
from .adapters import mafia
ADAPTERS.update(mafia=mafia)
from .adapters import liars_dice
ADAPTERS.update(liars_dice=liars_dice)
from .adapters import maexchen
ADAPTERS['maexchen'] = maexchen
from .adapters import go
ADAPTERS['go'] = go
from .adapters import draughts
ADAPTERS['draughts'] = draughts
from .adapters import scopa
ADAPTERS['scopa'] = scopa
from .adapters import euchre
ADAPTERS['euchre'] = euchre
from .adapters import archery
ADAPTERS['archery'] = archery
from .adapters import president
ADAPTERS['president'] = president
from .adapters import fanorona
ADAPTERS['fanorona'] = fanorona
from .adapters import pickleball
ADAPTERS['pickleball'] = pickleball
from .adapters import crossminton
ADAPTERS['crossminton'] = crossminton
from .adapters import blackjack
ADAPTERS['blackjack'] = blackjack
from .adapters import pai_gow
ADAPTERS['pai_gow'] = pai_gow
from .adapters.poker import Poker
ADAPTERS['holdem'] = Poker(2, False)
ADAPTERS['omaha'] = Poker(4, True)
from .adapters.draw_poker import DrawPoker
ADAPTERS['draw_poker'] = DrawPoker()
from .adapters.stud import Stud
ADAPTERS['stud'] = Stud()
from .adapters import durak
ADAPTERS['durak'] = durak
from .adapters import chess
ADAPTERS['chess'] = chess
from .adapters import rummy
ADAPTERS['rummy'] = rummy
from .adapters import mau_mau
ADAPTERS['mau_mau'] = mau_mau
from .adapters import thirty_one
ADAPTERS['thirty_one'] = thirty_one
from .adapters import racquetball
ADAPTERS['racquetball'] = racquetball
from .adapters import carom
ADAPTERS['carom'] = carom
from .adapters import nine_ball
ADAPTERS['nine_ball'] = nine_ball
from .adapters import petanque
ADAPTERS['petanque'] = petanque
from .adapters import tafl
ADAPTERS['tafl'] = tafl
from .adapters import xiangqi
ADAPTERS['xiangqi'] = xiangqi
from .adapters import shogi
ADAPTERS['shogi'] = shogi
from .adapters import backgammon
ADAPTERS['backgammon'] = backgammon
from .adapters import janggi
ADAPTERS['janggi'] = janggi
from .adapters import minigolf
ADAPTERS['minigolf'] = minigolf
from .adapters import ninepin
ADAPTERS['ninepin'] = ninepin
from .adapters import beach_tennis
ADAPTERS['beach_tennis'] = beach_tennis
from .adapters import padel
ADAPTERS['padel'] = padel
from .adapters import bridge
ADAPTERS['bridge'] = bridge
from .adapters import judo
ADAPTERS['judo'] = judo
from .adapters import bjj
ADAPTERS['bjj'] = bjj
from .adapters import cribbage
ADAPTERS['cribbage'] = cribbage
from .adapters.judged_combat import JudgedCombat
for pack in PACKS.values():
    if 'combat_rules' in pack:
        ADAPTERS[pack['adapter']] = JudgedCombat(pack['combat_rules'])
from .adapters import muay_thai
ADAPTERS['muay_thai'] = muay_thai
from .adapters import sixty_six
ADAPTERS['sixty_six'] = sixty_six
from .adapters import trail_running
ADAPTERS['trail_running'] = trail_running
from .adapters import canoe_slalom
ADAPTERS['canoe_slalom'] = canoe_slalom
from .adapters import craps
ADAPTERS['craps'] = craps
from .adapters import volleyball
ADAPTERS['volleyball'] = volleyball
from .adapters import armwrestling
ADAPTERS['armwrestling'] = armwrestling
from .adapters.timed_heats import TimedHeats
for pack in PACKS.values():
    if 'gymnastics_rules' in pack:
        from .adapters.gymnastics import Gymnastics
        ADAPTERS[pack['adapter']] = Gymnastics(pack['gymnastics_rules'])
    if 'timed_heats_rules' in pack:
        ADAPTERS[pack['adapter']] = TimedHeats(pack['timed_heats_rules'])
from .adapters import weightlifting
ADAPTERS['weightlifting'] = weightlifting
from .adapters import powerlifting
ADAPTERS['powerlifting'] = powerlifting
from .adapters import precision_shooting
ADAPTERS['precision_shooting'] = precision_shooting
from .adapters import trap
ADAPTERS['trap'] = trap
from .adapters import show_jumping
ADAPTERS['show_jumping'] = show_jumping
from .adapters import agility
ADAPTERS['agility'] = agility
from .adapters import belote
ADAPTERS['belote'] = belote
from .adapters import jass
ADAPTERS['jass'] = jass
from .adapters import diving
ADAPTERS['diving'] = diving
from .adapters import dressage
ADAPTERS['dressage'] = dressage
from .adapters import kendo
ADAPTERS['kendo'] = kendo
from .adapters import kubb
ADAPTERS['kubb'] = kubb
from .adapters import shuffleboard
ADAPTERS['shuffleboard'] = shuffleboard
from .adapters import golf
ADAPTERS['golf'] = golf
from .adapters import disc_golf
ADAPTERS['disc_golf'] = disc_golf
from .adapters import breaking
ADAPTERS['breaking'] = breaking
from .adapters import parkour_speed
ADAPTERS['parkour_speed'] = parkour_speed
from .adapters import sailing
ADAPTERS['sailing'] = sailing
from .adapters import waterski
ADAPTERS['waterski'] = waterski
from .adapters import cross_country
ADAPTERS['cross_country'] = cross_country
from .adapters import biathlon
ADAPTERS['biathlon'] = biathlon
from .adapters import ski_jumping
ADAPTERS['ski_jumping'] = ski_jumping
from .adapters import nordic_combined
ADAPTERS['nordic_combined'] = nordic_combined
from .adapters import rally
ADAPTERS['rally'] = rally
from .adapters import schafkopf
ADAPTERS['schafkopf'] = schafkopf
from .adapters import rope_skipping
ADAPTERS['rope_skipping'] = rope_skipping
from .adapters.course_race import CourseRace
for pack in PACKS.values():
    if 'course_race_rules' in pack:
        ADAPTERS[pack['adapter']] = CourseRace(pack['course_race_rules'])
from .adapters import skat
ADAPTERS['skat'] = skat
from .adapters import doppelkopf
ADAPTERS['doppelkopf'] = doppelkopf
from .adapters import boccia
ADAPTERS['boccia'] = boccia
from .adapters import fencing
ADAPTERS['fencing'] = fencing
from .adapters import trampoline
ADAPTERS['trampoline'] = trampoline
from .adapters import bodybuilding
ADAPTERS['bodybuilding'] = bodybuilding
from .adapters import triathlon
ADAPTERS['triathlon'] = triathlon
from .adapters import futsal
ADAPTERS['futsal'] = futsal
from .adapters import roundnet
ADAPTERS['roundnet'] = roundnet
from .adapters import curling
ADAPTERS['curling'] = curling
from .adapters import icestock
ADAPTERS['icestock'] = icestock
from .adapters import dodgeball
ADAPTERS['dodgeball'] = dodgeball
from .adapters import karate
ADAPTERS['karate'] = karate
from .adapters import wrestling
ADAPTERS['wrestling'] = wrestling
from .adapters.board_racing import BoardRacing
ADAPTERS['board_racing_windsurf'] = BoardRacing('windsurf')
ADAPTERS['board_racing_kite'] = BoardRacing('kite')
from .adapters.lap_course import LapCourse
for pack in PACKS.values():
    if 'lap_course_rules' in pack:
        ADAPTERS[pack['adapter']] = LapCourse(pack['lap_course_rules'])
from .adapters import ultimate
ADAPTERS['ultimate'] = ultimate
from .adapters import basketball
ADAPTERS['basketball'] = basketball
from .adapters import netball
ADAPTERS['netball'] = netball
from .adapters import snooker
ADAPTERS['snooker'] = snooker
from .adapters.rugby import Rugby
ADAPTERS['rugby_union'] = Rugby('union')
ADAPTERS['rugby_league'] = Rugby('league')
from .adapters import australian_football
ADAPTERS['australian_football'] = australian_football
from .adapters.gaelic import Gaelic
ADAPTERS['gaelic_football'] = Gaelic('football')
ADAPTERS['gaelic_hurling'] = Gaelic('hurling')
from .adapters import decathlon
ADAPTERS['decathlon'] = decathlon
from .adapters.circuit_race import CircuitRace
ADAPTERS['circuit_race_circuit'] = CircuitRace('circuit')
ADAPTERS['circuit_race_kart'] = CircuitRace('kart')
from .adapters.motor_race import MotorRace
ADAPTERS['motor_race_motorcycle'] = MotorRace('motorcycle')
ADAPTERS['motor_race_motocross'] = MotorRace('motocross')
from .adapters import eventing
ADAPTERS['eventing'] = eventing
from .adapters import canasta
ADAPTERS['canasta'] = canasta
from .adapters import aerials
ADAPTERS['aerials'] = aerials
from .adapters import handball
ADAPTERS['handball'] = handball
from .adapters.panel_final import PanelFinal
for pack in PACKS.values():
    if 'panel_final_rules' in pack:
        ADAPTERS[pack['adapter']] = PanelFinal(pack['panel_final_rules'])
from .adapters import dancesport
ADAPTERS['dancesport'] = dancesport
from .adapters import figure_skating
ADAPTERS['figure_skating'] = figure_skating
from .adapters import surfing
ADAPTERS['surfing'] = surfing
from .adapters import field_hockey
ADAPTERS['field_hockey'] = field_hockey
from .adapters import pelota
ADAPTERS['pelota'] = pelota
from .adapters import tamburello
ADAPTERS['tamburello'] = tamburello
from .adapters import real_tennis
ADAPTERS['real_tennis'] = real_tennis
from .adapters import tchoukball
ADAPTERS['tchoukball'] = tchoukball
from .adapters import sambo
ADAPTERS['sambo'] = sambo
from .adapters import taekwondo
ADAPTERS['taekwondo'] = taekwondo
from .adapters import sanda
ADAPTERS['sanda'] = sanda
from .adapters import savate
ADAPTERS['savate'] = savate
from .adapters import fistball
ADAPTERS['fistball'] = fistball
from .adapters import korfball
ADAPTERS['korfball'] = korfball
from .adapters import golf_croquet
ADAPTERS['golf_croquet'] = golf_croquet
from .adapters import diamond
ADAPTERS['baseball'] = diamond
ADAPTERS['softball'] = diamond
from .adapters import flag_football
ADAPTERS['flag_football'] = flag_football
from .adapters import lacrosse_sixes
ADAPTERS['lacrosse_sixes'] = lacrosse_sixes
from .adapters import floorball
ADAPTERS['floorball'] = floorball
from .adapters import tarock
ADAPTERS['tarock'] = tarock
from .adapters import cricket
ADAPTERS['cricket'] = cricket
from .adapters import mahjong
ADAPTERS['mahjong'] = mahjong
from .adapters import underwater_rugby
ADAPTERS['underwater_rugby'] = underwater_rugby
from .adapters import sepaktakraw
ADAPTERS['sepaktakraw'] = sepaktakraw
from .adapters import kabaddi
ADAPTERS['kabaddi'] = kabaddi
from .adapters import canoe_polo
ADAPTERS['canoe_polo'] = canoe_polo
from .adapters import underwater_hockey
ADAPTERS['underwater_hockey'] = underwater_hockey
from .adapters import polo
ADAPTERS['polo'] = polo
from .adapters import water_polo
ADAPTERS['water_polo'] = water_polo
from .adapters import american_football
ADAPTERS['american_football'] = american_football
from .adapters import kho_kho
ADAPTERS['kho_kho'] = kho_kho
from .adapters import ice_hockey
ADAPTERS['ice_hockey'] = ice_hockey
