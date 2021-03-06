from operator import itemgetter
import os
import warnings

from .filters import (
    MSCompare,
    MSHasValue,
    MSNoRules,
    MSNot,
    MSRawFilter,
    MSStrCompare,
)
from .instructions import _MS, SY, LC, LS, CS, AC, AP, TE
from .lookup import Lookup, LookupCollection


class NotImplementedWarning(UserWarning):
    pass


def lookups_from_cs(detail, lookup_type, name):

    function_name = detail[:6]
    function = globals().get(function_name)

    if function:
        lookups = function(lookup_type, name)
    else:
        warnings.warn('Symproc not implemented: {}'.format(function_name),
                      NotImplementedWarning)

        # Return default lookup; leave CS as is, maybe CS in instruction.py can
        # make something useful
        lookups = [{
            'instruction': CS(detail),
            'rules': MSNoRules(),
        }]

    return LookupCollection(lookups, id='-CS({})'.format(detail))


def DATCVR(lookup_type, name):
    return [{
        'instruction': LC('HODATA01'),
        'rules': MSNoRules(),
    }]


def DEPARE(lookup_type, name):

    # These values are normally passed by the mariner
    safety_contour = 10
    shallow_contour = 20
    deep_contour = 30

    # Basic implementation of DEPARE constructed symbol.
    # We are missing all the line and fill symbology
    rules = LookupCollection([
        Lookup(
            rules=MSCompare('DRVAL1', deep_contour, MSCompare.OP.GE),
            instruction=AC('DEPDW')
        ),
        Lookup(
            rules=MSCompare('DRVAL1', safety_contour, MSCompare.OP.GE),
            instruction=AC('DEPMD')
        ),
        Lookup(  # unused until safety_contour is configurable
            rules=MSCompare('DRVAL1', shallow_contour, MSCompare.OP.GE),
            instruction=AC('DEPMS')
        ),
        Lookup(
            instruction=AC('DEPIT'),
            rules=~MSHasValue('DRVAL1')
        ),
        Lookup(
            # Should be GE, but null == 0 and needs to use DEPIT
            rules=MSCompare('DRVAL1', '0', MSCompare.OP.GE),
            instruction=AC('DEPVS')
        ),
        Lookup(
            instruction=AC('DEPIT')
        ),
    ])

    if name == 'DRGARE':
        rules = rules @ Lookup(
            id='-DRGARE',
            instruction=AP('DRGARE01') + LS('DASH', 1, 'CHGRF'),
        )

    return rules


def DEPCNT(lookup_type, name):
    return [{
        'rules': (
            MSCompare('QUAPOS', '1', MSCompare.OP.GT)
            & MSCompare('QUAPOS', '10', MSCompare.OP.LT)
        ),
        'instruction': LS('DASH', 1, 'DEPCN'),
    }, {
        'rules': MSNoRules(),
        'instruction': LS('SOLD', 1, 'DEPCN'),
    }]


def LEGLIN(lookup_type, name):
    plnspd = TE("'%d kt'", 'plnspd', 3, 2, 2, '15110', 0, 0, 'CHBLK', 50)

    return [{
        'rules': MSCompare('select', '1') & MSHasValue('plnspd'),
        'instruction': [LC('PLNRTE03'), SY('PLNSPD03'), plnspd],
    }, {
        'rules': MSCompare('select', '1'),
        'instruction': LC('PLNRTE03'),
    }, {
        'rules': MSHasValue('plnspd'),
        'instruction': [LS('DOTT', 2, 'APLRT'), SY('PLNSPD04'), plnspd],
    }, {
        'rules': MSNoRules(),
        'instruction': LS('DOTT', 2, 'APLRT'),
    }]


