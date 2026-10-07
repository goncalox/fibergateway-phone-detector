"""Control validation and transactional behavior using synthetic router output."""
import asyncio
import importlib
import pathlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

PACKAGE = 'control_test_core'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(pathlib.Path(__file__).resolve().parents[1] / 'custom_components/wifi_phone_detector')]
sys.modules[PACKAGE] = package
commands = importlib.import_module(f'{PACKAGE}.commands')
router = importlib.import_module(f'{PACKAGE}.router')
parser = importlib.import_module(f'{PACKAGE}.parser')
MAC = '02:11:22:33:44:55'
RULE = commands.restriction('Weekday-Night', MAC, ['Mon','Tue','Wed','Thu','Fri'], '00:00', '05:00')
EMPTY = 'Nothing found. Try again.'


def table(*rules):
    return '|Name | MAC address | Days of week | Start Time | End Time |\n' + '\n'.join(
        f'|{r.name}|{r.mac}|{",".join(r.days)}|{r.start_time}|{r.end_time}|' for r in rules)


class ValidationTests(unittest.TestCase):
    def test_rejects_multicast_broadcast_and_zero_mac(self):
        for mac in ('ff:ff:ff:ff:ff:ff', '01:00:5e:00:00:01', '00:00:00:00:00:00'):
            with self.assertRaises(ValueError): commands.device_mac(mac)

    def test_rejects_rule_name_injection(self):
        for name in ('', 'Other --days-week=Sun', 'a\n/management/reboot', 'a;quit', 'a'*65):
            with self.assertRaises(ValueError): commands.rule_name(name)

    def test_times_require_minutes_and_valid_clock_values(self):
        for time in ('24:00','5:00','05:60','05:00:01','00:00\nquit'):
            with self.assertRaises(ValueError): commands.clock_time(time)
        self.assertEqual(commands.clock_time('05:00:00'), '05:00')

    def test_equal_times_are_not_assumed_to_mean_all_day(self):
        with self.assertRaises(ValueError): commands.restriction('Night', MAC, ['Mon'], '00:00','00:00')

    def test_day_selection_canonicalizes_without_adding_weekends(self):
        self.assertEqual(commands.weekdays(['Fri','Mon','Fri']), ('Mon','Fri'))
        for days in ([], ['Monday'], ['Mon','unknown'], 'Mon,Tue'):
            with self.assertRaises(ValueError): commands.weekdays(days)

    def test_multiline_and_control_char_commands_are_rejected(self):
        for text in ('', ' ', 'show\n/management/reboot', 'show\rquit', 'help\x1b[A'):
            with self.assertRaises(ValueError): commands.validate_command(text)

    def test_valid_table_and_empty_responses(self):
        self.assertEqual(commands.parse_time_restrictions(table(RULE)), (RULE,))
        self.assertEqual(commands.parse_time_restrictions(EMPTY), ())

    def test_unknown_or_duplicate_rules_do_not_mean_empty(self):
        for text in ('', '/cli>', 'Unknown command', table(RULE,RULE), table(RULE).replace('05:00','25:00')):
            with self.assertRaises(parser.ParseError): commands.parse_time_restrictions(text)


class Reader:
    def __init__(self, responses): self.responses=iter(responses)
    async def read(self, size):
        value=next(self.responses,'')
        if isinstance(value,BaseException):raise value
        return value


class Writer:
    def __init__(self):self.writes=[];self.closed=False
    def write(self,text):self.writes.append(text)
    async def drain(self):pass
    def close(self):self.closed=True


