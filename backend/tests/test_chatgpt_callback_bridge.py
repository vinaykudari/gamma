"""The local relay must validate Gamma's active account-owned state, not an old attempt."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest

spec = importlib.util.spec_from_file_location(
    'callback_bridge', Path(__file__).resolve().parents[2] / 'tools/chatgpt_callback_bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def client(status=None):
    result = object.__new__(bridge.GammaClient)
    result.request = Mock(side_effect=[status or {'ready': False, 'error': ''}, {'providers': []}])
    return result


def test_current_ui_attempt_is_validated_and_completed():
    gamma = client()
    callback = 'http://localhost:1455/auth/callback?state=new-ui-state&code=test-only-code'
    assert gamma.finish_callback(callback) == {'providers': []}
    assert gamma.request.call_args_list[0].args == ('/api/ai/oauth/chatgpt/status', {'state': 'new-ui-state'})
    path, fields = gamma.request.call_args_list[1].args
    assert path == '/api/ai/oauth/chatgpt/complete'
    assert fields['state'] == 'new-ui-state' and fields['callback'] == callback


@pytest.mark.parametrize('error', ['sign-in session expired', 'wrong account'])
def test_unowned_or_expired_state_is_never_redeemed(error):
    gamma = client({'ready': False, 'error': error})
    with pytest.raises(bridge.CallbackRejected):
        gamma.finish_callback('http://localhost:1455/auth/callback?state=foreign&code=test-only-code')
    assert gamma.request.call_count == 1


@pytest.mark.parametrize('query', ['code=test', 'state=test', 'state=a&state=b&code=test',
                                  'state=test&code=a&code=b', 'state=test&error=access_denied'])
def test_malformed_or_declined_callback_never_contacts_gamma(query):
    gamma = client()
    with pytest.raises(bridge.CallbackRejected):
        gamma.finish_callback('http://localhost:1455/auth/callback?' + query)
    gamma.request.assert_not_called()