def LIGHTS(lookup_type, name):
    def LIGHTS(num):
        return _MS('''
        STYLE
            SYMBOL 'LIGHTS{}'
            OFFSET 9 9
        END'''.format(num))

    return [{
        'instruction': SY('LIGHTS82'),
        'rules': MSCompare('CATLIT', '11') | MSCompare('CATLIT', '8'),
    }, {
        'instruction': SY('LIGHTS81'),
        'rules': MSCompare('CATLIT', '9'),
    }, {
        'instruction': SY('LIGHTS81'),
        'rules': (
            (MSCompare('CATLIT', '1') | MSCompare('CATLIT', '16'))
            & MSCompare('ORIENT', 'null')
        ),
    }, {
        'instruction': SY('LIGHTS81'),
        'rules': MSCompare('CATLIT', '1') | MSCompare('CATLIT', '16'),
    }, {
        'instruction': [],
        'rules': (
            MSCompare('VALNMR', '10', MSCompare.OP.LT)
            & MSRawFilter('NOT ("[CATLIT]" ~ "5" OR "[CATLIT]" ~ "6")')
            & MSCompare('LITCHR', '12', MSCompare.OP.NE)
        ),
    }, {
        # TODO: Figure out why a simple SY instruction ends up with a bad
        # offset
        'instruction': LIGHTS(11),
        'rules': MSCompare('COLOUR', '3,1') | MSCompare('COLOUR', '3'),
    }, {
        'instruction': LIGHTS(12),
        'rules': MSCompare('COLOUR', '4,1') | MSCompare('COLOUR', '4')
    }, {
        'instruction': LIGHTS(13),
        'rules': (
            MSCompare('COLOUR', '11')
            | MSCompare('COLOUR', '6')
            | MSCompare('COLOUR', '1')
        ),
    }] + (
        Lookup(
            rules=MSNot(MSHasValue('SECTR1') | MSHasValue('SECTR2'))
        ) @ (
            (Lookup(
                rules=MSCompare('VALNMR', '10', MSCompare.OP.LT),
                id='-flare',
            ) @ LookupCollection([
                Lookup(
                    id='-red',
                    rules=MSStrCompare.includes('COLOUR', 3),
                    instruction=LIGHTS(11)
                ),
                Lookup(
                    id='-green',
                    rules=MSStrCompare.includes('COLOUR', 4),
                    instruction=LIGHTS(12)
                ),
                Lookup(
                    id='-yellow',
                    rules=MSStrCompare.includes('COLOUR', 1, 6, 11),
                    instruction=LIGHTS(13)
                ),
            ])) + LookupCollection([
                Lookup(
                    id='-red',
                    rules=MSStrCompare.includes('COLOUR', 3),
                    instruction=SY('LIGHTS96')
                ),
                Lookup(
                    id='-green',
                    rules=MSStrCompare.includes('COLOUR', 4),
                    instruction=SY('LIGHTS95')
                ),
                Lookup(
                    id='-yellow',
                    rules=MSStrCompare.includes('COLOUR', 1, 6, 11),
                    instruction=SY('LIGHTS91')
                ),
                Lookup(
                    id='-magenta',
                    instruction=SY('LIGHTS90')
                ),
            ])
        )
    )


def OBSTRN(lookup_type, name):
    if lookup_type == 'Point':
        return OBSTRN_point(name)

    if lookup_type == 'Line':
        return OBSTRN_line(name)

    return OBSTRN_area(name)


def OBSTRN_area(name):
    return [{
        'rules': MSCompare('VALSOU', '30', MSCompare.OP.GT),
        'instruction': LS('DASH', 2, 'CHGRD')
    }, {
        'rules': MSHasValue('VALSOU'),
        'instruction': LS('DOTT', 2, 'CHBLK')
    }, {
        'rules': MSCompare('CATOBS', '6'),
        'instruction': [AP('FOULAR01'), LS('DOTT', 2, 'CHBLK')]
    }, {
        'rules': MSCompare('WATLEV', '1') | MSCompare('WATLEV', '2'),
        'instruction': [AC('CHBRN'), LS('SOLD', 2, 'CSTLN')]
    }, {
        'rules': MSCompare('WATLEV', '4'),
        'instruction': [AC('DEPIT'), LS('DASH', 2, 'CSTLN')]
    }, {
        'rules': MSNoRules(),
        'instruction': [AC('DEPVS'), LS('DOTT', 2, 'CHBLK')]
    }]


def OBSTRN_line(name):
    return [{
        'rules': MSCompare('VALSOU', '30', MSCompare.OP.GT),
        'instruction': LS('DASH', 2, 'CHBLK')
    }, {
        # VALSOU missing and <= SAFETY_DEPTH both lead here
        'rules': MSNoRules(),
        'instruction': LS('DOTT', 2, 'CHBLK')
    }]


