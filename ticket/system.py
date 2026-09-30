"""客服工单 - 含5个bug"""
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Ticket:
    tid: str
    status: str = "pending"  # pending/processing/waiting_player/replied/closed
    category: list = field(default_factory=list)  # 多选
    assignee: str = None
    reply_sent: bool = False  # bug2: 不记录发送状态
    created_at: datetime = None

class TicketSystem:
    def __init__(self):
        self.tickets: dict[str, Ticket] = {}
        self.agents: dict[str, list] = {}  # bug3: 不检查负载

    # 合法状态转换
    VALID_TRANSITIONS = {
        "pending": ["processing", "closed"],
        "processing": ["waiting_player", "replied", "closed"],
        "waiting_player": ["processing", "closed"],
        "replied": ["processing", "closed"],
        "closed": []  # bug1: 已关闭能重新打开
    }

    def update_ticket_status(self, tid: str, new_status: str) -> bool:
        # bug1: 不检查合法转换
        ticket = self.tickets.get(tid)
        if not ticket:
            return False
        ticket.status = new_status
        return True

    def send_reply_notification(self, tid: str) -> bool:
        # bug2: 不记录发送状态
        ticket = self.tickets.get(tid)
        if not ticket:
            return False
        ticket.status = "replied"
        return True

    def assign_ticket(self, tid: str, agent_id: str) -> bool:
        # bug3: 不检查负载
        ticket = self.tickets.get(tid)
        if not ticket:
            return False
        ticket.assignee = agent_id
        if agent_id not in self.agents:
            self.agents[agent_id] = []
        self.agents[agent_id].append(tid)
        return True

    def check_timeout(self, now: datetime) -> list:
        # bug4: 只检查pending
        timeout = []
        for tid, ticket in self.tickets.items():
            if ticket.status == "pending":
                timeout.append(tid)
        return timeout

    def get_tickets_by_category(self, category: str) -> list:
        # bug5: 用等于匹配，不用包含匹配
        result = []
        for tid, ticket in self.tickets.items():
            if ticket.category == [category]:
                result.append(tid)
        return result