class ControlTests(unittest.IsolatedAsyncioTestCase):
    async def session(self,responses,operation):
        self.writer=Writer()
        responses=['Login:','Password:','\n/cli>', *[r+'\n/cli>' if isinstance(r,str) else r for r in responses]]
        client=router.RouterClient('router','user','secret')
        with patch.object(router.telnetlib3,'open_connection',AsyncMock(return_value=(Reader(responses),self.writer))):
            return await operation(client)

    async def test_create_verifies_saved_rule(self):
        result=await self.session([EMPTY,'Rule created',table(RULE)],lambda c:c.async_create_time_restriction(RULE))
        self.assertTrue(result['created']);self.assertTrue(self.writer.closed)

    async def test_identical_rule_is_idempotent(self):
        result=await self.session([table(RULE)],lambda c:c.async_create_time_restriction(RULE))
        self.assertFalse(result['created'])
        self.assertFalse(any('create ' in value for value in self.writer.writes))

    async def test_conflicting_rule_is_preserved(self):
        other=commands.restriction(RULE.name,MAC,['Sat'],'01:00','06:00')
        with self.assertRaises(router.CommandError):await self.session([table(other)],lambda c:c.async_create_time_restriction(RULE))
        self.assertFalse(any('create ' in value or 'remove ' in value for value in self.writer.writes))

    async def test_unknown_table_prevents_writing(self):
        with self.assertRaises(parser.ParseError):await self.session(['unsupported format'],lambda c:c.async_create_time_restriction(RULE))
        self.assertFalse(any('create ' in value for value in self.writer.writes))

    async def test_lost_write_response_is_not_retried(self):
        with self.assertRaises(router.RouterError):await self.session([EMPTY,TimeoutError()],lambda c:c.async_create_time_restriction(RULE))
        self.assertEqual(sum('create ' in value for value in self.writer.writes),1)
        self.assertTrue(self.writer.closed)

    async def test_remove_preserves_other_rules(self):
        other=commands.restriction('Other',MAC,['Sun'],'01:00','02:00')
        result=await self.session([table(RULE,other),'Removed',table(other)],lambda c:c.async_remove_time_restriction(RULE.name))
        self.assertTrue(result['removed'])
        self.assertIn(f'{commands.TIME_RESTRICTIONS}remove --rmv-name={RULE.name}\r\n',self.writer.writes)

    async def test_missing_rule_remove_is_idempotent(self):
        result=await self.session([EMPTY],lambda c:c.async_remove_time_restriction(RULE.name))
        self.assertFalse(result['removed'])

    async def test_saved_result_must_match(self):
        with self.assertRaises(router.CommandError):await self.session([EMPTY,'Created',EMPTY],lambda c:c.async_create_time_restriction(RULE))

    async def test_rejected_command_is_not_reported_as_success(self):
        with self.assertRaises(router.CommandError):await self.session(['ERR::Permission denied'],lambda c:c.async_execute('/lan/config --ip=example'))
        self.assertTrue(self.writer.closed)

    async def test_generic_response_removes_echo_and_redacts_password(self):
        result=await self.session(['tree\nsecret\nresult'],lambda c:c.async_execute('tree'))
        self.assertEqual(result,'[redacted]\nresult')

    async def test_password_substring_does_not_corrupt_rule_verification(self):
        rule=commands.restriction('secret-night',MAC,['Mon'],'00:00','05:00')
        result=await self.session([EMPTY,'Created',table(rule)],lambda c:c.async_create_time_restriction(rule))
        self.assertEqual(result['rule']['name'],'secret-night')

    async def test_invalid_command_never_opens_a_connection(self):
        with patch.object(router.telnetlib3,'open_connection',AsyncMock()) as connect:
            with self.assertRaises(ValueError):await router.RouterClient('router','user','secret').async_execute('show\nquit')
            connect.assert_not_called()

    async def test_session_lock_serializes_commands(self):
        active=0; maximum=0
        async def connect(**kwargs):
            nonlocal active,maximum
            active+=1;maximum=max(active,maximum)
            writer=Writer()
            old_close=writer.close
            def close():
                nonlocal active
                old_close();active-=1
            writer.close=close
            await asyncio.sleep(0)
            return Reader(['Login:','Password:','\n/cli>','tree\nresult\n/cli>']),writer
        with patch.object(router.telnetlib3,'open_connection',connect):
            client=router.RouterClient('router','user','secret')
            await asyncio.gather(client.async_execute('tree'),client.async_execute('tree'))
        self.assertEqual(maximum,1)