def OBSTRN_point(name):
    common_rule = [{
        'rules': MSCompare('VALSOU', '30', MSCompare.OP.GT),
        'instruction': SY('DANGER02')
    }]

    if name == 'UWTROC':
        return common_rule + [{
            'rules': (
                MSHasValue('VALSOU')
                & (MSCompare('WATLEV', '4') | MSCompare('WATLEV', '5'))
            ),
            'instruction': SY('UWTROC04')
        }, {
            'rules': MSHasValue('VALSOU'),
            'instruction': SY('DANGER01')
        }, {
            'rules': MSCompare('WATLEV', '3'),
            'instruction': SY('UWTROC03')
        }, {
            'rules': MSNoRules(),
            'instruction': SY('UWTROC04')
        }]

    else:
        return common_rule + [{
            'rules': MSHasValue('VALSOU') & MSCompare('CATOBS', '6'),
            'instruction': SY('DANGER01')
        }, {
            'rules': (
                MSHasValue('VALSOU')
                & (MSCompare('WATLEV', '1') | MSCompare('WATLEV', '2'))
            ),
            'instruction': SY('OBSTRN11')
        }, {
            'rules': (
                MSHasValue('VALSOU')
                & (MSCompare('WATLEV', '4') | MSCompare('WATLEV', '5'))
            ),
            'instruction': SY('DANGER03')
        }, {
            'rules': MSHasValue('VALSOU'),
            'instruction': SY('DANGER01')
        }, {
            'rules': MSCompare('CATOBS', '6'),
            'instruction': SY('OBSTRN01')
        }, {
            'rules': MSCompare('WATLEV', '1') | MSCompare('WATLEV', '2'),
            'instruction': SY('OBSTRN11')
        }, {
            'rules': MSCompare('WATLEV', '4') | MSCompare('WATLEV', '5'),
            'instruction': SY('OBSTRN03')
        }, {
            'rules': MSNoRules(),
            'instruction': SY('OBSTRN01')
        }]


def OWNSHP(lookuptype, name):
    return [{
        'rules': MSNoRules(),
        'instruction': SY('OWNSHP01')
    }]


def QUALIN(lookuptype, name):
    common_rule = [{
        'instruction': LC('LOWACC21'),
        'rules': (
            # QUAPOS only has values 1 to 11. QUAPOS not in 1, 10, 11 is
            # equivalent to the below rules
            MSCompare('QUAPOS', '1', MSCompare.OP.GT)
            & MSCompare('QUAPOS', '10', MSCompare.OP.LT)
        )
    }]

    if name == 'COALNE':
        return common_rule + [{
            'instruction': LS('SOLD', 1, 'CSTLN'),
            'rules': MSNoRules()
        }]
    else:
        return common_rule + [{
            'instruction': [LS('SOLD', 3, 'CHMGF'), LS('SOLD', 1, 'CSTLN')],
            'rules': MSCompare('CONRAD', '1')
        }, {
            # CONRAD missing and CONRAD != 1 both lead here
            'instruction': LS('SOLD', 1, 'CSTLN'),
            'rules': MSNoRules()
        }]


def QUAPNT(lookup_type, name):
    return [{
        'instruction': SY('LOWACC01'),
        'rules': (
            MSCompare('QUAPOS', '1', MSCompare.OP.GT)
            & MSCompare('QUAPOS', '10', MSCompare.OP.LT)
        )
    }]


def QUAPOS(lookup_type, name):
    if lookup_type == 'Point':
        return QUAPNT(lookup_type, name)
    else:
        return QUALIN(lookup_type, name)


def RESARE(lookup_type, name):
    includes = MSStrCompare.includes
    return (
        Lookup(
            id='-CS(RESARE)',
            rules=includes('RESTRN', 7, 8, 14)
        ) @ RESARE_continuation_A()
        + Lookup(
            id='-CS(RESARE)',
            rules=includes('RESTRN', 1, 2)
        ) @ RESARE_continuation_B()
        + Lookup(
            id='-CS(RESARE)',
            rules=includes('RESTRN', 3, 4, 5, 6, 24)
        ) @ RESARE_continuation_C()
        + Lookup(
            id='-CS(RESARE)',
            rules=includes('RESTRN', 13, 16, 17, 23, 25, 26, 27)
        ) @ RESARE_continuation_D()
        + Lookup(
            id='-CS(RESARE)',
            rules=MSHasValue('RESTRN')
        ) @ RESARE_no_continuation()
        + Lookup(
            id='-CS(RESARE)'
        ) @ RESARE_continuation_E()
    )


