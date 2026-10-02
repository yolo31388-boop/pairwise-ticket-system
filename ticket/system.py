"""客服工单系统

状态机:
    pending -> processing / closed
    processing -> waiting_player / replied / closed
    waiting_player -> processing / closed
    replied -> processing / closed
    closed (终态, 不可再转换)
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

PENDING = "pending"
PROCESSING = "processing"
WAITING_PLAYER = "waiting_player"
REPLIED = "replied"
CLOSED = "closed"

# 除 closed 外都是活跃状态, 都需要超时检查
ACTIVE_STATUSES = (PENDING, PROCESSING, WAITING_PLAYER, REPLIED)

# 合法状态转换路径; 非法转换一律拒绝
VALID_TRANSITIONS = {
    PENDING: (PROCESSING, CLOSED),
    PROCESSING: (WAITING_PLAYER, REPLIED, CLOSED),
    WAITING_PLAYER: (PROCESSING, CLOSED),
    REPLIED: (PROCESSING, CLOSED),
    CLOSED: (),
}

DEFAULT_TIMEOUT_THRESHOLD = timedelta(days=7)
DEFAULT_MAX_AGENT_LOAD = 100


class InvalidStatusTransitionError(Exception):
    pass


@dataclass
class Ticket:
    tid: str
    status: str = PENDING
    category: list = field(default_factory=list)  # 多选分类
    assignee: str | None = None
    reply_sent: bool = False
    # 通知发送状态: none / pending / sent / failed
    notification_status: str = "none"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TicketSystem:
    def __init__(
        self,
        notifier=None,
        timeout_threshold: timedelta = DEFAULT_TIMEOUT_THRESHOLD,
        max_agent_load: int = DEFAULT_MAX_AGENT_LOAD,
    ):
        self.tickets: dict[str, Ticket] = {}
        # agent_id -> [ticket_id, ...]; 保留 list 形式以记录客服当前负载
        self.agents: dict[str, list] = {}
        # 显式标记的在线状态; 未登记的客服视为在线
        self.agent_online: dict[str, bool] = {}
        # notifier(ticket, content) -> bool, 用于注入/模拟通知发送结果
        self._notifier = notifier
        self.timeout_threshold = timeout_threshold
        self.max_agent_load = max_agent_load

    # ---------- 客服管理 ----------

    def register_agent(self, agent_id: str, online: bool = True) -> None:
        self.agents.setdefault(agent_id, [])
        self.agent_online[agent_id] = online

    def set_agent_online(self, agent_id: str, online: bool) -> None:
        self.register_agent(agent_id, online)

    def _is_online(self, agent_id: str) -> bool:
        # 未显式登记的客服默认在线
        return self.agent_online.get(agent_id, True)

    def _agent_load(self, agent_id: str) -> int:
        entry = self.agents.get(agent_id, [])
        if isinstance(entry, list):
            return len(entry)
        return len(entry.get("tickets", []))

    def _pick_least_loaded_agent(self) -> str | None:
        """在在线且未满载的客服中选负载最低的, 负载相同取最早登记的。"""
        candidates = [
            agent_id
            for agent_id in self.agents
            if self._is_online(agent_id)
            and self._agent_load(agent_id) < self.max_agent_load
        ]
        if not candidates:
            return None
        return min(candidates, key=self._agent_load)

    # ---------- 状态机 ----------

    def update_ticket_status(self, tid: str, new_status: str, raise_on_invalid: bool = False) -> bool:
        ticket = self.tickets.get(tid)
        if ticket is None:
            return False
        allowed = VALID_TRANSITIONS.get(ticket.status)
        if allowed is None or new_status not in allowed:
            if raise_on_invalid:
                raise InvalidStatusTransitionError(
                    f"ticket {tid}: {ticket.status} -> {new_status} is not allowed"
                )
            return False
        ticket.status = new_status
        ticket.updated_at = datetime.now()
        return True

    # ---------- 回复通知 ----------

    def _deliver_notification(self, ticket: Ticket, content: str | None = None) -> bool:
        """实际发送通知, 返回是否成功。可子类化覆盖或通过 notifier 注入。"""
        if self._notifier is None:
            return True
        try:
            return bool(self._notifier(ticket, content))
        except Exception:
            return False

    def send_reply_notification(self, tid: str, content: str | None = None) -> bool:
        ticket = self.tickets.get(tid)
        if ticket is None:
            return False
        # 只有能合法转到 replied 的工单才能发送回复通知
        if REPLIED not in VALID_TRANSITIONS.get(ticket.status, ()):
            return False

        previous_status = ticket.status
        ticket.notification_status = "pending"
        success = self._deliver_notification(ticket, content)

        if success:
            ticket.status = REPLIED
            ticket.reply_sent = True
            ticket.notification_status = "sent"
            ticket.updated_at = datetime.now()
            return True

        # 发送失败: 记录失败状态并回退工单状态, 不允许假装"已回复"
        ticket.status = previous_status
        ticket.reply_sent = False
        ticket.notification_status = "failed"
        return False

    # ---------- 工单分配 ----------

    def assign_ticket(self, tid: str, agent_id: str | None = None) -> bool:
        ticket = self.tickets.get(tid)
        if ticket is None:
            return False

        if agent_id is None:
            agent_id = self._pick_least_loaded_agent()
            if agent_id is None:
                return False
        else:
            if not self._is_online(agent_id):
                return False
            if self._agent_load(agent_id) >= self.max_agent_load:
                return False

        # 改派时先从原客服负载中移除
        previous = ticket.assignee
        if previous and previous != agent_id:
            bucket = self.agents.get(previous)
            if isinstance(bucket, list) and tid in bucket:
                bucket.remove(tid)

        ticket.assignee = agent_id
        bucket = self.agents.setdefault(agent_id, [])
        if tid not in bucket:
            bucket.append(tid)
        return True

    # ---------- 超时检查 ----------

    def check_timeout(self, now: datetime) -> list:
        """检查所有活跃状态(pending/processing/waiting_player/replied)的超时工单。"""
        timeout = []
        for tid, ticket in self.tickets.items():
            if ticket.status not in ACTIVE_STATUSES:
                continue
            if ticket.created_at is None:
                continue
            if now - ticket.created_at >= self.timeout_threshold:
                timeout.append(tid)
        return timeout

    # ---------- 分类查询 ----------

    def get_tickets_by_category(self, category: str) -> list:
        # category 是多选字段, 用包含匹配而不是等于匹配
        return [
            tid
            for tid, ticket in self.tickets.items()
            if category in ticket.category
        ]

    # 题目描述中使用的方法名别名
    send_ticket_reply_notification = send_reply_notification
    check_ticket_timeout = check_timeout
