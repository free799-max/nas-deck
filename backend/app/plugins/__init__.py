"""
插件包初始化模块。

本模块负责导入所有插件实现类，使其在包加载时被注册到系统中。
当其他模块执行 `from app.plugins import ...` 或 `import app.plugins` 时，
本文件会自动执行，从而完成所有插件的注册。

当前已注册的插件：
- JellyfinPlugin: Jellyfin 媒体服务器插件
- KomgaPlugin: Komga 漫画服务器插件
- MoviePilotPlugin: MoviePilot 媒体自动化插件

新增插件时，需要在此文件中添加对应的导入语句。
"""

# 插件包初始化

# 导入 Jellyfin 媒体服务器插件
from app.plugins.jellyfin.plugin import JellyfinPlugin

# 导入 Komga 漫画服务器插件
from app.plugins.komga.plugin import KomgaPlugin

# 导入 MoviePilot 媒体自动化插件
from app.plugins.moviepilot.plugin import MoviePilotPlugin
