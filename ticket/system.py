"""客服工单系统"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

@dataclass
class Ticket:
    tid: str
    status: str = "pending"  # pending/processing/waiting_player/replied/closed
    category: list = field(default_factory=list)  # 多选
    assignee: str = None
    reply_sent: bool = False
    created_at: datetime = None

class TicketSystem:
    # 活跃状态（需要超时检查）
    ACTIVE_STATUSES = {"pending", "processing", "waiting_player"}
    # 默认超时阈值
    DEFAULT_TIMEOUT = timedelta(days=7)

    def __init__(self):
        self.tickets: dict[str, Ticket] = {}
        self.agents: dict[str, list] = {}

    # 合法状态转换
    VALID_TRANSITIONS = {
        "pending": ["processing", "closed"],
        "processing": ["waiting_player", "replied", "closed"],
        "waiting_player": ["processing", "closed"],
        "replied": ["processing", "closed"],
        "closed": []
    }

    def update_ticket_status(self, tid: str, new_status: str) -> bool:
        ticket = self.tickets.get(tid)
        if not ticket:
            return False
        allowed = self.VALID_TRANSITIONS.get(ticket.status, [])
        if new_status not in allowed:
            return False
        ticket.status = new_status
        return True

    def _deliver_notification(self, ticket: Ticket) -> bool:
        # 实际通知网关的占位实现，失败时返回 False 或抛异常
        return True

    def send_reply_notification(self, tid: str) -> bool:
        ticket = self.tickets.get(tid)
        if not ticket:
            return False
        previous_status = ticket.status
        ticket.status = "replied"
        try:
            delivered = self._deliver_notification(ticket)
        except Exception:
            delivered = False
        if not delivered:
            # 发送失败：回退状态，不标记已发送
            ticket.status = previous_status
            ticket.reply_sent = False
            return False
        ticket.reply_sent = True
        return True

    def assign_ticket(self, tid: str, agent_id: str) -> bool:
        ticket = self.tickets.get(tid)
        if not ticket:
            return False
        # 负载均衡：若指定客服不是负载最低的，改派给负载最低的客服
        if self.agents:
            least_loaded = min(self.agents, key=lambda a: len(self.agents[a]))
            if agent_id in self.agents and len(self.agents[agent_id]) > len(self.agents[least_loaded]):
                agent_id = least_loaded
        ticket.assignee = agent_id
        if agent_id not in self.agents:
            self.agents[agent_id] = []
        self.agents[agent_id].append(tid)
        return True

    def check_timeout(self, now: datetime, threshold: timedelta = None) -> list:
        if threshold is None:
            threshold = self.DEFAULT_TIMEOUT
        timed_out = []
        for tid, ticket in self.tickets.items():
            if ticket.status not in self.ACTIVE_STATUSES:
                continue
            if ticket.created_at is not None and now - ticket.created_at >= threshold:
                timed_out.append(tid)
        return timed_out

    def get_tickets_by_category(self, category: str) -> list:
        result = []
        for tid, ticket in self.tickets.items():
            if category in ticket.category:
                result.append(tid)
        return result
