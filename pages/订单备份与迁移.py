from 功能组件_页面共用代码.release_runtime import ensure_current_release
ensure_current_release()

from 功能组件_页面共用代码.ui import inject_css, render_sidebar, require_staff_access, page_title
from 功能组件_页面共用代码.dialogue_ui import storage_panel

inject_css()
render_sidebar()
require_staff_access()
page_title("订单备份与迁移", "查看订单存储状态，下载完整备份，或将备份导入空数据库")
storage_panel()
