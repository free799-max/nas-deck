"""修复应用模板：共享 volumes 跳过 project_name 前缀。

编排共享配置合并时会给共享 volumes 项打上 shared=True 标记（见
services/orchestration/shared_config.py）。应用模板中相对路径默认会加上
project_name 前缀（应用私有目录），但共享存储（如 media/downloads）应直接
相对于 Docker 挂载目录。本脚本将各应用 yaml_template 中的路径表达式：

    vol.host_path if vol.host_path.startswith('/') else project_name ~ '/' ~ vol.host_path

替换为：

    vol.host_path if (vol.host_path.startswith('/') or vol.shared) else project_name ~ '/' ~ vol.host_path

执行方式：
    PYTHONPATH=./app .venv/bin/python -m scripts.fix_shared_volume_templates
"""

import asyncio

from sqlalchemy import select

from app.database import async_session
from app.models.app_store import App

OLD_EXPR = "vol.host_path if vol.host_path.startswith('/') else project_name ~ '/' ~ vol.host_path"
NEW_EXPR = "vol.host_path if (vol.host_path.startswith('/') or vol.shared) else project_name ~ '/' ~ vol.host_path"


async def main():
    async with async_session() as db:
        result = await db.execute(select(App))
        apps = result.scalars().all()
        for app in apps:
            template = app.yaml_template or ""
            if OLD_EXPR not in template:
                continue
            count = template.count(OLD_EXPR)
            app.yaml_template = template.replace(OLD_EXPR, NEW_EXPR)
            print(f"updated {app.name}: {count} 处")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
