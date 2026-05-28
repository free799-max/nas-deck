"""
APScheduler 定时调度器模块。

使用 APScheduler 的 AsyncIOScheduler 实现定时任务调度，
默认每 30 分钟执行一次订阅更新检查。检查流程包括：
1. 查询所有已启用的插件实例
2. 获取每个实例下的活跃订阅
3. 调用对应插件检测更新
4. 如有更新，通过通知引擎向用户推送通知
5. 将更新记录写入数据库

本模块在导入时会创建全局单例 scheduler 和 subscription_checker。
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import async_session
from app.models.plugin import PluginInstance
from app.models.subscription import Subscription, UpdateLog
from app.models.notification import NotificationChannel
from app.core.plugin_loader import plugin_loader
from app.core.notification_engine import notification_engine
from app.plugins.base import BasePlugin

logger = logging.getLogger(__name__)

# 全局调度器实例，基于 asyncio 异步调度
scheduler = AsyncIOScheduler()


class SubscriptionChecker:
    """订阅更新检查器，负责定时检测订阅源的变化并推送通知。

    核心工作流程：
    1. 从数据库查询所有已启用的插件实例
    2. 遍历每个实例，获取其关联的活跃订阅
    3. 调用插件的 check_updates 方法检测是否有新内容
    4. 将更新记录持久化到数据库
    5. 查询订阅用户的已启用通知渠道并推送通知
    """

    async def check_plugin_updates(
        self, plugin: BasePlugin, config: dict, subscriptions: list
    ):
        """调用插件检查订阅更新。

        将配置和订阅列表传递给插件的 check_updates 方法，
        由插件自行判断是否有新内容发布。

        Args:
            plugin: 插件实例，需实现 BasePlugin 接口。
            config: 插件实例的配置字典。
            subscriptions: 订阅信息列表，每项包含 id 和 item_id 字段。

        Returns:
            插件返回的更新列表。
        """
        return await plugin.check_updates(config, subscriptions)

    async def run(self):
        """执行一轮完整的订阅更新检查。

        这是调度器定时调用的入口方法。流程如下：
        1. 查询所有已启用的插件实例
        2. 对每个实例，查询其关联的活跃订阅
        3. 调用插件检测更新
        4. 将更新写入 UpdateLog 表
        5. 向订阅用户的所有已启用通知渠道推送通知
        6. 提交数据库事务
        """
        logger.debug("Starting subscription update check")
        async with async_session() as db:
            # 查询所有已启用的插件实例
            instances = (
                await db.execute(
                    select(PluginInstance).where(PluginInstance.enabled.is_(True))
                )
            ).scalars().all()

            # 遍历每个插件实例
            for instance in instances:
                # 根据插件名称获取已注册的插件对象
                plugin = plugin_loader.get(instance.plugin_name)
                if not plugin:
                    logger.warning(f"Plugin '{instance.plugin_name}' not found, skipping instance {instance.id}")
                    continue

                # 查询该实例下所有活跃状态的订阅
                subs = (
                    await db.execute(
                        select(Subscription).where(
                            Subscription.instance_id == instance.id,
                            Subscription.status == "active",
                        )
                    )
                ).scalars().all()

                if not subs:
                    # 没有活跃订阅，跳过该实例
                    continue

                # 调用插件检查更新
                try:
                    updates = await self.check_plugin_updates(
                        plugin=plugin,
                        config=instance.config,
                        subscriptions=[{"id": s.id, "item_id": s.item_id} for s in subs],
                    )
                except Exception as e:
                    logger.error(f"Plugin {instance.plugin_name} check failed: {e}")
                    continue

                # 处理检测到的每一条更新
                for update in updates:
                    # 创建更新日志记录
                    log = UpdateLog(
                        subscription_id=update.subscription_id,
                        title=update.title,
                        content=update.content,
                        notified=False,  # 初始标记为未通知
                    )
                    db.add(log)

                    # 查找该更新对应的订阅记录，以获取用户信息
                    sub = next((s for s in subs if s.id == update.subscription_id), None)
                    if sub:
                        # 查询该用户所有已启用的通知渠道
                        channels = (
                            await db.execute(
                                select(NotificationChannel).where(
                                    NotificationChannel.user_id == sub.user_id,
                                    NotificationChannel.enabled.is_(True),
                                )
                            )
                        ).scalars().all()

                        # 向所有已启用通知渠道推送消息
                        any_notified = False
                        for channel in channels:
                            try:
                                await notification_engine.send(
                                    channel.type,
                                    update.title,
                                    update.content,
                                    config=channel.config,
                                )
                                any_notified = True
                            except Exception as e:
                                logger.error(f"Notification failed via {channel.type}: {e}")
                        # 只要有任意一个渠道发送成功，就标记为已通知
                        log.notified = any_notified

            # 提交本轮所有数据库变更
            await db.commit()
            logger.debug("Subscription update check completed")


# 全局单例，供调度器调用
subscription_checker = SubscriptionChecker()


def setup_scheduler():
    """初始化并启动定时调度器。

    配置一个每 30 分钟执行一次的定时任务，任务 ID 为 "check_updates"。
    如果调度器已经在运行，则直接返回不做任何操作。
    如果任务已存在（例如之前已添加过），也不会重复添加。
    """
    if scheduler.running:
        # 调度器已启动，避免重复启动
        return
    if not scheduler.get_job("check_updates"):
        # 添加定时任务：每 30 分钟执行一次 subscription_checker.run
        scheduler.add_job(
            subscription_checker.run, "interval", minutes=30, id="check_updates"
        )
    scheduler.start()
    logger.info("Scheduler started")
