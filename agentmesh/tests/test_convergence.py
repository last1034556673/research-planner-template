"""Tests for convergence strategies."""

import time
import pytest
from agentmesh.message import Message
from agentmesh.convergence import TokenBudgetStrategy, QuietStrategy, ConsensusStrategy


def _msg(sender="a", kind="request"):
    return Message(sender=sender, receiver="b", kind=kind, content="test")


def test_token_budget():
    strategy = TokenBudgetStrategy(max_messages=3)
    msgs = [_msg() for _ in range(2)]
    assert not strategy.should_stop(msgs)
    msgs.append(_msg())
    assert strategy.should_stop(msgs)


def test_quiet_strategy():
    strategy = QuietStrategy(quiet_seconds=0.1)
    msg = _msg()
    msg.timestamp = time.time() - 1.0  # 1 second ago
    assert strategy.should_stop([msg])

    msg2 = _msg()
    msg2.timestamp = time.time()  # just now
    assert not strategy.should_stop([msg2])


def test_consensus_strategy():
    strategy = ConsensusStrategy(agent_names=["a", "b"])
    msgs = [Message(sender="a", receiver=None, kind="answer", content="done")]
    assert not strategy.should_stop(msgs)
    msgs.append(Message(sender="b", receiver=None, kind="result", content="done"))
    assert strategy.should_stop(msgs)
