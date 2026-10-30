# language: zh-CN
功能: WeTrade App - Android 冒烟

  场景: 启动 App 并校验首页元素
    当 启动应用[com.wetrade.crm.trial][com.wetrade.crm.MainActivity]
    而且 等待[8]秒
    而且 页面渲染完成出现元素[name=登录/注册]
