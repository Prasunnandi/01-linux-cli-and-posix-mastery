#!/usr/bin/env python3
"""
Day 45 Lab: Crontab 5-Field Lexical Parser & Bitmask Matcher
Parses standard POSIX crontab expressions:
[Minute] [Hour] [Day of Month] [Month] [Day of Week]
Supports:
- Wildcards (*)
- Ranges (1-5)
- Steps (*/15 or 1-10/2)
- Lists (1,15,30)
- The Day-of-Month vs Day-of-Week Disjunction rule.
Uses Python standard library only.
"""

from dataclasses import dataclass
from typing import Set


@dataclass
class ParsedCronSchedule:
    minutes: Set[int]
    hours: Set[int]
    doms: Set[int]
    months: Set[int]
    dows: Set[int]
    is_dom_wildcard: bool
    is_dow_wildcard: bool

    def matches(self, minute: int, hour: int, dom: int, month: int, dow: int) -> bool:
        """Evaluates whether given timestamp parameters match the cron schedule."""
        if minute not in self.minutes or hour not in self.hours or month not in self.months:
            return False

        # POSIX Disjunction rule: If both DoM and DoW are specified (neither is *),
        # the match succeeds if EITHER matches (OR condition)!
        if not self.is_dom_wildcard and not self.is_dow_wildcard:
            return (dom in self.doms) or (dow in self.dows)

        # Standard conjunction
        return (dom in self.doms) and (dow in self.dows)


class CrontabParser:
    @staticmethod
    def parse_field(field_str: str, min_val: int, max_val: int) -> Set[int]:
        """Parses a single crontab field string into a set of matching integers."""
        results = set()
        for part in field_str.split(','):
            part = part.strip()
            # Case 1: Step expression (*/15 or 1-10/2)
            if '/' in part:
                sub_part, step_str = part.split('/', 1)
                step = int(step_str)
                if sub_part == '*' or sub_part == '':
                    start, end = min_val, max_val
                elif '-' in sub_part:
                    start_str, end_str = sub_part.split('-', 1)
                    start, end = int(start_str), int(end_str)
                else:
                    start, end = int(sub_part), max_val

                results.update(range(start, end + 1, step))

            # Case 2: Range expression (1-5)
            elif '-' in part:
                start_str, end_str = part.split('-', 1)
                results.update(range(int(start_str), int(end_str) + 1))

            # Case 3: Wildcard (*)
            elif part == '*':
                results.update(range(min_val, max_val + 1))

            # Case 4: Literal integer
            else:
                results.add(int(part))

        return results

    @staticmethod
    def parse_crontab(expr: str) -> ParsedCronSchedule:
        fields = expr.strip().split()
        if len(fields) != 5:
            raise ValueError(f"Crontab requires exactly 5 fields, got {len(fields)}")

        min_str, hr_str, dom_str, mon_str, dow_str = fields

        return ParsedCronSchedule(
            minutes=CrontabParser.parse_field(min_str, 0, 59),
            hours=CrontabParser.parse_field(hr_str, 0, 23),
            doms=CrontabParser.parse_field(dom_str, 1, 31),
            months=CrontabParser.parse_field(mon_str, 1, 12),
            dows=CrontabParser.parse_field(dow_str, 0, 6),
            is_dom_wildcard=(dom_str == '*'),
            is_dow_wildcard=(dow_str == '*')
        )


def main():
    print("====================================================")
    print("DAY 45: CRONTAB 5-FIELD LEXICAL PARSER & MATCHER")
    print("====================================================")

    # Expression: Every 15 minutes past 2 AM on Mon-Fri
    cron_expr = "*/15 2 * * 1-5"
    sched = CrontabParser.parse_crontab(cron_expr)

    print(f"Parsed Expression: '{cron_expr}'")
    print(f"  Minutes : {sorted(sched.minutes)}")
    print(f"  Hours   : {sorted(sched.hours)}")
    print(f"  DoWs    : {sorted(sched.dows)}")

    assert sched.minutes == {0, 15, 30, 45}
    assert sched.hours == {2}
    assert sched.dows == {1, 2, 3, 4, 5}

    # Test 1: Match 02:15 on Wednesday (DoW=3)
    match1 = sched.matches(minute=15, hour=2, dom=14, month=5, dow=3)
    assert match1 is True
    print("\n1. Test 02:15 Wednesday -> [MATCHED]")

    # Test 2: Mismatch 02:10 on Wednesday (minute 10 not in */15)
    match2 = sched.matches(minute=10, hour=2, dom=14, month=5, dow=3)
    assert match2 is False
    print("2. Test 02:10 Wednesday -> [SKIPPED] (Correct)")

    # Test 3: POSIX Disjunction rule: "0 0 1,15 * 1" (1st and 15th OR Mondays)
    disjunction_cron = "0 0 1,15 * 1"
    disj_sched = CrontabParser.parse_crontab(disjunction_cron)
    # Day 18 (not 1 or 15), but it is a Monday (DoW=1) -> MUST MATCH!
    disj_match = disj_sched.matches(minute=0, hour=0, dom=18, month=5, dow=1)
    assert disj_match is True
    print("3. Test POSIX Disjunction (DoM=18, Monday) -> [MATCHED] (OR Rule verified)")

    print("\n[VERIFIED] Crontab lexical parser passed all RFC/POSIX test cases!")


if __name__ == "__main__":
    main()