def RESARE_no_continuation():
    return LookupCollection([
        Lookup(
            rules=MSStrCompare.includes('RESTRN',
                                        9, 10, 11, 12, 15, 18, 19, 20, 21, 22),
            instruction=SY('INFARE51')
        ),
        Lookup(
            rules=MSNoRules(),
            instruction=SY('RSRDEF51')
        )
    ]) @ LookupCollection([
        Lookup(instruction=LS('DASH', 2, 'CHMGD'), table='Plain'),
        Lookup(instruction=LC('CTYARE51'), table='Symbolized')
    ])


def RESARE_continuation_A():
    includes = MSStrCompare.includes
    return LookupCollection([
        Lookup(
            rules=(
                includes('RESTRN',
                         1, 2, 3, 4, 5, 6, 13, 16, 17, 23, 24, 25, 26, 27)
                | includes('CATREA', 1, 8, 9, 12, 14, 18, 19, 21, 24, 25, 26)
            ),
            instruction=SY('ENTRES61')
        ),
        Lookup(
            rules=(
                includes('RESTRN', 9, 10, 11, 12, 15, 18, 19, 20, 21, 22)
                | includes('CATREA', 4, 5, 6, 7, 10, 20, 22, 23)
            ),
            instruction=SY('ENTRES71')
        ),
        Lookup(instruction=SY('ENTRES51'))
    ]) @ LookupCollection([
        Lookup(instruction=LS('DASH', 2, 'CHMGD'), table='Plain', id='PLAIN'),
        Lookup(instruction=LC('ENTRES51'), table='Symbolized', id='SYM')
    ])


def RESARE_continuation_B():
    includes = MSStrCompare.includes
    return LookupCollection([
        Lookup(
            rules=(
                includes('RESTRN', 3, 4, 5, 6, 13, 16, 17, 23, 24, 25, 26, 27)
                | includes('CATREA', 1, 8, 9, 12, 14, 18, 19, 21, 24, 25, 26)
            ),
            instruction=SY('ACHRES61')
        ),
        Lookup(
            rules=(
                includes('RESTRN', 9, 10, 11, 12, 15, 18, 19, 20, 21, 22)
                | includes('CATREA', 4, 5, 6, 7, 10, 20, 22, 23)
            ),
            instruction=SY('ACHRES71')
        ),
        Lookup(instruction=SY('ACHRES51'))
    ]) @ LookupCollection([
        Lookup(instruction=LS('DASH', 2, 'CHMGD'), table='Plain'),
        Lookup(instruction=LC('ACHRES51'), table='Symbolized')
    ])


def RESARE_continuation_C():
    includes = MSStrCompare.includes
    return LookupCollection([
        Lookup(
            rules=(
                includes('RESTRN', 13, 16, 17, 23, 24, 25, 26, 27)
                | includes('CATREA', 1, 8, 9, 12, 14, 18, 19, 21, 24, 25, 26)
            ),
            instruction=SY('FSHRES61')
        ),
        Lookup(
            rules=(
                includes('RESTRN', 9, 10, 11, 12, 15, 18, 19, 20, 21, 22)
                | includes('CATREA', 4, 5, 6, 7, 10, 20, 22, 23)
            ),
            instruction=SY('FSHRES71')
        ),
        Lookup(instruction=SY('FSHRES51'))
    ]) @ LookupCollection([
        Lookup(instruction=LS('DASH', 2, 'CHMGD'), table='Plain'),
        Lookup(instruction=LC('FSHRES51'), table='Symbolized')
    ])


def RESARE_continuation_D():
    includes = MSStrCompare.includes
    return LookupCollection([
        Lookup(
            rules=(
                includes('RESTRN', 9, 10, 11, 12, 15, 18, 19, 20, 21, 22)
                | includes('CATREA', 4, 5, 6, 7, 10, 20, 22, 23)
            ),
            instruction=SY('CTYARE71')
        ),
        Lookup(instruction=SY('CTYARE51'))
    ]) @ LookupCollection([
        Lookup(instruction=LS('DASH', 2, 'CHMGD'), table='Plain'),
        Lookup(instruction=LC('CTYARE51'), table='Symbolized')
    ])


