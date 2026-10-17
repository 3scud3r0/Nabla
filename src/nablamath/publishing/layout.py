"""Typed presentation of exact results and bounded previews for print."""
from fractions import Fraction
import math
import re


def display_value(value):
    if type(value) is int or (type(value) is str and re.fullmatch(r'[+-]?\d+(?:/\d+)?',value)):
        try:
            rational = Fraction(value)
        except (ValueError,ZeroDivisionError):
            pass
        else:
            if max(len(str(rational.numerator)),len(str(rational.denominator))) <= 24:
                return {'kind':'exact','numerator':str(rational.numerator),'denominator':str(rational.denominator)}
    if type(value) is float and math.isfinite(value):
        return {'kind':'approximate','text':format(value,'.10g')}
    if isinstance(value,list) and value and len(value) <= 6:
        parts = [display_value(v) for v in value]
        if all(part['kind'] in {'exact','approximate'} for part in parts):
            return {'kind':'vector','items':parts}
        if all(isinstance(row,list) and 1 <= len(row) <= 4 for row in value) and len(value) <= 4 and len({len(row) for row in value}) == 1:
            rows = [[display_value(v) for v in row] for row in value]
            widths = [max(len(part.get('text',part.get('numerator',''))),len(part.get('denominator',''))) for row in rows for part in row]
            if all(part['kind'] in {'exact','approximate'} for row in rows for part in row) and max(widths,default=0)*len(rows[0])+2*(len(rows[0])-1)<=30:
                return {'kind':'matrix','rows':rows}
    if isinstance(value,list):
        return {'kind':'text','text':f'{len(value)} entries; complete values in the experiment bundle'}
    if isinstance(value,dict):
        names = ', '.join(str(k) for k in list(value)[:5])
        return {'kind':'text','text':f'{len(value)} fields: {names}; complete object in the experiment bundle'}
    text = str(value)
    text = text if len(text)<=256 else text[:240]+'… [complete value in bundle]'
    text = re.sub(r'[^\s]{32,}',lambda match:'\u200b'.join(match[0][i:i+20] for i in range(0,len(match[0]),20)),text)
    return {'kind':'text','text':text}
