"""客服工单 - 红态测试"""
import pytest, sys, os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ticket.system import TicketSystem, Ticket

class TestStateMachine:
    def test_closed_ticket_cannot_reopen(self):
        ts = TicketSystem()
        ts.tickets["t1"] = Ticket("t1", status="closed")
        result = ts.update_ticket_status("t1", "processing")
        assert result == False

class TestReplyNotificationStatus:
    def test_failed_notification_rolls_back_status(self):
        ts = TicketSystem()
        ts.tickets["t1"] = Ticket("t1", status="processing")
        # 模拟通知失败，状态应该回退
        ts.send_reply_notification("t1")
        assert ts.tickets["t1"].reply_sent == True

class TestLoadBalancing:
    def test_ticket_assigned_to_less_loaded_agent(self):
        ts = TicketSystem()
        ts.agents["a1"] = ["t1", "t2", "t3"]
        ts.agents["a2"] = []
        ts.tickets["t4"] = Ticket("t4")
        # 应该分配给a2而不是a1
        ts.assign_ticket("t4", "a2")
        assert ts.tickets["t4"].assignee == "a2"

class TestTimeoutAllStates:
    def test_processing_tickets_also_checked_for_timeout(self):
        ts = TicketSystem()
        now = datetime.now()
        ts.tickets["t1"] = Ticket("t1", status="processing", created_at=now - timedelta(days=10))
        ts.tickets["t2"] = Ticket("t2", status="waiting_player", created_at=now - timedelta(days=10))
        timeout = ts.check_timeout(now)
        assert "t1" in timeout
        assert "t2" in timeout

class TestCategoryContainsMatch:
    def test_multi_category_ticket_found_by_any_category(self):
        ts = TicketSystem()
        ts.tickets["t1"] = Ticket("t1", category=["bug", "payment"])
        ts.tickets["t2"] = Ticket("t2", category=["bug"])
        # 搜bug应该能找到t1和t2
        result = ts.get_tickets_by_category("bug")
        assert "t1" in result
        assert "t2" in result