def RESARE_continuation_E():
    rule_a = MSStrCompare.includes('CATREA',
                                   1, 8, 9, 12, 14, 18, 19, 21, 24, 25, 26)
    rule_b = MSStrCompare.includes('CATREA', 4, 5, 6, 7, 10, 20, 22, 23)

    return LookupCollection([
        Lookup(
            rules=rule_a & rule_b,
            instruction=SY('CTYARE71')
        ),
        Lookup(
            rules=rule_a,
            instruction=SY('CTYARE51')
        ),
        Lookup(
            rules=MSHasValue('CATREA') & rule_b,
            instruction=SY('INFARE51')
        ),
        Lookup(
            instruction=SY('RSRDEF51')
        )
    ]) @ LookupCollection([
        Lookup(instruction=LS('DASH', 2, 'CHMGD'), table='Plain'),
        Lookup(instruction=LC('CTYARE51'), table='Symbolized')
    ])


def RESTRN(lookup_type, name):
    includes = MSStrCompare.includes

    return [{
        'rules': (
            includes('RESTRN', 7, 8, 14)
            & includes('RESTRN', 1, 2, 3, 4, 5, 13, 16, 17, 23, 24, 25, 26, 27)
        ),
        'instruction': SY('ENTRES61'),
    }, {
        'rules': (
            includes('RESTRN', 7, 8, 14)
            & includes('RESTRN', 9, 10, 11, 12, 15, 18, 19, 20, 21, 22)
        ),
        'instruction': SY('ENTRES71'),
    }, {
        'rules': includes('RESTRN', 7, 8, 14),
        'instruction': SY('ENTRES51'),
    }, {
        'rules': (
            includes('RESTRN', 1, 2)
            & includes('RESTRN', 3, 4, 5, 6, 13, 16, 17, 23, 24, 25, 26, 27)
        ),
        'instruction': SY('ACHRES61'),
    }, {
        'rules': (
            includes('RESTRN', 1, 2)
            & includes('RESTRN', 9, 10, 11, 12, 15, 18, 19, 20, 21, 22)
        ),
        'instruction': SY('ACHRES71'),
    }, {
        'rules': includes('RESTRN', 1, 2),
        'instruction': SY('ACHRES51'),
    }, {
        'rules': (
            includes('RESTRN', 3, 4, 5, 6, 24)
            & includes('RESTRN', 13, 16, 17, 23, 25, 26, 27)
        ),
        'instruction': SY('FHSRES61')
    }, {
        'rules': (
            includes('RESTRN', 3, 4, 5, 6, 24)
            & includes('RESTRN', 9, 10, 11, 12, 15, 18, 19, 20, 21, 22)
        ),
        'instruction': SY('FHSRES71'),
    }, {
        'rules': includes('RESTRN', 3, 4, 5, 6, 24),
        'instruction': SY('FHSRES51'),
    }, {
        'rules': (
            includes('RESTRN', 13, 16, 17, 23, 25, 26, 27)
            & includes('RESTRN', 9, 10, 11, 12, 15, 18, 19, 20, 21, 22)
        ),
        'instruction': SY('CTYARE71'),
    }, {
        'rules': includes('RESTRN', 13, 16, 17, 23, 25, 26, 27),
        'instruction': SY('CTYARE51'),
    }, {
        'rules': includes('RESTRN', 9, 10, 11, 12, 15, 18, 19, 20, 21, 22),
        'instruction': SY('INFARE51'),
    }, {
        'rules': MSNoRules(),
        'instruction': SY('RSRDEF51'),
    }]


def SLCONS(lookup_type, name):
    return [{
        'instruction': SY('LOWACC01'),
        'rules': (
            # QUAPOS only has values 1 to 11. QUAPOS not in 1, 10, 11 is
            # equivalent to the below rules
            MSCompare('QUAPOS', '1', MSCompare.OP.GT)
            & MSCompare('QUAPOS', '10', MSCompare.OP.LT)
        )
    }, {
        'instruction': LC('LOWACC21'),
        'rules': (
            # QUAPOS only has values 1 to 11. QUAPOS not in 1, 10, 11 is
            # equivalent to the below rules
            MSCompare('QUAPOS', '1', MSCompare.OP.GT)
            & MSCompare('QUAPOS', '10', MSCompare.OP.LT)
        )
    }, {
        'instruction': LS('DASH', 1, 'CSTLN'),
        'rules': MSCompare('CONDTN', '1') | MSCompare('CONDTN', '2')
    }, {
        'instruction': LS('SOLD', 4, 'CSTLN'),
        'rules': (
            MSCompare('CATSLC', '6')
            | MSCompare('CATSLC', '15')
            | MSCompare('CATSLC', '16')
        )
    }, {
        'instruction': LS('DASH', 2, 'CSTLN'),
        'rules': MSCompare('WATLEV', '3') | MSCompare('WATLEV', '4')
    }, {
        'instruction': LS('SOLD', 2, 'CSTLN'),
        'rules': MSNoRules()
    }]


def SOUNDG(lookup_type, name):
    safety_depth = 30
    label_template = '''
        LABEL
            TEXT (round([DEPTH]+(-0.5),1))
            TYPE TRUETYPE
            FONT sc
            COLOR {{color[{colour}].rgb}}
            # COLOR 136 152 139
            SIZE 8
            ANTIALIAS TRUE
            FORCE TRUE
        END

        LABEL
            EXPRESSION ([DEPTH] > 10 AND [DEPTH] < 31 AND ([DEPTH] * 10 % 10))
            TEXT ( [DEPTH] * 10 % 10)
            OFFSET 8 4
            TYPE TRUETYPE
            FONT sc
            COLOR {{color[{colour}].rgb}}
            # COLOR 136 152 139
            SIZE 7
            ANTIALIAS TRUE
            FORCE TRUE
        END

        LABEL
            EXPRESSION ([DEPTH] < 10 AND ([DEPTH] * 10 % 10))
            TEXT ( [DEPTH] * 10 % 10)
            OFFSET 5 4
            TYPE TRUETYPE
            FONT sc
            COLOR {{color[{colour}].rgb}}
            # COLOR 136 152 139
            SIZE 6
            ANTIALIAS TRUE
            FORCE TRUE
        END
    '''

    return [{
        'instruction': _MS(label_template.format(colour='CHGRD')),
        'rules': MSCompare('DEPTH', safety_depth, MSCompare.OP.LE)
    }, {
        'instruction': _MS(label_template.format(colour='CHGRF')),
    }]


def SYMINS(lookup_type, name):
    instructions = {
        'Point': SY('NEWOBJ01'),
        'Line': LC('NEWOBJ01'),
        'Area': [SY('NEWOBJ01'), LS('DASH', 2, 'CHMGD')],
    }

    return [{
        'rules': MSNoRules(),
        'instruction': instructions[lookup_type],
    }]


topshp_to_sy = [
    # (topshp, floating, rigid),
    ('1', 'TOPMAR02', 'TOPMAR22'),
    ('2', 'TOPMAR04', 'TOPMAR24'),
    ('3', 'TOPMAR10', 'TOPMAR30'),
    ('4', 'TOPMAR12', 'TOPMAR32'),
    ('5', 'TOPMAR13', 'TOPMAR33'),
    ('6', 'TOPMAR14', 'TOPMAR34'),
    ('7', 'TOPMAR65', 'TOPMAR85'),
    ('8', 'TOPMAR17', 'TOPMAR86'),
    ('9', 'TOPMAR16', 'TOPMAR36'),
    ('10', 'TOPMAR08', 'TOPMAR28'),
    ('11', 'TOPMAR07', 'TOPMAR27'),
    ('12', 'TOPMAR14', 'TOPMAR14'),
    ('13', 'TOPMAR05', 'TOPMAR25'),
    ('14', 'TOPMAR06', 'TOPMAR26'),
    ('15', 'TMARDEF2', 'TOPMAR88'),
    ('16', 'TMARDEF2', 'TOPMAR87'),
    ('17', 'TMARDEF2', 'TMARDEF1'),
    ('18', 'TOPMAR10', 'TOPMAR30'),
    ('19', 'TOPMAR13', 'TOPMAR33'),
    ('20', 'TOPMAR14', 'TOPMAR34'),
    ('21', 'TOPMAR13', 'TOPMAR33'),
    ('22', 'TOPMAR14', 'TOPMAR34'),
    ('23', 'TOPMAR14', 'TOPMAR34'),
    ('24', 'TOPMAR02', 'TOPMAR22'),
    ('25', 'TOPMAR04', 'TOPMAR24'),
    ('26', 'TOPMAR10', 'TOPMAR30'),
    ('27', 'TOPMAR17', 'TOPMAR86'),
    ('28', 'TOPMAR18', 'TOPMAR89'),
    ('29', 'TOPMAR02', 'TOPMAR22'),
    ('30', 'TOPMAR17', 'TOPMAR86'),
    ('31', 'TOPMAR14', 'TOPMAR14'),
    ('32', 'TOPMAR10', 'TOPMAR30'),
    ('33', 'TMARDEF2', 'TMARDEF1'),
]


def TOPMAR(lookup_type, name):
    if os.environ.get('TOPMAR_FLOAT'):
        sy_getter = itemgetter(0)
    else:
        sy_getter = itemgetter(1)

    return [{
        'instruction': SY(sy),
        'rules': MSCompare('TOPSHP', shp)
    }
        for shp, floating, rigid in topshp_to_sy
        for sy in [sy_getter([floating, rigid])]
    ] + [{
        'instruction': SY(sy_getter(('TMARDEF2', 'TMARDEF1'))),
        'rules': MSHasValue('TOPSHP')
    }, {
        'instruction': SY('QUESMRK1'),
        'rules': MSNoRules(),
    }]


def WRECKS(lookup_type, name):
    if lookup_type == 'Point':
        return WRECKS_Point(lookup_type, name)
    else:
        return WRECKS_other(lookup_type, name)


def WRECKS_other(lookup_type, name):
    # TODO: add rules for background
    return [{
        'rules': (
            MSCompare('QUAPOS', '1', MSCompare.OP.GT)
            & MSCompare('QUAPOS', '10', MSCompare.OP.LT)
        ),
        'instruction': LC('LOWACC41')
    }, {
        'rules': MSCompare('VALSOU', '30', MSCompare.OP.GT),
        'instruction': LS('DASH', 2, 'CHBLK')
    }, {
        'rules': MSHasValue('VALSOU'),
        'instruction': LS('DOTT', 2, 'CHBLK')
    }, {
        'rules': MSCompare('WATLEV', '1') | MSCompare('WATLEV', '2'),
        'instruction': [LS('SOLD', 2, 'CSTLN'), AC('CHBRN')]
    }, {
        'rules': MSCompare('WATLEV', '4'),
        'instruction': [LS('DASH', 2, 'CSTLN'), AC('DEPIT')]
    }, {
        'rules': MSCompare('WATLEV', '3') | MSCompare('WATLEV', '5'),
        'instruction': [LS('DOTT', 2, 'CSTLN'), AC('DEPVS')]
    }, {
        'rules': MSNoRules(),
        'instruction': [LS('DOTT', 2, 'CSTLN'), AC('DEPVS')]
    }]


def WRECKS_Point(lookup_type, name):
    return [{
        'rules': MSCompare('VALSOU', '30', MSCompare.OP.GT),
        'instruction': SY('DANGER02')
        + TE('Wk', '', 2, 1, 2, '15110', 1, 0, 'CHBLK', 21)
    }, {
        'rules': MSHasValue('VALSOU'),
        'instruction': SY('DANGER01')
        + TE('Wk', '', 2, 1, 2, '15110', 1, 0, 'CHBLK', 21)
    }, {
        'rules': MSCompare('CATWRK', '1') & MSCompare('WATLEV', '3'),
        'instruction': SY('WRECKS04')
    }, {
        'rules': MSCompare('CATWRK', '2') & MSCompare('WATLEV', '3'),
        'instruction': SY('WRECKS05')
    }, {
        'rules': (
            MSCompare('CATWRK', '4')
            | MSCompare('CATWRK', '5')
            | MSCompare('WATLEV', '1')
            | MSCompare('WATLEV', '2')
            | MSCompare('WATLEV', '3')
            | MSCompare('WATLEV', '4')
        ),
        'instruction': SY('WRECKS01')
    }, {
        'rules': MSNoRules(),
        'instruction': SY('WRECKS05')
    }]


def no_symbology(lookup_type, name):
    "Generic function for CS with no symbology"
    return []


CLRLIN = VRMEBL = PASTRK = VESSEL = no_symbology
